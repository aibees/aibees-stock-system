"""매수추천(trade_buy_target_stock) 기반 실전 시뮬레이션 엔진.

app/test/sim_buy_target.py 를 화면(API)에서 쓸 수 있게 옮긴 것.
차이는 두 가지다:
  1) matplotlib/PNG 를 만들지 않고 **JSON 으로 반환**한다(차트는 프론트가 그린다).
  2) 종목 선택을 '당일 등락률 최저' 고정이 아니라
     **user_options.s1_buy_order** 로 한다 → worker(BuyExecutor)와 같은 순서.
     시뮬 결과와 실제 매수 종목이 어긋나면 시뮬을 볼 이유가 없다.

정책 (원본과 동일):
  · 동시 보유 1종목, 전량매수/전량매도.
  · 대기중: 당일(ymd) 추천이 있으면 정렬 1순위 종목을 매수.
            지나간 추천은 폐기 — 매일 그날 추천을 새로 본다.
  · 보유중: 매일 KospiStrategy1.get_action_in_active 로 매도판단.
            SELL 계열이면 당일 종가 매도. 진입일에도 1회 판정(bars_held=0).
  · 매도한 날은 재매수 안 함.
  · 체결가: 매수 = entry_price 옵션('close' | 'next_open'), 매도 = 당일 종가.

사전조건:
  후보 종목 캔들이 trade_candle_data 에 있어야 한다
  (TradeCandleBackfillJob 이 매일 21:00 에 적재).
"""
from decimal import Decimal

from sqlalchemy import text

from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.strategy.backtester import KisBacktester
from stock_shared.strategy.base import Action
from stock_shared.strategy.buy_order import describe_buy_order, make_buy_order_key
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.vo.userCoinInfo import UserCoinInfo

SELL_ACTIONS = {Action.SELL_PROFIT, Action.SELL_STOP_LOSS, Action.SELL_STOP_PROFIT,
                Action.SELL_TRAIL, Action.SELL_TIME}

# 편도 수수료+세금 근사. 왕복 2배로 반영한다.
DEFAULT_FEE_RATE = 0.0011
DEFAULT_INIT_CASH = 1_000_000

EXIT_REASON_KR = {
    'SELL_PROFIT': '익절', 'SELL_STOP_LOSS': '손절', 'SELL_STOP_PROFIT': '익절',
    'SELL_TRAIL': '트레일링', 'SELL_TIME': '타임스탑', 'EOD': '기간종료 청산',
}


class BuyTargetSimulator:
    """세션 1개를 물고 시뮬 1회를 수행한다. 인스턴스 재사용 금지(캔들 캐시 때문)."""

    def __init__(self, session, user_info, strategy=None):
        self.session = session
        self.ui = user_info
        self.strategy = strategy or KospiStrategy1()
        self.dao = TradeCandleDataDao()
        self._candle_cache = {}

    # ── 데이터 로딩 ────────────────────────────────────────────────
    def _trading_days(self, start: str, end: str = None) -> list:
        """trade_candle_data 에 존재하는 거래일(YYYY-MM-DD) 오름차순."""
        sql = "SELECT DISTINCT datetime FROM trade_candle_data WHERE datetime >= :s"
        p = {'s': start + ' 00:00:00'}
        if end:
            sql += " AND datetime <= :e"
            p['e'] = end + ' 23:59:59'
        sql += " ORDER BY datetime"
        return [r[0][:10] for r in self.session.execute(text(sql), p).all()]

    def _reco_by_day(self, start: str, end: str, buy_order: str) -> dict:
        """ymd -> [정렬된 추천 종목 dict, ...].

        정렬은 worker 와 동일한 make_buy_order_key 를 쓴다.
        정렬에 필요한 컬럼(score/volume/rate/rank_no/close)을 모두 조회한다.
        """
        sql = ("SELECT ymd, stock_code, stock_name, rate, close, volume, score, rank_no "
               "FROM trade_buy_target_stock WHERE ymd >= :s")
        p = {'s': start.replace('-', '')}
        if end:
            sql += " AND ymd <= :e"
            p['e'] = end.replace('-', '')

        by_day = {}
        for row in self.session.execute(text(sql), p).mappings().all():
            by_day.setdefault(row['ymd'], []).append(dict(row))

        key = make_buy_order_key(buy_order)
        for ymd in by_day:
            by_day[ymd].sort(key=key)
        return by_day

    @staticmethod
    def _to_float_row(r: dict) -> dict:
        """캔들 1행의 Decimal 값을 float 으로 정규화.

        trade_candle_data 는 DECIMAL(18,8) 컬럼이고 TradeCandleData.to_dict() 가
        Decimal 을 그대로 반환한다. 그대로 두면 전략 내부에서
            (peak - entry) / entry
        같은 연산이 Decimal 과 float 을 섞어
            unsupported operand type(s) for -: 'decimal.Decimal' and 'float'
        로 터진다. 포지션 상태(ui.peak_high 등)는 float 인데 캔들은 Decimal 이라
        max(float, Decimal) 이 Decimal 을 돌려주는 순간 오염이 시작된다.

        개별 사용처마다 float() 을 씌우면 반드시 한 군데를 빠뜨린다.
        캔들이 들어오는 이 입구 한 곳에서 정규화한다.
        (Decimal 만 변환하므로 datetime·macd_g_cross_n 같은 문자열은 그대로 유지)
        """
        return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in r.items()}

    def _candles(self, code: str):
        """(rows_list, {date: (idx, row)}) 캐시 로드."""
        if code not in self._candle_cache:
            raw = self.dao.select_candle_data(self.session, {'coin_code': code})
            rows = [self._to_float_row(r) for r in raw]
            by_date = {r['datetime'][:10]: (i, r) for i, r in enumerate(rows)}
            self._candle_cache[code] = (rows, by_date)
        return self._candle_cache[code]

    # ── 시뮬 본체 ──────────────────────────────────────────────────
    def run(self, start: str, end: str = None,
            init_cash: int = DEFAULT_INIT_CASH, fee_rate: float = DEFAULT_FEE_RATE,
            entry_price: str = 'next_open', skip_gapup: bool = False,
            buy_order: str = None) -> dict:

        days = self._trading_days(start, end)
        if not days:
            return {
                'ok': False,
                'message': f'{start} ~ {end or "최근"} 구간에 캔들 데이터가 없습니다. '
                           f'차트 백필 배치(STOCK_CANDLE_BACKFILL_JOB)를 먼저 실행하세요.',
                'summary': None, 'trades': [], 'equity_curve': [],
            }

        reco = self._reco_by_day(start, end, buy_order)
        ui = self.ui
        strategy = self.strategy

        trades = []
        mode = 'FLAT'              # FLAT(대기) | PENDING(다음날 시가 대기) | HOLD(보유)
        code = ep = entry_date = entry_name = None
        pend = None                # (code, name, 추천일종가)

        def _open(c, name, row, price, date):
            nonlocal code, ep, entry_date, entry_name, mode
            cur = UserCoinInfo.from_dict(row)
            code, entry_name = c, name
            ep = float(price)
            entry_date = date
            ui.has_position = True
            ui.avg_price = ui.entry_price = ep
            ui.entry_atr = float(cur.atr or 0)
            ui.peak_high = float(cur.high)
            ui.peak_close = float(cur.close)
            ui.bars_since_peak = 0
            ui.bars_held = 0
            mode = 'HOLD'

        def _eval_sell(d, advance: bool):
            """매도판정 1회. advance=True 면 포지션 상태(peak/bars) 선갱신.
            진입일은 advance=False — _open 에서 초기값을 이미 세팅했다."""
            nonlocal code, ep, entry_date, entry_name, mode
            rows, by_date = self._candles(code)
            if d not in by_date:
                return                       # 그날 미거래 → 다음날
            idx, cur_row = by_date[d]
            prev_row = rows[idx - 1] if idx > 0 else rows[idx]
            cur = UserCoinInfo.from_dict(cur_row)
            prev = UserCoinInfo.from_dict(prev_row)

            if advance:
                prev_peak = ui.peak_high
                ui.peak_high = max(ui.peak_high, cur.high)
                ui.peak_close = max(ui.peak_close, cur.close)
                ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
                ui.bars_held += 1

            res = strategy.get_action_with_prev('active', prev, cur, ui)
            action = res.get('result_action') or Action[res.get('action_type', 'HOLD')]
            if action in SELL_ACTIONS:
                xp = float(cur.close)
                gross = (xp - ep) / ep if ep > 0 else 0.0
                trades.append({
                    'coin': code, 'stock_name': entry_name or '',
                    'entry_dt': entry_date, 'entry_price': ep,
                    'exit_dt': d, 'exit_price': xp,
                    'exit_reason': action.name,
                    'exit_reason_kr': EXIT_REASON_KR.get(action.name, action.name),
                    'bars_held': ui.bars_held,
                    'ret_gross': gross, 'ret_net': gross - 2 * fee_rate,
                })
                mode = 'FLAT'
                code = ep = entry_date = entry_name = None
                ui.has_position = False

        for d in days:
            ymd = d.replace('-', '')

            if mode == 'HOLD':
                _eval_sell(d, advance=True)
                continue                     # 매도했든 아니든 그날은 재매수 안 함

            if mode == 'PENDING':
                pc, pname, pref = pend
                rows, by_date = self._candles(pc)
                if d in by_date:
                    _, row = by_date[d]
                    o_px = float(row['open'])
                    if skip_gapup and o_px > pref:      # 갭업 추격 회피
                        mode = 'FLAT'
                    else:
                        _open(pc, pname, row, o_px, d)
                        _eval_sell(d, advance=False)    # 진입일에도 판정
                        continue
                else:
                    mode = 'FLAT'            # 다음 거래일에 안 나옴 → 폐기

            if mode == 'FLAT':
                cand = reco.get(ymd)
                if not cand:
                    continue
                chosen = None
                for c in cand:               # 정렬 순서대로, 캔들 있는 첫 종목
                    rows, by_date = self._candles(c['stock_code'])
                    if d in by_date:
                        chosen = (c, by_date[d][1])
                        break
                if not chosen:
                    continue
                meta, cand_row = chosen
                if entry_price == 'next_open':
                    pend = (meta['stock_code'], meta.get('stock_name'), float(cand_row['close']))
                    mode = 'PENDING'
                else:
                    _open(meta['stock_code'], meta.get('stock_name'),
                          cand_row, float(cand_row['close']), d)
                    _eval_sell(d, advance=False)
                continue

        # ── 종료 시 미청산 포지션 정리 (마지막날 종가) ──────────────
        if mode == 'HOLD':
            rows, by_date = self._candles(code)
            last_idx = by_date.get(days[-1], (len(rows) - 1, rows[-1]))[0]
            last_close = float(rows[last_idx]['close'])
            gross = (last_close - ep) / ep if ep > 0 else 0.0
            trades.append({
                'coin': code, 'stock_name': entry_name or '',
                'entry_dt': entry_date, 'entry_price': ep,
                'exit_dt': days[-1], 'exit_price': last_close,
                'exit_reason': 'EOD', 'exit_reason_kr': EXIT_REASON_KR['EOD'],
                'bars_held': ui.bars_held,
                'ret_gross': gross, 'ret_net': gross - 2 * fee_rate,
            })

        return self._build_result(days, trades, init_cash, fee_rate,
                                  entry_price, skip_gapup, buy_order)

    # ── 결과 조립 ──────────────────────────────────────────────────
    def _build_result(self, days, trades, init_cash, fee_rate,
                      entry_price, skip_gapup, buy_order) -> dict:
        """요약 + 잔액곡선 + 매매로그. 원본 _report/_plot_result 가 하던 계산을 JSON 으로."""
        summary = KisBacktester(strategy=self.strategy)._summarize('SIM', trades)
        summary.pop('trade_list', None)      # trades 로 따로 내려주므로 중복 제거

        # 실제 주수 기준 복리 잔액 (원본 _plot_result 와 동일 계산)
        cash = float(init_cash)
        curve = [{'idx': 0, 'label': '시작', 'cash': round(cash)}]
        for i, t in enumerate(trades, 1):
            ep, xp = t['entry_price'], t['exit_price']
            sh = int(cash / (ep * (1 + fee_rate))) if ep > 0 else 0
            cash = cash - sh * ep * (1 + fee_rate) + sh * xp * (1 - fee_rate)
            t['shares'] = sh
            t['cash_after'] = round(cash)
            t['ret_net_pct'] = round(t['ret_net'] * 100, 2)
            curve.append({
                'idx': i,
                'label': f"{t['coin']} {t['entry_dt'][5:]}",
                'cash': round(cash),
            })

        return {
            'ok': True,
            'period': {'start': days[0], 'end': days[-1], 'trading_days': len(days)},
            'config': {
                'entry_price': entry_price,
                'skip_gapup': skip_gapup,
                'fee_rate': fee_rate,
                'buy_order': describe_buy_order(buy_order),
            },
            'summary': summary,
            'equity_curve': curve,
            'trades': trades,
            'final': {
                'init_cash': init_cash,
                'final_cash': round(cash),
                'pnl': round(cash - init_cash),
                'pnl_pct': round((cash / init_cash - 1) * 100, 2) if init_cash else 0.0,
            },
        }


def run_sim(session, user_info, **kwargs) -> dict:
    """단발 실행 헬퍼. 인스턴스를 매번 새로 만들어 캔들 캐시를 격리한다."""
    return BuyTargetSimulator(session, user_info).run(**kwargs)
