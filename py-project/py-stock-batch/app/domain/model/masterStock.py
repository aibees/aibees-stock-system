from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Index
from sqlalchemy.dialects.mysql import DECIMAL
from app.domain.model.base import Base

class MasterStock(Base):
    __tablename__ = 'master_stock'

    corp_code = Column(String, primary_key=True)
    stock_code = Column(String)
    stock_name = Column(String)
    stock_type = Column(String)
    stock_type_yf = Column(String)
    stock_class = Column(String)
    group_code = Column(String)
    market_stop = Column(String)
    nxt_flag = Column(String)
    created_date = Column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'corp_code': self.corp_code,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'stock_type': self.stock_type,
            'stock_type_yf': self.stock_type_yf,
            'stock_class': self.stock_class,
            'group_code': self.group_code,
            'market_stop': self.market_stop,
            'nxt_flag': self.nxt_flag,
            'created_date': self.created_date
        }