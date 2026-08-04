from abc import ABC, abstractmethod
from enum import Enum

from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.domains.vo.UserOptionMeta import UserOptionMeta

class Action(Enum):
    HOLD = 0
    BUY = 1
    BUY_BREAKOUT = 2  # 돌파 매수
    BUY_DIP = 3       # 눌림목 매수
    BUY_ALL = 4
    BUY_SURGE = 5
    SELL_PROFIT = 11   # 익절
    SELL_STOP_LOSS = 12     # 손절
    SELL_STOP_PROFIT = 14
    SELL_TRAIL = 13    # 트레일링 스탑 (추세 꺾임)
    SELL_TIME = 15     # 타임 스탑 (보유기간 초과, 정체)


class StockStrategy(ABC):

    def __init__(self):
        self.balance_limit = 5000
        self.stop_loss_pct = 0.03       # 3% 손실 시 칼손절 (ATR 보조 캡)
        self.take_profit_pct = 0.07     # 1차 익절 목표 (눌림목용)

        # ── ATR 기반 매도 설정 (균형) ──────────────────────────────
        self.k_stop_atr = 2.0     # 진입가 - 2*ATR = 초기 손절
        self.k_trail_atr = 3.0    # 고점 - 3*ATR = 트레일링(샹들리에) 스탑
        self.k_tp_atr = 4.0       # 진입가 + 4*ATR = 목표 익절 (≈2R)
        self.max_hold_bars = 10   # 타임 스탑: 보유 봉수 한도
        self.time_stop_band = 0.015  # 타임 스탑 발동 시 정체 판정 수익률 밴드(±1.5%)

    def get_result_with_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> dict:
        prev_info = UserCoinInfo.from_dict(trade_data[len(trade_data)-2])
        coin_info = UserCoinInfo.from_dict(trade_data[len(trade_data)-1])
        return self.get_action_with_prev('watch', prev_info, coin_info, user_info)


    @abstractmethod
    def get_action(self, coin_info: UserCoinInfo, user_info: UserOptionMeta):
        pass

    @abstractmethod
    def get_action_with_prev(self, position_type, prev_info: UserCoinInfo, coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        pass