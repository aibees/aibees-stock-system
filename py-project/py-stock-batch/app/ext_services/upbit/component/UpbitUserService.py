from stock_shared.dao.userMasterDao import UserMasterDao
from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.domain.dto.userOptionMeta import UserOptionMeta


class UpbitUserService:
    def __init__(self):
        self.userMasterDaoImpl = UserMasterDao()
        pass

    ####################################################
    # get_target_user_info
    # - upbit 관리메일 대상 사용자 조회
    ####################################################
    def get_target_user_info(self, session):
        param = {
            'upbit_options': 'Y'
        }

        result = self.userMasterDaoImpl.select_user_upbit_options(session, param)

        # 사용자 정보 추출
        def extractor(x):
            user_meta = UserOptionMeta()
            user_meta.email = x['email']
            user_meta.user_name = x['user_name']
            user_meta.user_id = x['user_id']
            user_meta.access_key = x['upbit_access_key']
            user_meta.secret_key = x['upbit_secret_key']
            user_meta.time_frame = x['time_frame']
            user_meta.thresholds_buy_entry = x['buy_entry']
            user_meta.thresholds_buy_confirm = x['buy_confirm']
            user_meta.thresholds_sell_entry = x['sell_entry']
            user_meta.thresholds_sell_confirm = x['sell_exit']
            user_meta.ratio_trend = x['ratio_trend']
            user_meta.ratio_momentum = x['ratio_momentum']
            user_meta.ratio_volatility = x['ratio_volatility']
            user_meta.ratio_volume = x['ratio_volume']
            return user_meta

        def coin_extractor(x):
            coin_info = UserCoinInfo()
            coin_info.division = x['division']
            coin_info.group_id = x['group_id']
            coin_info.coin_code = x['stock_code']
            coin_info.status = x['status']
            coin_info.curr_balance = x['curr_balance']
            coin_info.enabled = x['enabled_flag']
            coin_info.added_at = x['added_at']
            return coin_info

        user_list = list(map(extractor, result))

        for meta in user_list:
            param = {
                'user_id': meta.user_id,
                'division': 'upbit'
            }

            # 사용자 별 관심코인 리스트 조회
            coin_result_list = self.userMasterDaoImpl.select_user_target_code(session, param)
            meta.coin_list = list(map(coin_extractor, coin_result_list))

        return user_list