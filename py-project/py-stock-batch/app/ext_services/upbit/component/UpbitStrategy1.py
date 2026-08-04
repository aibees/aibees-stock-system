from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import StockStrategy, Action


class UpbitStrategy1(StockStrategy):
    def __init__(self):
        super().__init__()
        self.stop_loss_pct = 0.03       # 3% 손실 시 칼손절
        self.take_profit_pct = 0.05     # 1차 익절 목표 (눌림목용)
        self.trailing_stop_activation = 0.05 # 5% 수익나면 트레일링 스탑 활성화

        # 지표 기준값
        self.rsi_buy = 35.0
        self.rsi_sell = 70.0
        self.stoch_buy = 20.0
        self.stoch_sell = 80.0

    # def execute(self, trade_data, coin_info: UserCoinInfo, user_info: UserOptionMeta):


    def get_action_with_prev(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        pass


    def get_action(self, coin_info: UserCoinInfo, user_info: UserOptionMeta) -> Action:
        # 종가 유효성 검사
        if coin_info.close == 0.0:
            return Action.HOLD

        if user_info.has_position: # 매도 포지션
            return self.get_action_in_active(coin_info, user_info)

        else: # 매수 포지션
            return self.get_action_in_watch(coin_info)


    # 매수포지션일 때
    def get_action_in_watch(self, coin_info: UserCoinInfo) -> Action:
        is_uptrend = (coin_info.close > coin_info.ema120) or (coin_info.ema20 > coin_info.ema60)

        if not is_uptrend:
            return Action.HOLD

        if (coin_info.close > coin_info.bb_upper) and (coin_info.vol_ratio > 2.0) and (
                coin_info.macd > coin_info.macd_s):
            # BB폭이 좁다가 상단 돌파 + 거래량 폭발 + MACD 상승
            return Action.BUY_BREAKOUT

        # 가격 위치: BB 하단 ~ BB 중간 사이 or EMA 60일선 지지
        price_condition = (coin_info.close <= coin_info.bb_lower * 1.01) or (
                    abs(coin_info.close - coin_info.ema60) / coin_info.ema60 < 0.01)

        # 오실레이터: 과매도 찍고 돌아서는 순간
        oscillator_condition = (coin_info.rsi < 45.0) and (coin_info.fs_k > coin_info.fs_d)

        if price_condition and oscillator_condition:
            return Action.BUY_DIP

        return Action.HOLD

    # 매도포지션일 때
    def get_action_in_active(self, coin_info: UserCoinInfo, user_info: UserOptionMeta) -> Action:
        current_profit_pct = (coin_info.close - user_info.avg_price) / user_info.avg_price

        # 1. stop loss
        if current_profit_pct <= -self.stop_loss_pct:
            return Action.SELL_STOP

        # 2. 트레일링 스탑 / 추세 이탈 매도
        # 가격이 EMA 20선 아래로 강하게 깨지면 매도 (단기 추세 종료)
        # 단, 노이즈 방지를 위해 종가가 EMA20보다 0.5% 이상 낮을 때
        if coin_info.close < (coin_info.ema20 * 0.995):
            return Action.SELL_TRAIL

        # 3. 과열 신호 매도 (RSI 75 이상 + BB 상단 돌파 시 분할 매도 관점)
        # 여기서는 전량 매도로 구현
        if coin_info.rsi > self.rsi_sell and coin_info.close > coin_info.bb_upper:
            return Action.SELL_PROFIT

        # 4. (눌림목 전용) 목표 수익 달성 후 스토캐스틱 데드크로스
        # 수익은 났는데(5% 이상), 모멘텀이 꺾이면(K < D) 매도
        if current_profit_pct > self.take_profit_pct:
            if coin_info.fs_k < coin_info.fs_d:
                return Action.SELL_PROFIT

        return Action.HOLD