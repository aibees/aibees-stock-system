"""
master_stock — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, String, text

from stock_shared.base import Base


class MasterStock(Base):
    __tablename__ = "master_stock"

    corp_code = Column(String(20), primary_key=True, nullable=False)
    stock_code = Column(String(6), nullable=False)
    stock_name = Column(String(100), nullable=False)
    stock_type = Column(String(6), nullable=False)
    stock_type_yf = Column(String(45), nullable=True)
    stock_class = Column(String(1), nullable=True)
    group_code = Column(String(45), nullable=True)
    created_date = Column(DateTime, nullable=True)
    market_stop = Column(String(1), nullable=True)
    nxt_flag = Column(String(1), nullable=True, server_default=text("N"))

    def to_dict(self):
        return {
            "corp_code": self.corp_code,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "stock_type": self.stock_type,
            "stock_type_yf": self.stock_type_yf,
            "stock_class": self.stock_class,
            "group_code": self.group_code,
            "created_date": self.created_date,
            "market_stop": self.market_stop,
            "nxt_flag": self.nxt_flag,
        }
