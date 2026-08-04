import importlib
import threading
from concurrent.futures import ProcessPoolExecutor

from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone

from app.config.contextManager import get_session
from app.domain.dao.batchJobMasterDao import BatchJobMasterDao


# ──────────────────────────────────────────────────────────────
#  module-level wrapper — ProcessPoolExecutor가 pickle하는 대상
#
#  클래스 메서드(bound method)를 직접 등록하면 인스턴스 전체를
#  pickle해야 하는데, KisEngine(PyKis 세션)·ThreadPoolExecutor
#  등 직렬화 불가 객체가 포함되어 PicklingError가 발생한다.
#
#  module-level 함수는 "모듈 경로 + 함수명" 만으로 직렬화되므로
#  내부 상태를 전혀 pickle하지 않아 문제가 없다.
#
#  또한 자식 프로세스 진입 직후 engine.dispose()를 호출하여
#  fork로 복사된 부모 프로세스의 커넥션 풀을 폐기한다.
#  (dispose() 없이 사용하면 부모-자식이 같은 소켓 FD를 공유해
#   쿼리 결과 오염 또는 SSL 오류가 발생할 수 있다.)
# ──────────────────────────────────────────────────────────────
def _execute_job(module_name: str, class_name: str, **kwargs):
    from app.config.database import dbConn
    dbConn.engine.dispose()

    jobModule = importlib.import_module(module_name)
    jobClass  = getattr(jobModule, class_name)
    jobClass().process(**kwargs)


# ──────────────────────────────────────────────────────────────
#  수동 실행(/once) 전용 ProcessPoolExecutor.
#
#  기존엔 job 을 gunicorn worker 프로세스 안 daemon Thread 로 돌렸는데,
#  batch 의 CPU-bound 구간이 GIL 을 오래 잡으면 worker 의 heartbeat 가
#  끊겨 gunicorn arbiter 가 WORKER TIMEOUT 으로 worker 를 죽였다
#  (그러면 job Thread 도 daemon 이라 같이 죽음).
#  → 스케줄러 자동실행과 동일하게 '별도 프로세스'에서 실행해
#    web worker 를 블로킹하지 않는다. _execute_job 은 pickle 안전.
# ──────────────────────────────────────────────────────────────
_manual_executor = None
_manual_lock = threading.Lock()


def run_job_once(module_name: str, class_name: str, **kwargs):
    """수동(/once) batch 실행을 web worker 밖 별도 프로세스로 submit(비블로킹).
    반환: concurrent.futures.Future (호출측은 대기하지 않음)."""
    global _manual_executor
    with _manual_lock:
        if _manual_executor is None:
            _manual_executor = ProcessPoolExecutor(max_workers=2)
    return _manual_executor.submit(_execute_job, module_name, class_name, **kwargs)


class StockScheduler:
    def __init__(self):
        self.batchJobMasterDaoImpl = BatchJobMasterDao()
        self.scheduler = BackgroundScheduler(
            executors={
                'default': {'type': 'processpool', 'max_workers': 4}
            },
            job_defaults={
                'max_instances': 1,       # 같은 Job 중복 실행 방지
                'misfire_grace_time': 60  # 놓친 실행은 60초 이내만 보정
            }
        )
        self.load_jobs()

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def pause_job(self, job_id):
        self.scheduler.pause_job(job_id)

    def resume_job(self, job_id):
        self.scheduler.resume_job(job_id)

    def load_jobs(self):
        print("APScheduler Job Load....")
        self.scheduler.remove_all_jobs()

        with get_session() as session:
            job_list = self.batchJobMasterDaoImpl.select_batch_master_running(session)
            for job in job_list:
                try:
                    # 부모 프로세스에서는 인스턴스를 생성하지 않는다.
                    # jobInstance를 만들어 bound method를 등록하면
                    # 스케줄 트리거 시점에 인스턴스 전체를 pickle하려다 실패한다.
                    # DB의 job_name 컬럼으로 등록 로그를 남기고,
                    # 실제 인스턴스 생성은 _execute_job 안(자식 프로세스)에서 수행한다.
                    print("JOB REGISTERED :", job['job_name'])

                    trigger = CronTrigger(
                        day_of_week=job['cron_day_of_week'],
                        hour=job['cron_hour'],
                        minute=job['cron_minute'],
                        timezone=timezone('Asia/Seoul')
                    )

                    self.scheduler.add_job(
                        _execute_job,
                        trigger=trigger,
                        id=job['job_id'],
                        name=job['job_name'],
                        args=[job['module_name'], job['class_name']]
                    )
                except Exception as e:
                    print(f"Job 등록 실패 [{job.get('job_id')}]: {e}")


scheduleManage = StockScheduler()
