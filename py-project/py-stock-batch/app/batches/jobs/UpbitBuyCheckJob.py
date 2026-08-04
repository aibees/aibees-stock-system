from app.batches.jobs.job import Job
from stock_shared.dao.userMasterDao import UserMasterDao
from app.domain.dao.userTestDao import UserTestDao
from app.domain.dto.userOptionMeta import UserOptionMeta
from app.ext_services.upbit.component.UpbitService import UpbitService
from app.ext_services.upbit.UpbitCcxt import CcxtUpbit

from concurrent.futures import ThreadPoolExecutor
import pprint, traceback


class UpbitCurrCheckJob(Job):
    def __init__(self):
        super().__init__()
        self.job_name = 'UpbitCurrCheckJob'
        self.userTestDaoImpl = UserTestDao()
        self.userMasterDaoImpl = UserMasterDao()
        self.upbitServiceImpl = UpbitService()
        self.executor = ThreadPoolExecutor(max_workers=5)

    def get_name(self):
        return self.job_name

    ####################################################
    # 배치 시작
    ####################################################
    def run_batch(self, **kwargs):
        # 배치 실행대상 사용자 
        user_info_list = self.upbitServiceImpl.get_target_user_info(self.session)

        for user_info in user_info_list:
            try:
                # threading 등록
                # TODO : custom threading 으로 전역 Thread Executor 만들고 queueing 까지
                f = self.executor.submit(self.works, user_info)
                pprint.pprint(f.result())
            except Exception as e:
                pprint.pprint(e)


    ####################################################
    # threading 실행에 들어가는 메인 def
    ####################################################
    def works(self, user_info: UserOptionMeta):
        try:
            # upbit 접속
            upbit = CcxtUpbit(user_info.access_key, user_info.secret_key)

            for coin in user_info.coin_list:
                # 기술적 지표 계산
                ohlcv = upbit.getOHLCV(coin.coin_code, user_info.time_frame)
                self.upbitServiceImpl.compute_indicator_df(ohlcv, coin)

                coin.score = 0.0

            # 2. balance
            # favorite list외 잔액 등록된게 있다면(내가 직접 어플에서 매수하면 자동등록) 
            # balance_info = upbit.getCurrentWallet()['info']
            # 일단 여기는 DB에서 원화 조회
            # 운영에서는 upbit조회
            wallet_param = {
                'user_id': user_info.user_id,
            }
            user_wallet = self.userTestDaoImpl.select_user_test_wallet(self.session, wallet_param)
            user_info.krw_balance = user_wallet['user_balance']

            for coin in user_info.coin_list:
                print("code : " + str(coin.coin_code))
                # 코인 별로 행동 판단 후 처리
                # TODO: 실제 매매 판단 로직을 구현해야 합니다.
                result = {}

                if not result.get('result', False):
                    print("false")

                else:
                    update_stock_param = {
                        'user_id': user_info.user_id,
                        'coin_code': coin.coin_code,
                        'division': coin.division,
                        'status': result['info']['status'],
                        'curr_balance': coin.curr_balance + result['info']['bought_amount'],
                    }
                    self.userTestDaoImpl.update_user_interest_stocks(self.session, update_stock_param)

                    update_wallet_param = {
                        'user_id': user_info.user_id,
                        'user_balance': user_info.krw_balance - result['info']['used_balance'],
                    }
                    self.userTestDaoImpl.update_user_wallet(self.session, update_wallet_param)

            return "work done"
        except Exception as e:
            traceback.print_exc()