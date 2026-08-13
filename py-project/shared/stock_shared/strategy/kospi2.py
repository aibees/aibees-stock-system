"""
kospi2.py — M2 (KOSPI100 ETF ↔ 인버스 교대) 전략 골격.

운용모드 M2: KOSPI 추세를 판단해 정방향 ETF / 인버스 ETF 를 교대 매매한다.
  · 방향 판정 (trend_symbol 일봉 기준)
        score = (close>MA20 ? +1:-1) + (MA5>MA20 ? +1:-1) + (MACD_hist>0 ? +1:-1)
        score >=  threshold_long   → LONG    (정방향 ETF)
        score <= -threshold_short  → SHORT   (인버스 ETF)
        그 외                      → NEUTRAL (현금 대기)
  · 같은 방향 연속 시 재진입하지 않고 보유 유지(핑퐁 방지)
  · 보유 중 반대 신호 → SELL_REGIME_FLIP 청산 후 다음 tick 에서 반대편 진입
  · flip_cooldown_bars 로 청산 직후 재진입 방지

※ 기존 HMA/OBV/MACD 조합 전략은 제거되었다. 현재는 인터페이스만 있는 스켈레톤이다.
"""
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import StockStrategy, Action


class KospiStrategy2(StockStrategy):
    """M2 : ETF 정방향/인버스 교대 매매."""

    MODE_CODE = 'M2'

    def __init__(self):
        super().__init__()
        # ── M2 전용 파라미터 (구현 시 채운다) ───────────────────────
        self.ma_short = 5
        self.ma_long = 20
        self.threshold_long = 2
        self.threshold_short = 2
        self.flip_cooldown_bars = 0

    # ── 유저 설정 주입 ────────────────────────────────────────────
    def configure(self, user_info: UserOptionMeta) -> None:
        """active_config(long_code/short_code/trend_symbol/임계값)를 반영."""
        raise NotImplementedError('KospiStrategy2.configure 미구현')

    # ── 방향 판정 ─────────────────────────────────────────────────
    def decide_direction(self, coin_info: UserCoinInfo) -> str:
        """LONG / SHORT / NEUTRAL 반환."""
        raise NotImplementedError('KospiStrategy2.decide_direction 미구현')

    # ── 매매 판정 ─────────────────────────────────────────────────
    def get_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> Action:
        raise NotImplementedError('KospiStrategy2.get_action 미구현')

    def get_action_with_prev(self, position_type: str, prev_info: UserCoinInfo,
                             coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        raise NotImplementedError('KospiStrategy2.get_action_with_prev 미구현')

    def get_action_in_watch(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                            user_info: UserOptionMeta) -> dict:
        """미보유 — 방향 판정 후 해당 ETF 매수 여부."""
        raise NotImplementedError('KospiStrategy2.get_action_in_watch 미구현')

    def get_action_in_active(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                             user_info: UserOptionMeta) -> dict:
        """보유 — 매도 판정 + 반대 신호 시 강제 청산."""
        raise NotImplementedError('KospiStrategy2.get_action_in_active 미구현')
