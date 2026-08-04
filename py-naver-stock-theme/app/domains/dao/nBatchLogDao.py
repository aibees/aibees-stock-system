from app.domains.models.nStockBatchLog import NStockBatchLog
from app.domains.models.batchJobMaster import BatchJobMaster
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
from datetime import datetime
import logging

logging.basicConfig(level=logging.ERROR)

class BatchLogDao:
    def __init__(self):
        self.__name__ = 'BatchLogDao'
        
    # select
    # ================================================================
    def select_batch_log_list(self, session, param):
        stmt = select(
            NStockBatchLog,
            BatchJobMaster.job_name.label("batch_name")
        ).join(
            BatchJobMaster, NStockBatchLog.batch_code == BatchJobMaster.job_id
        ).where(
            and_(
                NStockBatchLog.start_time >= param['start_date'],
                NStockBatchLog.end_time <= param['end_date']
            )
        ).order_by(NStockBatchLog.start_time.desc())

        results = session.execute(stmt).mappings().all()

        return [
            {
                **row["NStockBatchLog"].to_dict(),
                "batch_name": row["batch_name"]
            }
            for row in results
        ]
            
    
    # select (pageable) - BatchLogSetting.vue
    # ================================================================
    def select_batch_log_page(self, session, page: int, size: int):
        stmt = (
            select(NStockBatchLog)
            .order_by(NStockBatchLog.batch_seq.desc())
            .offset(page * size)
            .limit(size)
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # count total rows
    # ================================================================
    def count_batch_log(self, session):
        stmt = select(func.count()).select_from(NStockBatchLog)
        return session.execute(stmt).scalar() or 0

    # next batch_seq (max + 1)
    # ================================================================
    def next_batch_seq(self, session):
        stmt = select(func.max(NStockBatchLog.batch_seq))
        max_seq = session.execute(stmt).scalar()
        return (max_seq or 0) + 1

    # insert
    # ================================================================
    def insert_batch_log(self, session, data):
        stmt = insert(
            NStockBatchLog
        ).values(
            batch_seq=data['batch_seq'],
            batch_code=data['batch_code'],
            batch_cnt=0,
            status='RUNNING',
            start_time=data['start_time'],
            end_time=None,
            desc=data['desc']
        )
        
        session.execute(stmt)
            
            
    # update
    # ================================================================
    def update_batch_log(self, session, data):
        
        stmt = update(
            NStockBatchLog
        ).where(
            NStockBatchLog.batch_seq == data['batch_seq']
        ).values(
            status=data['status'],
            desc=data['desc'],
            batch_cnt=data['batch_cnt'],
            end_time=data['end_time']
        )
        
        session.execute(stmt)