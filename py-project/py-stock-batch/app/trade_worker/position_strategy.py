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


def _s1_fingerprint(meta) -> tuple:
    """user_meta 의 s1_* 값들을 비교 가능한 튜플로. 설정 변경 감지용.

    user_options 에 updated_at 이 없어서 타임스탬프 비교를 못 한다.
    행 1건을 읽어 값 자체를 비교하는 편이 스키마 변경보다 싸고 정확하다
    (되돌리기·재저장으로 타임스탬프만 바뀐 경우를 오탐하지도 않는다).
    """
    return tuple(
        (k, str(getattr(meta, k, None)))
        for k in sorted(k for k in vars(meta) if k.startswith("s1_"))
    )


class SellStrategy:
    def __init__(self, engine, user_id: int, lookback_days: int = 250):
        self.engine = engine                    # KisEngine (get_daily_ohlcv)
        self.user_id = user_id
        self.lookback = lookback_days
        self.kis_service = KisService()
        self.strategy = KospiStrategy1()
        with get_session() as s:                # s1_* 파라미터 포함 유저 옵션
            self.user_meta = UserService().get_user_options(s, user_id)
        # user_options 의 s1_* 로 전략 기본값을 덮어쓴다. 이 호출이 빠지면
        # 화면에서 조정한 손절/익절/트레일링 값이 worker 에 전혀 반영되지 않는다.
        self.strategy.configure(self.user_meta)
        self._fingerprint = _s1_fingerprint(self.user_meta)

    # ── 장중 설정 재적용 ─────────────────────────────────────────────
    def reload_if_changed(self) -> list[tuple[str, object, object]]:
        """user_options 를 다시 읽어 s1_* 이 바뀌었으면 전략을 재구성한다.

        반환: [(속성명, 이전값, 새값), ...] — 변경 없으면 빈 리스트.

        ※ 기존 KospiStrategy1 인스턴스에 configure() 를 다시 호출하면 안 된다.
          configure 는 값이 None 이면 setattr 을 건너뛰므로, 유저가 필드를
          비워서(NULL) '기본값으로 되돌린' 변경이 반영되지 않고 옛 override 가
          그대로 남는다. 그래서 **새 인스턴스**를 만들어 갈아끼운다.
          SellExecutor/BuyExecutor 는 self.strategy.strategy 를 매번 조회하므로
          교체 즉시 새 파라미터를 쓴다.
        """
        with get_session() as s:
            new_meta = UserService().get_user_options(s, self.user_id)

        new_fp = _s1_fingerprint(new_meta)
        if new_fp == self._fingerprint:
            return []

        old_strategy = self.strategy
        old_meta = self.user_meta
        fresh = KospiStrategy1()
        fresh.configure(new_meta)

        # 실제로 달라진 전략 속성만 추린다(로그·알림용).
        changes = []
        for attr in vars(fresh):
            old_v, new_v = getattr(old_strategy, attr, None), getattr(fresh, attr)
            if old_v != new_v:
                changes.append((attr, old_v, new_v))

        # 전략 객체에 없고 user_meta 에만 있는 값도 로그에 남긴다.
        #   s1_buy_order 는 KospiStrategy1 속성이 아니라 BuyExecutor 가 직접 읽는다.
        #   위 루프만으로는 변경돼도 로그에 안 잡혀, 실제로 반영됐는지 사후 확인이
        #   불가능했다(매수 종목이 예상과 다를 때 원인 추적이 막힌다).
        for key in ("s1_buy_order",):
            old_v, new_v = getattr(old_meta, key, None), getattr(new_meta, key, None)
            if old_v != new_v:
                changes.append((key, old_v, new_v))

        self.user_meta = new_meta
        self.strategy = fresh
        self._fingerprint = new_fp
        return changes

    # ── 보유 포지션의 라인 재계산 (KIS API 미사용) ─────────────────────
    def recalc_lines(self, pos: dict) -> dict | None:
        """현재 파라미터로 stop/target/trail 을 다시 계산한다.

        일봉 지표(OBV 데드크로스·타임스탑·추세국면)는 손대지 않는다.
        그건 evaluate() 영역이고 KIS 조회가 필요하며, 애초에 실시간 판정 대상이
        아니다(sell_executor 문서 참고). 여기서는 **실시간 감시가 쓰는 3개 라인**만
        메모리 값(entry_price / peak_high / last_atr)으로 다시 만든다.
        → 외부 호출 0회라 장중에 몇 번을 불러도 부담이 없다.

        반환: DB/메모리에 반영할 state dict. 계산 불가면 None.
        """
        entry = _f(pos.get("entry_price"))
        if entry <= 0:
            return None

        s = self.strategy
        state = {
            "stop_price": round(entry * (1 - s.stop_loss_pct), 2),
            "target_price": round(entry * (1 + s.take_profit_pct), 2),
        }

        peak = _f(pos.get("peak_high") or entry)
        atr = _f(pos.get("last_atr") or pos.get("entry_atr"))
        peak_gain = (peak - entry) / entry

        # 활성화 게이트 미달이거나 트레일링 off → 라인 제거(None).
        # 트레일링을 껐는데 옛 라인이 남아 매도되는 사고를 막는다.
        if not getattr(s, "use_trailing", True) or peak_gain < getattr(s, "trail_activate_pct", 0.08):
            state["trail_line"] = None
        else:
            line, _src = s._trail_line_of(entry, peak, atr)
            state["trail_line"] = round(line, 2)
        return state

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
        old_ph = _f(pos.get("peak_high") or entry)
        old_bsp = int(pos.get("bars_since_peak") or 0)
        old_bars = int(pos.get("bars_held") or 0)

        # ── 고점 갱신 (peak_high 단일 기준) ────────────────────────────
        # 평시엔 SellExecutor 가 소켓 체결가로 실시간 갱신하고 세션 종료 시 flush 한다.
        # 여기서는 그 값을 신뢰하되, **전일 확정봉(prev)의 high 로 한 번 보정**한다.
        # worker 재시작·주말 공백·소켓 끊김 구간에서 놓친 고점을 복구하기 위한 안전망.
        # curr(당일 봉)는 09:00 시점이라 아직 시가 근처지만 포함해도 손해는 없다.
        curr_high, prev_high = _f(curr.get("high")), _f(prev.get("high"))
        new_ph = max(old_ph, prev_high, curr_high)
        if advance:
            bars_held = old_bars + 1
            bars_since_peak = 0 if new_ph > old_ph else old_bsp + 1
        else:
            bars_held, bars_since_peak = old_bars, old_bsp

        # 포지션 상태 주입
        um = self.user_meta
        um.entry_price = entry
        um.avg_price = entry
        um.entry_atr = _f(pos.get("entry_atr"))
        um.bars_held = bars_held
        um.peak_high = new_ph
        um.bars_since_peak = bars_since_peak

        coin = UserCoinInfo.from_dict({**curr, "coin": code})
        prev_i = UserCoinInfo.from_dict({**prev, "coin": code})
        result = self.strategy.get_action_in_active(prev_i, coin, um)
        ctx = result.get("sell_ctx", {})

        # 실시간 감시가 쓸 ATR. SellExecutor 가 장중 라인 재계산에 재사용하도록 state 로 넘긴다.
        atr_now = _f(curr.get("atr")) or um.entry_atr
        trail_line = self._calc_trail(entry, new_ph, atr_now)
        state = {
            "bars_held": bars_held,
            "peak_high": round(new_ph, 4),
            "last_atr": atr_now,
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

    def _calc_trail(self, entry, peak_high, atr):
        """트레일링 라인(활성 시). 실시간 감시용으로 항상 계산해 저장.

        고점 기준은 peak_high 단일(구 trail_basis 선택 제거).
        라인 산출식은 전략(KospiStrategy1._trail_line_of)에 위임한다.
        여기서 식을 복제하면 드로다운 캡 같은 변경이 실시간 감시에만 누락된다.
        ※ SellExecutor._advance_peak 이 장중에 같은 식으로 재계산한다.
        """
        s = self.strategy
        peak = peak_high
        if entry <= 0:
            return None
        peak_gain = (peak - entry) / entry
        if not getattr(s, "use_trailing", True) or peak_gain < getattr(s, "trail_activate_pct", 0.08):
            return None
        line, _src = s._trail_line_of(entry, peak, atr)
        return line
