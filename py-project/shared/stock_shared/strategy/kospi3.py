"""
kospi3.py — M3 (지정가 감시) 전략 골격.

운용모드 M3: 사용자가 등록한 지정가 세트(user_limit_order)로만 매매한다.
  · buy_price  이하 도달 → 매수
  · sell_price 이상 도달 → 매도
  · use_stop_loss='Y' 인 경우 stop_price 손절만 병행
  · 상태흐름 : WAIT_BUY → BOUGHT → DONE / STOPPED (loop_flag='Y' 면 재감시)

S1 매도 로직을 쓰지 않는 유일한 모드다.

※ 현재는 인터페이스만 있는 스켈레톤이다. 로직 미구현.
"""
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import StockStrategy, Action


class KospiStrategy3(StockStrategy):
    """M3 : 지정가 감시 매매."""

    MODE_CODE = 'M3'

    def __init__(self):
        super().__init__()
        # ── M3 전용 파라미터 (구현 시 채운다) ───────────────────────
        self.use_stop_loss = False
        self.loop_flag = False

    # ── 유저 설정 주입 ────────────────────────────────────────────
    def configure(self, user_info: UserOptionMeta) -> None:
        """user_limit_order 값을 인스턴스 파라미터에 반영."""
        raise NotImplementedError('KospiStrategy3.configure 미구현')

    # ── 매매 판정 ─────────────────────────────────────────────────
    def get_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> Action:
        raise NotImplementedError('KospiStrategy3.get_action 미구현')

    def get_action_with_prev(self, position_type: str, prev_info: UserCoinInfo,
                             coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        raise NotImplementedError('KospiStrategy3.get_action_with_prev 미구현')

    def get_action_in_watch(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                            user_info: UserOptionMeta) -> dict:
        """WAIT_BUY — 현재가 <= buy_price 판정."""
        raise NotImplementedError('KospiStrategy3.get_action_in_watch 미구현')

    def get_action_in_active(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                             user_info: UserOptionMeta) -> dict:
        """BOUGHT — 현재가 >= sell_price(또는 <= stop_price) 판정."""
        raise NotImplementedError('KospiStrategy3.get_action_in_active 미구현')
