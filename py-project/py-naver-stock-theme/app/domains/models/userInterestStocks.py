from sqlalchemy import Column, String, Integer, PrimaryKeyConstraint, DateTime
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserInterestStock(Base):
    __tablename__ = 'user_interest_stocks'

    group_id     = Column(Integer,       nullable=False)
    stock_code   = Column(String(45),    nullable=False)
    status       = Column(String(45),    nullable=False)
    added_at     = Column(DateTime,      nullable=True)
    enabled_flag = Column(String(1),     nullable=True)
    curr_balance = Column(DECIMAL(18,8), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('group_id', 'stock_code'),
    )

    def to_dict(self):
        return {
            'group_id':     self.group_id,
            'stock_code':   self.stock_code,
            'status':       self.status,
            'added_at':     self.added_at.strftime("%Y-%m-%d %H:%M:%S") if self.added_at else None,
            'enabled_flag': self.enabled_flag,
            'curr_balance': float(self.curr_balance) if self.curr_balance is not None else None,
        }