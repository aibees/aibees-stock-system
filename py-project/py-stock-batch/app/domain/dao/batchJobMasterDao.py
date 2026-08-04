from app.domain.model.batchJobMaster import BatchJobMaster
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
import logging

logging.basicConfig(level=logging.ERROR)

class BatchJobMasterDao:
    def __init__(self):
        self.__name__ = 'BatchJobMasterDao'
        
    # select
    # ================================================================
    def select_batch_master_running(self, session):
        stmt = select(
            BatchJobMaster
        ).where(
            BatchJobMaster.enabled_flag == 'Y'
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]