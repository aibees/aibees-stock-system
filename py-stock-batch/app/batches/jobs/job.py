from abc import ABC, abstractmethod

from app.common.utils.commUtils import *
from app.config.database import dbConn
from app.domain.dao.batchLogDao import BatchLogDao

import logging
logging.basicConfig(level=logging.ERROR)

class Job(ABC):
    def __init__(self):
        # session은 process() 실행 시마다 새로 생성하여 세션 누수를 방지합니다.
        self.session = None
        self.batchLogDaoImpl = BatchLogDao()
        self.job_name = 'job'

    def process(self, **kwargs):
        print('=======  JOB  START =======')
        # ProcessPoolExecutor: fork로 물려받은 부모 커넥션 폐기
        # 이 줄이 없으면 부모-자식이 같은 TCP 소켓을 공유해 쿼리 오염 발생
        dbConn.engine.dispose()
        # dispose() 후 신규 커넥션으로 세션 생성
        self.session = dbConn.get_session()
        batch_seq = get_numeric_timestamp()

        insert_param = {
            'batch_seq': batch_seq,
            'batch_code': self.job_name,
            'start_time': get_numeric_timestamp(),
            'desc': f'배치시작 (Params: {kwargs})' if kwargs else '배치시작'
        }
        self.batchLogDaoImpl.insert_batch_log(self.session, insert_param)
        self.session.commit()

        try:
            print(f'======= BATCH START :: {batch_seq} =======')
            batch_result = self.run_batch(**kwargs)

            print('======= BATCH  END  =======')

            update_param = {
                'batch_seq': batch_seq,
                'status': batch_result.get('status', 'SUCCESS'),
                'desc': batch_result.get('desc', '정상 종료'),
                'batch_cnt': batch_result.get('batch_cnt', 0),
                'end_time': get_numeric_timestamp(),
            }

            self.batchLogDaoImpl.update_batch_log(self.session, update_param)
            self.session.commit()
            print('=======  JOB   END  =======')
        except Exception as e:
            print('=======  JOB  FAIL  =======')
            self.session.rollback()
            logging.exception(e)

            try:
                error_msg = f'배치 실패: {str(e)}'[:255]

                update_param = {
                    'batch_seq': batch_seq,
                    'status': 'FAIL',
                    'desc': error_msg,
                    'batch_cnt': 0,
                    'end_time': get_numeric_timestamp(),
                }
                self.batchLogDaoImpl.update_batch_log(self.session, update_param)
                self.session.commit()
            except Exception as log_e:
                print('======= LOG UPDATE FAIL =======')
                self.session.rollback()
                logging.exception(log_e)
        finally:
            # 성공/실패 여부와 무관하게 항상 세션을 닫아 커넥션 누수를 방지합니다.
            if self.session:
                self.session.remove()
                self.session = None

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def run_batch(self, **kwargs):
        pass
    