import logging

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.batchJobMaster import BatchJobMaster

logging.basicConfig(level=logging.ERROR)

_COLS = (
    "job_name",
    "module_name",
    "class_name",
    "cron_minute",
    "cron_hour",
    "cron_day_of_week",
    "enabled_flag",
)


class BatchJobMasterDao(BaseDao):
    model = BatchJobMaster

    def __init__(self):
        self.__name__ = "BatchJobMasterDao"

    # select all : BaseDao.select_all 사용
    # ================================================================

    # select by job_id
    # ================================================================
    def select_by_job_id(self, session, job_id: str):
        stmt = select(BatchJobMaster).where(BatchJobMaster.job_id == job_id)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # select enabled jobs
    # ================================================================
    def select_enabled_jobs(self, session):
        stmt = select(BatchJobMaster).where(BatchJobMaster.enabled_flag == "Y")
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # py-stock-batch 호환 별칭 (select_enabled_jobs 와 동일 동작)
    # ================================================================
    def select_batch_master_running(self, session):
        return self.select_enabled_jobs(session)

    # insert (신규 등록 전용 - 중복 시 별도 처리 필요)
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(BatchJobMaster).values(
            job_id=data["job_id"], **{c: data[c] for c in _COLS}
        )
        session.execute(stmt)

    # upsert
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        stmt = insert(BatchJobMaster).values(
            job_id=data["job_id"], **{c: data[c] for c in _COLS}
        )
        upsert_stmt = stmt.on_duplicate_key_update(**{c: data[c] for c in _COLS})
        session.execute(upsert_stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
