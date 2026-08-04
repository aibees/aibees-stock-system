"""
KisBacktester.py — KIS 전용 백테스트 엔진

배치(py-stock-batch)의 KisBacktester를 그대로 포팅.
가정/로직/집계 방식 일체 변경 금지.

- 진입/청산: 시그널 봉 다음날 시초가 체결 (없으면 현재 종가)
- 한 종목 동시 1 포지션, 전액 진입
- vol_avg / downtrend_ratio: DB 미저장이므로 run_one에서 즉석 계산하여 주입
"""
from app.domains.vo.UserCoinInfo import UserCoinInfo
from app.domains.vo.UserOptionMeta import UserOptionMeta
from app.services.kis.StockStrategy import Action
from app.services.kis.KospiStrategy import KospiStrategy1


class KisBacktester:
    BUY_ACTIONS = {Action.BUY, Action.BUY_BREAKOUT, Action.BUY_DIP, Action.BUY_ALL, Action.BUY_SURGE}
    SELL_ACTIONS = {Action.SELL_PROFIT, Action.SELL_STOP_LOSS, Action.SELL_STOP_PROFIT,
                    Action.SELL_TRAIL, Action.SELL_TIME}

    def __init__(self, strategy=None, fee_rate: float = 0.0015):
        self.strategy = strategy or KospiStrategy1()
        self.fee_rate = fee_rate

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
        """매 종목마다 포지션 상태를 깨끗이 초기화한 복제본"""
        ui = UserOptionMeta()
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
    def run_one(self, coin_code: str, rows: list, base_user_info: UserOptionMeta) -> dict:
        """단일 종목 백테스트. rows = datetime 오름차순 candle dict 리스트"""
        ui = self._new_user_info(base_user_info)

        # vol_avg 즉석 계산 주입 (DB 미저장)
        w = getattr(self.strategy, 'vol_ma_window', 20)
        vols = [float(r.get('volume') or 0) for r in rows]
        for i in range(len(rows)):
            rows[i]['vol_avg'] = (sum(vols[i + 1 - w:i + 1]) / w) if i + 1 >= w else 0.0

        # downtrend_ratio 즉석 계산 주입 (DB 미저장)
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

        trades = []
        in_pos  = False
        entry_price  = 0.0
        entry_dt     = ''
        entry_action = None
        pending_buy  = False
        pending_entry_action = None

        for i in range(1, len(rows)):
            prev_info = UserCoinInfo.from_dict(rows[i - 1])
            coin_info = UserCoinInfo.from_dict(rows[i])

            # ── 전봉 BUY 시그널 → 이번 봉 시초가로 진입 ──
            if pending_buy:
                in_pos       = True
                entry_price  = float(coin_info.open) if coin_info.open else float(coin_info.close)
                entry_dt     = coin_info.datetime
                entry_action = pending_entry_action
                ui.has_position = True
                ui.avg_price    = entry_price
                ui.entry_price  = entry_price
                ui.entry_atr    = coin_info.atr
                ui.peak_high    = coin_info.high
                ui.peak_close   = coin_info.close
                ui.bars_since_peak = 0
                ui.bars_held    = 0
                pending_buy     = False

            if not in_pos:
                res    = self.strategy.get_action_with_prev('watch', prev_info, coin_info, ui)
                action = self._resolve_action(res)
                if action in self.BUY_ACTIONS:
                    if i + 1 < len(rows):
                        pending_buy          = True
                        pending_entry_action = action
            else:
                # 보유 봉 상태 갱신
                prev_peak = ui.peak_high
                ui.peak_high  = max(ui.peak_high,  coin_info.high)
                ui.peak_close = max(ui.peak_close, coin_info.close)
                if ui.peak_high > prev_peak:
                    ui.bars_since_peak = 0
                else:
                    ui.bars_since_peak += 1
                ui.bars_held += 1

                res    = self.strategy.get_action_with_prev('active', prev_info, coin_info, ui)
                action = self._resolve_action(res)
                if action in self.SELL_ACTIONS:
                    if i + 1 < len(rows):
                        next_row   = rows[i + 1]
                        exit_price = float(next_row.get('open') or next_row.get('close', coin_info.close))
                        exit_dt    = next_row.get('datetime', coin_info.datetime)
                    else:
                        exit_price = float(coin_info.close)
                        exit_dt    = coin_info.datetime
                    gross = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
                    net   = gross - 2 * self.fee_rate
                    trades.append({
                        'coin':         coin_code,
                        'entry_dt':     entry_dt,
                        'entry_price':  entry_price,
                        'entry_action': entry_action.name,
                        'exit_dt':      exit_dt,
                        'exit_price':   exit_price,
                        'exit_reason':  action.name,
                        'bars_held':    ui.bars_held,
                        'ret_gross':    gross,
                        'ret_net':      net,
                    })
                    in_pos = False
                    self._reset_position(ui)

        # 종료 미청산 강제 청산 (mark-to-market)
        if in_pos:
            last  = UserCoinInfo.from_dict(rows[-1])
            gross = (last.close - entry_price) / entry_price if entry_price > 0 else 0.0
            net   = gross - 2 * self.fee_rate
            trades.append({
                'coin':         coin_code,
                'entry_dt':     entry_dt,
                'entry_price':  entry_price,
                'entry_action': entry_action.name,
                'exit_dt':      last.datetime,
                'exit_price':   last.close,
                'exit_reason':  'EOD',
                'bars_held':    ui.bars_held,
                'ret_gross':    gross,
                'ret_net':      net,
            })

        return self._summarize(coin_code, trades)

    # ──────────────────────────────────────────────────────────────
    def _summarize(self, coin_code: str, trades: list) -> dict:
        n = len(trades)
        if n == 0:
            return {'coin': coin_code, 'trades': 0, 'win_rate': 0.0, 'total_return': 0.0,
                    'avg_ret': 0.0, 'profit_factor': 0.0, 'mdd': 0.0, 'avg_bars': 0.0,
                    'exit_breakdown': {}, 'trade_list': []}

        rets   = [t['ret_net'] for t in trades]
        wins   = [r for r in rets if r > 0]
        losses = [r for r in rets if r <= 0]

        # 복리 자본곡선 & MDD
        equity = 1.0
        curve  = []
        for r in rets:
            equity *= (1 + r)
            curve.append(equity)
        peak = curve[0]
        mdd  = 0.0
        for v in curve:
            peak = max(peak, v)
            mdd  = min(mdd, v / peak - 1)

        gross_profit  = sum(wins)
        gross_loss    = -sum(losses)
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        exit_breakdown = {}
        for t in trades:
            exit_breakdown[t['exit_reason']] = exit_breakdown.get(t['exit_reason'], 0) + 1

        return {
            'coin':          coin_code,
            'trades':        n,
            'win_rate':      round(len(wins) / n * 100, 2),
            'total_return':  round((equity - 1) * 100, 2),
            'avg_ret':       round(sum(rets) / n * 100, 2),
            'avg_win':       round(sum(wins) / len(wins) * 100, 2) if wins else 0.0,
            'avg_loss':      round(sum(losses) / len(losses) * 100, 2) if losses else 0.0,
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
            'mdd':           round(mdd * 100, 2),
            'avg_bars':      round(sum(t['bars_held'] for t in trades) / n, 1),
            'exit_breakdown': exit_breakdown,
            'trade_list':    trades,
        }

    # ──────────────────────────────────────────────────────────────
    def aggregate(self, results: list) -> dict:
        """여러 종목 결과를 ALL 단위로 합산"""
        all_trades = [t for r in results for t in r['trade_list']]
        merged = self._summarize('ALL', all_trades)
        merged['symbols'] = len([r for r in results if r['trades'] > 0])
        return merged
