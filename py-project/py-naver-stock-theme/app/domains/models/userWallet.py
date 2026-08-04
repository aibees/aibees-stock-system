from sqlalchemy import Column, Integer
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserWallet(Base):
    __tablename__ = 'user_wallet'

    user_id      = Column(Integer,       primary_key=True)
    user_balance = Column(DECIMAL(18,8), nullable=False)

    def to_dict(self):
        return {
            'user_id':      self.user_id,
            'user_balance': float(self.user_balance) if self.user_balance is not None else None,
        }
