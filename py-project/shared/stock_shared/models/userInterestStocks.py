"""
user_interest_stocks — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class UserInterestStocks(Base):
    __tablename__ = "user_interest_stocks"

    __table_args__ = (PrimaryKeyConstraint("group_id", "stock_code"),)

    group_id = Column(Integer, nullable=False)
    stock_code = Column(String(45), nullable=False)
    status = Column(String(45), nullable=False)
    added_at = Column(DateTime, nullable=True)
    enabled_flag = Column(String(1), nullable=True)
    curr_balance = Column(DECIMAL(18, 8), nullable=True)

    def to_dict(self):
        return {
            "group_id": self.group_id,
            "stock_code": self.stock_code,
            "status": self.status,
            "added_at": self.added_at,
            "enabled_flag": self.enabled_flag,
            "curr_balance": self.curr_balance,
        }
