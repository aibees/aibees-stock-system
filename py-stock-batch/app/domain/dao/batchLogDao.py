from app.domain.model.nStockBatchLog import NStockBatchLog
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
from datetime import datetime
import logging

logging.basicConfig(level=logging.ERROR)

class BatchLogDao:
    def __init__(self):
        self.__name__ = 'BatchLogDao'
        
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