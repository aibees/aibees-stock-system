from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.batchJobMaster import BatchJobMaster

import logging
logging.basicConfig(level=logging.ERROR)


class BatchJobMasterDao(BaseDao):
    model = BatchJobMaster

    def __init__(self):
        self.__name__ = 'BatchJobMasterDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by job_id
    # ================================================================
    def select_by_job_id(self, session, job_id: str):
        stmt = select(BatchJobMaster).where(BatchJobMaster.job_id == job_id)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # select enabled jobs
    # ================================================================
    def select_enabled_jobs(self, session):
        stmt = select(BatchJobMaster).where(BatchJobMaster.enabled_flag == 'Y')
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # insert (신규 등록 전용 - 중복 시 별도 처리 필요)
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(BatchJobMaster).values(
            job_id=data['job_id'],
            job_name=data['job_name'],
            module_name=data['module_name'],
            class_name=data['class_name'],
            cron_minute=data['cron_minute'],
            cron_hour=data['cron_hour'],
            cron_day_of_week=data['cron_day_of_week'],
            enabled_flag=data['enabled_flag'],
        )
        session.execute(stmt)

    # upsert
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        stmt = insert(BatchJobMaster).values(
            job_id=data['job_id'],
            job_name=data['job_name'],
            module_name=data['module_name'],
            class_name=data['class_name'],
            cron_minute=data['cron_minute'],
            cron_hour=data['cron_hour'],
            cron_day_of_week=data['cron_day_of_week'],
            enabled_flag=data['enabled_flag'],
        )
        upsert_stmt = stmt.on_duplicate_key_update(
            job_name=data['job_name'],
            module_name=data['module_name'],
            class_name=data['class_name'],
            cron_minute=data['cron_minute'],
            cron_hour=data['cron_hour'],
            cron_day_of_week=data['cron_day_of_week'],
            enabled_flag=data['enabled_flag'],
        )
        session.execute(upsert_stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
