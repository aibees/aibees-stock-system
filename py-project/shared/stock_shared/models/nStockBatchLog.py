"""
stock_batch_log — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from stock_shared.base import Base


class NStockBatchLog(Base):
    __tablename__ = "stock_batch_log"

    batch_seq = Column(BigInteger, primary_key=True, nullable=False)
    batch_code = Column(String(100), nullable=False)
    batch_cnt = Column(Integer, nullable=True)
    status = Column(String(45), nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    desc = Column(String(256), nullable=True)

    def to_dict(self):
        return {
            "batch_seq": self.batch_seq,
            "batch_code": self.batch_code,
            "batch_cnt": self.batch_cnt,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "desc": self.desc,
        }
