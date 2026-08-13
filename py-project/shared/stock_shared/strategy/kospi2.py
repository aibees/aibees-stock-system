"""
kospi2.py — M2 (단일 종목 고정) 전략 골격.

운용모드 M2: 사용자가 지정한 종목 1개만 매매한다.
  · 매수 진입 규칙(entry_rule)
      IMMEDIATE : 장 시작 즉시 전량 매수
      SIGNAL    : 매수 필터 충족 시 매수
  · 매도 판정은 이 클래스가 자체적으로 갖는다(KospiStrategy1 상속하지 않음).

※ 현재는 인터페이스만 있는 스켈레톤이다. 로직 미구현.
"""
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import StockStrategy, Action


class KospiStrategy2(StockStrategy):
    """M2 : 단일 종목 고정 매매."""

    MODE_CODE = 'M2'

    def __init__(self):
        super().__init__()
        # ── M2 전용 파라미터 (구현 시 채운다) ───────────────────────
        self.entry_rule = 'SIGNAL'   # IMMEDIATE | SIGNAL
        self.invest_ratio = 1.0      # 예수금 대비 투입 비율

    # ── 유저 설정 주입 ────────────────────────────────────────────
    def configure(self, user_info: UserOptionMeta) -> None:
        """user_options / active_config 값을 인스턴스 파라미터에 반영."""
        raise NotImplementedError('KospiStrategy2.configure 미구현')

    # ── 매매 판정 ─────────────────────────────────────────────────
    def get_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> Action:
        raise NotImplementedError('KospiStrategy2.get_action 미구현')

    def get_action_with_prev(self, position_type: str, prev_info: UserCoinInfo,
                             coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        raise NotImplementedError('KospiStrategy2.get_action_with_prev 미구현')

    def get_action_in_watch(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                            user_info: UserOptionMeta) -> dict:
        """미보유 상태 — 매수 여부 판정."""
        raise NotImplementedError('KospiStrategy2.get_action_in_watch 미구현')

    def get_action_in_active(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                             user_info: UserOptionMeta) -> dict:
        """보유 상태 — 매도 여부 판정."""
        raise NotImplementedError('KospiStrategy2.get_action_in_active 미구현')
