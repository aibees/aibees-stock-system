from app.domain.dto.userCoinInfo import UserCoinInfo
from app.domain.dto.userOptionMeta import UserOptionMeta
from app.ext_services.StockStrategy import StockStrategy, Action


class UpbitStrategy2(StockStrategy):
    def __init__(self):
        super().__init__()


    def get_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> Action:
        pass

    def get_action_with_prev(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo, user_info: UserOptionMeta):

        result_action = Action.HOLD

        check_cnt = 0
        sma_checker = self.check_stochastic(user_info, prev_info, coin_info)
        if sma_checker:
            check_cnt += 1

        stochastic_checker = self.check_stochastic(user_info, prev_info, coin_info)
        if stochastic_checker:
            check_cnt += 1

        rsi_checker = self.check_rsi(user_info, prev_info, coin_info)
        if rsi_checker:
            check_cnt += 1

        macd_checker = self.check_macd(user_info, prev_info, coin_info)
        if macd_checker:
            check_cnt += 1

        obv_checker = self.check_obv(user_info, prev_info, coin_info)
        if obv_checker:
            check_cnt += 1

        print("date : " + coin_info.datetime)
        print("sma : " + str(sma_checker) + " | stk : " + str(stochastic_checker) + " | rsi : " + str(rsi_checker) + " | macd : " + str(macd_checker) + " | obv : " + str(obv_checker))
        if user_info.has_position:
            current_profit_pct = (coin_info.close - user_info.avg_price) / user_info.avg_price

            # stop pre-profit
            if current_profit_pct >= self.take_profit_pct:
                return {
                    'sma_checker': 'N',
                    'rsi_checker': 'N',
                    'macd_checker': 'N',
                    'stochastic_checker': 'N',
                    'obv_checker': 'N',
                    'result_action': Action.SELL_STOP_PROFIT
                }

            # stop loss
            if current_profit_pct <= -self.stop_loss_pct:
                return {
                    'sma_checker': 'N',
                    'rsi_checker': 'N',
                    'macd_checker': 'N',
                    'stochastic_checker': 'N',
                    'obv_checker': 'N',
                    'result_action': Action.SELL_STOP_LOSS
                }

            bb_upper_checker = coin_info.bb_lower_chk < 1
            if bb_upper_checker:
                check_cnt += 1

            if  check_cnt >= 4:
                result_action = Action.SELL_PROFIT

        else:
            bb_lower_checker = coin_info.bb_lower_chk > 0
            if bb_lower_checker:
                check_cnt += 1

            if  check_cnt >= 4:
                result_action = Action.BUY_DIP

        print("has_position : " + str(user_info.has_position) + " | cnt : " + str(check_cnt))
        print("action : " + result_action.name)

        return {
            'sma_checker': 'Y' if sma_checker else 'N',
            'rsi_checker': 'Y' if rsi_checker else 'N',
            'macd_checker': 'Y' if macd_checker else 'N',
            'stochastic_checker': 'Y' if stochastic_checker else 'N',
            'obv_checker': 'Y' if obv_checker else 'N',
            'result_action': result_action
        }

    def check_sma(self, user_info: UserOptionMeta, prev_info: UserCoinInfo, coin_info: UserCoinInfo) -> bool:
        if user_info.has_position:
            return coin_info.close > coin_info.ema20 > coin_info.ema60 > coin_info.ema120
        else:
            return coin_info.close < coin_info.ema20 < coin_info.ema60 < coin_info.ema120


    def check_stochastic(self, user_info: UserOptionMeta, prev_info: UserCoinInfo, coin_info: UserCoinInfo) -> bool:
        """
        K < thredhold 상태에서 K가 D를 골든크로스 했는지 확인
        """
        k_lower_threshold = 30
        k_upper_threshold = 80

        is_golden_cross = (prev_info.fs_k < prev_info.fs_d) and \
                          (coin_info.fs_d < prev_info.fs_k)

        is_dead_cross = (prev_info.fs_k > prev_info.fs_d) and \
                        (coin_info.fs_d > coin_info.fs_k)

        if user_info.has_position:
            return coin_info.fs_k > k_upper_threshold or \
                   (is_dead_cross and prev_info.fs_k > k_upper_threshold)
        else:
            return coin_info.fs_k < k_lower_threshold or \
                   (is_golden_cross and prev_info.fs_k < k_lower_threshold)


    def check_rsi(self, user_info: UserOptionMeta, prev_info: UserCoinInfo, coin_info: UserCoinInfo):
        """
        RSI 과매도 상태에서 signal 과의 골든 크로스 발생 여부
        """

        rsi_lower_threshold = 37
        rsi_upper_threshold = 80

        is_golden_cross = (prev_info.rsi < prev_info.rsi_signal) and \
                          (coin_info.rsi_signal <= coin_info.rsi)

        is_dead_cross = (prev_info.rsi > prev_info.rsi_signal) and \
                        (coin_info.rsi_signal >= coin_info.rsi)

        if user_info.has_position:
            # 임계점 넘었거나, dead_cross 인데 이전 rsi가 임계점 넘었을 때
            return coin_info.rsi > rsi_upper_threshold or \
                   (is_dead_cross and prev_info.rsi > rsi_upper_threshold)
        else:
            return coin_info.rsi < rsi_lower_threshold or \
                   (is_golden_cross and prev_info.rsi < rsi_lower_threshold)


    def check_macd(self, user_info: UserOptionMeta, prev_info: UserCoinInfo, coin_info: UserCoinInfo):
        is_minus = coin_info.macd < 0

        if user_info.has_position: # 매도 타이밍 탐지
            is_upper_mean = coin_info.macd > coin_info.macd_upper_mean
            is_max = coin_info.macd_recent_max == prev_info.macd
            return not is_minus and is_max and is_upper_mean and (prev_info.macd - prev_info.macd_s) > (coin_info.macd - coin_info.macd_s)

        else:
            is_lower_mean = coin_info.macd < coin_info.macd_lower_mean
            is_min = coin_info.macd_recent_min == prev_info.macd

            return is_minus and is_min and is_lower_mean and (prev_info.macd_s - prev_info.macd) > (coin_info.macd_s - prev_info.macd)


    def check_obv(self, user_info: UserOptionMeta, prev_info: UserCoinInfo, coin_info: UserCoinInfo):
        percentage = 0.33 #(0 < x < 0.5)
        obv_min = coin_info.obv_recent_min
        obv_max = coin_info.obv_recent_max

        if user_info.has_position:
            first_quarter_line = percentage * obv_min + (1 - percentage) * obv_max
            return (coin_info.obv < obv_max) and (first_quarter_line < coin_info.obv)
        else:
            third_quarter_line = percentage * obv_max + (1 - percentage) * obv_min
            return (coin_info.obv > obv_min) and (third_quarter_line > coin_info.obv)