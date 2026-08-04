from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserAuth(Base):
    __tablename__ = 'user_auth'

    user_id = Column(Integer, primary_key=True)
    auth_id = Column(String(64), nullable=False)
    enabled_flag = Column(String(1), nullable=False)
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'auth_id': self.auth_id,
            'enabled_flag': self.enabled_flag,
            'created_date': self.created_date,
            'updated_date': self.updated_date
        }
