from sqlalchemy import Column, Integer, String, DateTime, PrimaryKeyConstraint, DECIMAL
from app.domain.model.base import Base

class UserInterestStocks(Base):
    __tablename__ = 'user_interest_stocks'

    group_id = Column(Integer, nullable=False)
    stock_code = Column(String(45), nullable=False)
    enabled_flag = Column(String(1), nullable=False)
    status = Column(String(45), nullable=False)
    curr_balance = Column(DECIMAL(18, 8), nullable=False)
    added_at = Column(DateTime)

    __table_args__ = (
        PrimaryKeyConstraint('group_id', 'stock_code'),
    )

    def to_dict(self):
        return {
            "group_id": self.group_id,
            "stock_code": self.stock_code,
            "status": self.status,
            "enabled_flag": self.enabled_flag,
            "curr_balance": self.curr_balance or 0.0,
            "added_at": self.added_at.isoformat() if self.added_at else None,
        }
