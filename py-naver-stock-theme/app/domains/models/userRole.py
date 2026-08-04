from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserRole(Base):
    __tablename__ = 'user_role'

    auth_id = Column(String(64), primary_key=True)
    auth_nm = Column(String(200), nullable=False)

    def to_dict(self):
        return {
            'auth_id': self.auth_id,
            'auth_nm': self.auth_nm
        }
