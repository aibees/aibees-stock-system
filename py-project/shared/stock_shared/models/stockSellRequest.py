"""
stock_sell_request — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, Integer, PrimaryKeyConstraint, String, func, text
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class StockSellRequest(Base):
    __tablename__ = "stock_sell_request"

    __table_args__ = (PrimaryKeyConstraint("user_id", "stock_code"),)

    user_id = Column(Integer, nullable=False)
    stock_code = Column(String(45), nullable=False)
    stock_name = Column(String(45), nullable=True)
    entry_date = Column(String(8), nullable=True)
    entry_price = Column(DECIMAL(18, 8), nullable=True)
    hold_qty = Column(DECIMAL(18, 8), nullable=True)
    memo = Column(String(255), nullable=True)
    enabled_flag = Column(String(1), nullable=False, server_default=text("Y"))
    created_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, server_default=func.now(), server_onupdate=func.now())

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "entry_date": self.entry_date,
            "entry_price": self.entry_price,
            "hold_qty": self.hold_qty,
            "memo": self.memo,
            "enabled_flag": self.enabled_flag,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
