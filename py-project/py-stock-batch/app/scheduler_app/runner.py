from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ProcessPoolExecutor as APProcessPoolExecutor
from pytz import timezone

from app.config.contextManager import get_session
from app.scheduler_app.job_runner import MP_CONTEXT, _execute_job, run_job_once  # noqa: F401
from stock_shared.dao.batchJobMasterDao import BatchJobMasterDao

# ──────────────────────────────────────────────────────────────
#  주의 — 이 모듈은 맨 아래에서 `scheduleManage = StockScheduler()` 를
#  실행한다. 즉 **import 만 해도 DB 붙고 스케줄러가 선다.**
#
#  그래서 자식 프로세스가 실행할 함수(_execute_job)를 여기 두면 안 된다.
#  자식은 그 함수를 되살리려고 이 모듈을 재import 하고, 그 순간
#  스케줄러를 통째로 다시 세우기 때문이다. → job_runner.py 로 분리했다.
#  (run_job_once / _execute_job 은 기존 import 경로 호환을 위해 re-export)
# ──────────────────────────────────────────────────────────────


class StockScheduler:
    def __init__(self):
        self.batchJobMasterDaoImpl = BatchJobMasterDao()
        self.scheduler = BackgroundScheduler(
            # dict 설정({'type':'processpool'})으로는 mp_context 를 못 넘긴다.
            # 수동실행(/once) 풀과 동일한 spawn 컨텍스트를 쓰도록 객체로 준다.
            # → 자동/수동 두 경로의 프로세스 생성 방식을 하나로 통일.
            executors={
                'default': APProcessPoolExecutor(
                    max_workers=4,
                    pool_kwargs={'mp_context': MP_CONTEXT},
                )
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
