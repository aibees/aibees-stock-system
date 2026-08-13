"""
KIS 전용 백테스트 엔진.

trade_candle_data(또는 동일 스키마의 dict 리스트)를 시간순으로 순회하면서
- 무포지션: watch 시그널(get_action_in_watch)로 진입 판별
- 보유중  : 포지션 상태(entry_price/entry_atr/peak_high/bars_held)를 매 봉 갱신 후
            active 시그널(get_action_in_active)로 청산 판별
하고, 종목별 매매기록과 성과지표를 집계한다.

가정:
- 진입/청산 모두 '시그널 봉 다음날 시초가' 체결. 슬리피지/세금은 fee_rate로 근사.
- 다음 봉이 없는 경우(마지막 봉 시그널)에는 현재 종가로 체결.
- 한 종목당 동시에 1 포지션, 전액 진입(수익률은 트레이드별 % 복리 집계).
"""
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import Action
from stock_shared.strategy.kospi1 import KospiStrategy1


class KisBacktester:
    BUY_ACTIONS = {Action.BUY, Action.BUY_BREAKOUT, Action.BUY_DIP, Action.BUY_ALL, Action.BUY_SURGE}
    SELL_ACTIONS = {Action.SELL_PROFIT, Action.SELL_STOP_LOSS, Action.SELL_STOP_PROFIT,
                    Action.SELL_TRAIL, Action.SELL_TIME}

    def __init__(self, strategy=None, fee_rate: float = 0.0015):
        # fee_rate: 편도 수수료+세금 근사 (왕복은 2*fee_rate 차감). KOSPI 매도세 등 감안 기본 0.15%/편도
        self.strategy = strategy or KospiStrategy1()
        self.fee_rate = fee_rate

    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _wma(vals: list, period: int) -> list:
        """가중이동평균(WMA). 최근값 가중치 큼. 구간 미충족 인덱스는 None."""
        n = len(vals)
        out = [None] * n
        if period <= 0:
            return out
        denom = period * (period + 1) / 2.0
        for i in range(n):
            if i + 1 < period:
                continue
            s = 0.0
            for k in range(period):
                s += vals[i - period + 1 + k] * (k + 1)  # 오래된값→작은 가중치
            out[i] = s / denom
        return out

    def _hma(self, vals: list, period: int) -> list:
        """HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) ). 미산출 인덱스는 None."""
        import math
        if period <= 1:
            return [float(v) for v in vals]
        half = max(1, period // 2)
        sqrt_p = max(1, int(round(math.sqrt(period))))
        wma_half = self._wma(vals, half)
        wma_full = self._wma(vals, period)
        raw = [None] * len(vals)
        for i in range(len(vals)):
            if wma_half[i] is not None and wma_full[i] is not None:
                raw[i] = 2 * wma_half[i] - wma_full[i]
        # raw 에 None 구간이 있으므로, WMA 를 None-aware 로 재적용
        out = [None] * len(vals)
        denom = sqrt_p * (sqrt_p + 1) / 2.0
        for i in range(len(vals)):
            if i + 1 < sqrt_p:
                continue
            seg = raw[i - sqrt_p + 1:i + 1]
            if any(x is None for x in seg):
                continue
            s = 0.0
            for k in range(sqrt_p):
                s += seg[k] * (k + 1)
            out[i] = s / denom
        return out

    # ──────────────────────────────────────────────────────────────
    def _resolve_action(self, res) -> Action:
        if not res:
            return Action.HOLD
        ra = res.get('result_action')
        if isinstance(ra, Action):
            return ra
        name = res.get('action_type')
        return Action[name] if name in Action.__members__ else Action.HOLD

    def _new_user_info(self, base: UserOptionMeta) -> UserOptionMeta:
        """매 종목마다 포지션 상태를 깨끗이 초기화한 복제본 사용"""
        ui = UserOptionMeta()
        # 진입 판별에 쓰는 옵션 값 복사
        for k in ('vol_limit', 'vol_surge', 'delay_date', 'macd_recent_day',
                  'bb_over_recent_day', 'bb_width_threshold'):
            setattr(ui, k, getattr(base, k, getattr(ui, k)))
        ui.has_position = False
        ui.entry_price = ui.entry_atr = ui.peak_high = ui.peak_close = ui.avg_price = 0.0
        ui.bars_since_peak = 0
        ui.bars_held = 0
        return ui

    def _reset_position(self, ui: UserOptionMeta):
        ui.has_position = False
        ui.avg_price = ui.entry_price = ui.entry_atr = ui.peak_high = ui.peak_close = 0.0
        ui.bars_since_peak = 0
        ui.bars_held = 0

    # ──────────────────────────────────────────────────────────────
    def run_one(self, coin_code: str, rows: list[dict], base_user_info: UserOptionMeta) -> dict:
        """단일 종목 백테스트. rows = datetime 오름차순 정렬된 candle dict 리스트"""
        ui = self._new_user_info(base_user_info)

        # DB candle 에는 vol_avg 컬럼이 없으므로 백테스트 시 즉석 계산해 주입
        # (라이브 경로는 compute_indicator_df 가 vol_avg 를 채움)
        w = getattr(self.strategy, 'vol_ma_window', 20)
        vols = [float(r.get('volume') or 0) for r in rows]
        for i in range(len(rows)):
            rows[i]['vol_avg'] = (sum(vols[i + 1 - w:i + 1]) / w) if i + 1 >= w else 0.0

        # 추세국면 분류기(downtrend_ratio)도 DB 컬럼이 없으므로 즉석 계산해 주입.
        # = 최근 regime_window 봉 중 (close < ema60) 비율. ema60 미산출(0/None) 봉은 제외.
        # 066430/048910 분석 결론: 윈도우는 길게(90), 임계값은 높게(0.70)여야
        # 상승종목의 급등 초입을 살리면서 하락종목만 방어로 라우팅된다.
        rw = int(getattr(self.strategy, 'regime_window', 90))
        for i in range(len(rows)):
            lo = max(0, i + 1 - rw)
            below = total = 0
            for j in range(lo, i + 1):
                e60 = rows[j].get('ema60')
                if e60 in (None, 0, '0') or float(e60) == 0.0:
                    continue
                total += 1
                if float(rows[j].get('close') or 0) < float(e60):
                    below += 1
            rows[i]['downtrend_ratio'] = (below / total) if total > 0 else 0.0

        # ── HMA(Hull MA) 주입 ─────────────────────────────────────────
        # DB candle 에 hma 컬럼이 없으므로 종가로 즉석 계산해 주입.
        # (라이브 경로는 compute_indicator_df 가 동일 로직으로 hma/hma_slope 채움)
        # HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) )
        hp = int(getattr(self.strategy, 'hma_period', 20) or 20)
        closes = [float(r.get('close') or 0) for r in rows]
        hma_vals = self._hma(closes, hp)
        for i in range(len(rows)):
            rows[i]['hma'] = hma_vals[i] if hma_vals[i] is not None else 0.0
            prev_h = hma_vals[i - 1] if i > 0 else None
            rows[i]['hma_slope'] = (hma_vals[i] - prev_h) \
                if (hma_vals[i] is not None and prev_h is not None) else 0.0

        # ── 체결강도 proxy 주입 ───────────────────────────────────────
        # 일봉 candle 에는 실 체결강도(CTTR/STRN)가 없으므로 OHLCV 로 근사.
        # 종가위치 CLV = (close-low)/(high-low) 를 0~200 스케일로(100=중간=균형).
        # live 경로는 KIS inquire-ccnl 실값을 coin_info.chegyul_strength 로 대체 주입.
        for i in range(len(rows)):
            hi = float(rows[i].get('high') or 0)
            lo = float(rows[i].get('low') or 0)
            cl = float(rows[i].get('close') or 0)
            rows[i]['chegyul_strength'] = ((cl - lo) / (hi - lo) * 200.0) if hi > lo else 100.0

        trades = []
        in_pos = False
        entry_price = 0.0
        entry_dt = ''
        entry_action = None
        pending_buy = False          # 시그널 발생 → 다음 봉 시초가 진입 대기
        pending_entry_action = None

        for i in range(1, len(rows)):
            prev_info = UserCoinInfo.from_dict(rows[i - 1])
            coin_info = UserCoinInfo.from_dict(rows[i])

            # ── 전봉 BUY 시그널 → 이번 봉 시초가로 진입 ──
            if pending_buy:
                in_pos = True
                entry_price = float(coin_info.open) if coin_info.open else float(coin_info.close)
                entry_dt = coin_info.datetime
                entry_action = pending_entry_action
                ui.has_position = True
                ui.avg_price = entry_price
                ui.entry_price = entry_price
                ui.entry_atr = coin_info.atr
                ui.peak_high = coin_info.high
                ui.peak_close = coin_info.close
                ui.bars_since_peak = 0
                ui.bars_held = 0
                pending_buy = False

            if not in_pos:
                res = self.strategy.get_action_with_prev('watch', prev_info, coin_info, ui)
                action = self._resolve_action(res)
                if action in self.BUY_ACTIONS:
                    # 다음 봉이 있을 때만 진입 예약
                    if i + 1 < len(rows):
                        pending_buy = True
                        pending_entry_action = action
            else:
                # 보유 봉 상태 갱신 (트레일링/타임스탑 기준)
                prev_peak = ui.peak_high
                ui.peak_high = max(ui.peak_high, coin_info.high)
                ui.peak_close = max(ui.peak_close, coin_info.close)
                # 신고가(장중) 갱신 여부로 '추세 생존' 판정 → #4 동적 타임스탑에서 사용
                if ui.peak_high > prev_peak:
                    ui.bars_since_peak = 0
                else:
                    ui.bars_since_peak += 1
                ui.bars_held += 1

                res = self.strategy.get_action_with_prev('active', prev_info, coin_info, ui)
                action = self._resolve_action(res)
                if action in self.SELL_ACTIONS:
                    # 다음 봉 시초가로 청산, 없으면 현재 종가
                    if i + 1 < len(rows):
                        next_row = rows[i + 1]
                        exit_price = float(next_row.get('open') or next_row.get('close', coin_info.close))
                        exit_dt = next_row.get('datetime', coin_info.datetime)
                    else:
                        exit_price = float(coin_info.close)
                        exit_dt = coin_info.datetime
                    gross = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
                    net = gross - 2 * self.fee_rate
                    trades.append({
                        'coin': coin_code,
                        'entry_dt': entry_dt, 'entry_price': entry_price, 'entry_action': entry_action.name,
                        'exit_dt': exit_dt, 'exit_price': exit_price, 'exit_reason': action.name,
                        'bars_held': ui.bars_held,
                        'ret_gross': gross, 'ret_net': net,
                    })
                    in_pos = False
                    self._reset_position(ui)

        # 종료 시점 미청산 포지션 강제 정리(mark-to-market)
        if in_pos:
            last = UserCoinInfo.from_dict(rows[-1])
            gross = (last.close - entry_price) / entry_price if entry_price > 0 else 0.0
            net = gross - 2 * self.fee_rate
            trades.append({
                'coin': coin_code,
                'entry_dt': entry_dt, 'entry_price': entry_price, 'entry_action': entry_action.name,
                'exit_dt': last.datetime, 'exit_price': last.close, 'exit_reason': 'EOD',
                'bars_held': ui.bars_held, 'ret_gross': gross, 'ret_net': net,
            })

        return self._summarize(coin_code, trades)

    # ──────────────────────────────────────────────────────────────
    def _summarize(self, coin_code: str, trades: list[dict]) -> dict:
        n = len(trades)
        if n == 0:
            return {'coin': coin_code, 'trades': 0, 'win_rate': 0.0, 'total_return': 0.0,
                    'avg_ret': 0.0, 'profit_factor': 0.0, 'mdd': 0.0, 'avg_bars': 0.0,
                    'exit_breakdown': {}, 'trade_list': []}

        rets = [t['ret_net'] for t in trades]
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]

        # 복리 자본곡선 & MDD
        equity = 1.0
        curve = []
        for r in rets:
            equity *= (1 + r)
            curve.append(equity)
        peak = curve[0]
        mdd = 0.0
        for v in curve:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)

        gross_profit = sum(wins)
        gross_loss = -sum(losses)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        exit_breakdown = {}
        for t in trades:
            exit_breakdown[t['exit_reason']] = exit_breakdown.get(t['exit_reason'], 0) + 1

        return {
            'coin': coin_code,
            'trades': n,
            'win_rate': round(len(wins) / n * 100, 2),
            'total_return': round((equity - 1) * 100, 2),
            'avg_ret': round(sum(rets) / n * 100, 2),
            'avg_win': round(sum(wins) / len(wins) * 100, 2) if wins else 0.0,
            'avg_loss': round(sum(losses) / len(losses) * 100, 2) if losses else 0.0,
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
            'mdd': round(mdd * 100, 2),
            'avg_bars': round(sum(t['bars_held'] for t in trades) / n, 1),
            'exit_breakdown': exit_breakdown,
            'trade_list': trades,
        }

    # ──────────────────────────────────────────────────────────────
    def aggregate(self, results: list[dict]) -> dict:
        """여러 종목 결과를 전체 단위로 합산"""
        all_trades = [t for r in results for t in r['trade_list']]
        merged = self._summarize('ALL', all_trades)
        merged['symbols'] = len([r for r in results if r['trades'] > 0])
        return merged
