"""
매도 판정 = KospiStrategy1 재사용 (docs_buy_target_sim_spec.md §4 와 동일 로직).

worker 전용 포지션(trade_worker_position)의 HOLDING 종목에 대해:
  - 일봉 OHLCV(KisEngine.get_daily_ohlcv) → 지표계산(KisService.compute_indicator_df)
  - 포지션 상태(entry_price/entry_atr/bars_held/peak/bars_since_peak) 주입
  - KospiStrategy1.get_action_in_active 로 action + stop/target/trail 산출
을 수행한다. daily 배치(StockSellCheckJob)·trade_sell_target_stock 과 무관하게 자체 계산.
"""
import logging
from datetime import date, timedelta

from app.batches.services.userService import UserService
from app.config.contextManager import get_session
from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.ext_services.kis.component.KisStockService import KisService
from stock_shared.strategy.kospi1 import KospiStrategy1

log = logging.getLogger("trade_worker.strategy")


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class SellStrategy:
    def __init__(self, engine, user_id: int, lookback_days: int = 250):
        self.engine = engine                    # KisEngine (get_daily_ohlcv)
        self.user_id = user_id
        self.lookback = lookback_days
        self.kis_service = KisService()
        self.strategy = KospiStrategy1()
        with get_session() as s:                # s1_* 파라미터 포함 유저 옵션
            self.user_meta = UserService().get_user_options(s, user_id)

    # ── 일봉 지표 계산 (공통) ────────────────────────────────────────
    def _indicators(self, code: str):
        end = date.today().strftime("%Y-%m-%d")
        start = (date.today() - timedelta(days=self.lookback)).strftime("%Y-%m-%d")
        ohlcv = self.engine.get_daily_ohlcv(code, start, end)
        if ohlcv is None or len(ohlcv) < 2:
            return None
        computed = self.kis_service.compute_indicator_df(ohlcv, user_info=self.user_meta)
        computed.fillna(0.0, inplace=True)
        return computed.to_dict(orient="records")

    # ── 매수 직후 초기 라인(즉시 손절/익절 보호) ──────────────────────
    def initial_lines(self, code: str, entry_price: float):
        """진입 즉시 stop/target + entry_atr 산출. 진입일엔 매도판정 안 함(spec §3.3)."""
        rows = self._indicators(code)
        atr = _f(rows[-1].get("atr")) if rows else 0.0
        stop = entry_price * (1 - self.strategy.stop_loss_pct)
        target = entry_price * (1 + self.strategy.take_profit_pct)
        return {"entry_atr": atr, "stop_price": round(stop, 2), "target_price": round(target, 2)}

    # ── 일별 평가 (HOLDING 포지션) ───────────────────────────────────
    def evaluate(self, pos: dict):
        """포지션 1건 평가 → (result dict, state dict). 데이터 부족 시 (None, None)."""
        code = pos["stock_code"]
        rows = self._indicators(code)
        if not rows or len(rows) < 2:
            return None, None
        curr, prev = rows[-1], rows[-2]

        today = date.today().strftime("%Y%m%d")
        advance = (pos.get("last_check_ymd") != today)   # 하루 1회만 봉수/피크 전진

        entry = _f(pos.get("entry_price"))
        old_pc = _f(pos.get("peak_close") or entry)
        old_ph = _f(pos.get("peak_high") or entry)
        old_bsp = int(pos.get("bars_since_peak") or 0)
        old_bars = int(pos.get("bars_held") or 0)

        curr_close, curr_high = _f(curr.get("close")), _f(curr.get("high"))
        new_pc = max(old_pc, curr_close)
        new_ph = max(old_ph, curr_high)
        if advance:
            bars_held = old_bars + 1
            bars_since_peak = 0 if (new_ph > old_ph or new_pc > old_pc) else old_bsp + 1
        else:
            bars_held, bars_since_peak = old_bars, old_bsp

        # 포지션 상태 주입
        um = self.user_meta
        um.entry_price = entry
        um.avg_price = entry
        um.entry_atr = _f(pos.get("entry_atr"))
        um.bars_held = bars_held
        um.peak_close = new_pc
        um.peak_high = new_ph
        um.bars_since_peak = bars_since_peak

        coin = UserCoinInfo.from_dict({**curr, "coin": code})
        prev_i = UserCoinInfo.from_dict({**prev, "coin": code})
        result = self.strategy.get_action_in_active(prev_i, coin, um)
        ctx = result.get("sell_ctx", {})

        trail_line = self._calc_trail(entry, new_pc, new_ph, _f(curr.get("atr")) or um.entry_atr)
        state = {
            "bars_held": bars_held,
            "peak_close": round(new_pc, 4),
            "peak_high": round(new_ph, 4),
            "bars_since_peak": bars_since_peak,
            "last_check_ymd": today,
            "stop_price": ctx.get("stop_price"),
            "target_price": ctx.get("target_price"),
            "trail_line": round(trail_line, 2) if trail_line is not None else None,
            "action_type": result.get("action_type", "HOLD"),
            "profit_pct": ctx.get("profit_pct"),
            "sell_reason": ctx.get("sell_reason") or result.get("action_type"),
        }
        return result, state

    def _calc_trail(self, entry, peak_close, peak_high, atr):
        """트레일링 라인(활성 시). 실시간 감시용으로 항상 계산해 저장."""
        s = self.strategy
        basis = getattr(s, "trail_basis", "close")
        peak = peak_close if basis == "close" else peak_high
        if entry <= 0:
            return None
        peak_gain = (peak - entry) / entry
        if not getattr(s, "use_trailing", True) or peak_gain < getattr(s, "trail_activate_pct", 0.08):
            return None
        if atr and atr > 0:
            return peak - getattr(s, "k_trail_atr", 3.0) * atr
        return peak * (1 - getattr(s, "trail_floor_pct", 0.10))
