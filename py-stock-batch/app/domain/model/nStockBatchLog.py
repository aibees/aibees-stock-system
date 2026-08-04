from sqlalchemy import Column, BigInteger, Integer, DateTime, String
from app.domain.model.base import Base

class NStockBatchLog(Base):
    __tablename__ = 'stock_batch_log'

    batch_seq = Column(BigInteger, primary_key=True)
    batch_code = Column(String(100), nullable=False)
    batch_cnt = Column(Integer, nullable=True)
    status = Column(String(45), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    desc = Column(String(256), nullable=True)
    
    def to_dict(self):
        return {
            'batch_seq': self.batch_seq,
            'batch_code': self.batch_code,
            'batch_cnt': self.batch_cnt,
            'status': self.status,
            'start_time': self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else None,
            'end_time': self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            'desc': self.desc,
        }