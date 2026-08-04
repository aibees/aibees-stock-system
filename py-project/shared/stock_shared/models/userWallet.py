"""
user_wallet — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, Integer, text
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class UserWallet(Base):
    __tablename__ = "user_wallet"

    user_id = Column(Integer, primary_key=True, nullable=False)
    user_balance = Column(DECIMAL(18, 8), nullable=False)
    stock_amount = Column(DECIMAL(18, 8), nullable=False, server_default=text("0.00000000"))
    total_asset = Column(DECIMAL(18, 8), nullable=False, server_default=text("0.00000000"))
    updated_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "user_balance": self.user_balance,
            "stock_amount": self.stock_amount,
            "total_asset": self.total_asset,
            "updated_at": self.updated_at,
        }
