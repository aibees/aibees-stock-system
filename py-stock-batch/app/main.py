import sys
import time

from app.flask_app.runner import FlaskApp
# ── 개발/백테스트 전용 모듈 — 운영 빌드에서는 임포트하지 않는다 ──────────────
# (호출부는 아래 process()에서 이미 주석 처리됨. 백테스트(KisBacktester)가 운영
#  프로세스에 딸려 들어오지 않도록 임포트도 차단. 개발 시에만 주석 해제해 사용)
# from app.test.test_1 import test as test_1
from app.test.test_5 import test_backtest_insert_one as test_5
from app.test.test_7 import test as test_7
from app.test.test_backtest import run   # ← KisBacktester 의존 (백테스트 러너)
# Flask 인스턴스를 외부에서 가져다 쓸 수 있도록 정의
flaskApp = FlaskApp(None).get_app()

def process(args):
    # if args[1] == 'job_test':
    #     test_7()
    # print(args)
    # if args[1] == 'test' and args[3] == 'acc':
    #     test_5(args[2], '2026-06-19')
    #     time.sleep(2)
    #     test_5(args[2], '2026-04-07')
    #     time.sleep(2)
    #     test_5(args[2], '2026-01-28')
    #     time.sleep(2)
    #     test_5(args[2], '2025-11-15')
    #     time.sleep(2)
    #     test_5(args[2], '2025-08-30')
    #     time.sleep(2)
    #     test_5(args[2], '2025-06-25')
    #
    # if args[1] == 'test' and args[3] == 'back':
    #     print(args)
    #     run(args[2], start_date='2025-04-19')
    flaskApp.run(host="0.0.0.0", port=5557, threaded=True)

if __name__ == "__main__":
    process(sys.argv)