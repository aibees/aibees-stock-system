from sqlalchemy import Column, Integer, String, UniqueConstraint, DECIMAL, DateTime
from app.domain.model.base import Base

class UserWallet(Base):
    __tablename__ = 'user_wallet'

    user_id = Column(Integer, primary_key=True)
    user_balance = Column(DECIMAL(18, 8), nullable=False)           # 예수금(현금)
    stock_amount = Column(DECIMAL(18, 8), nullable=False, default=0)  # 보유주식 평가금액 합계
    total_asset  = Column(DECIMAL(18, 8), nullable=False, default=0)  # 총자산(예수금+보유주식평가)
    updated_at   = Column(DateTime)                                   # 마지막 동기화 시각

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'user_balance': float(self.user_balance) if self.user_balance is not None else 0.0,
            'stock_amount': float(self.stock_amount) if self.stock_amount is not None else 0.0,
            'total_asset': float(self.total_asset) if self.total_asset is not None else 0.0,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
