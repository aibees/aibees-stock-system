from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserLoginType(Base):
    __tablename__ = 'user_login_type'

    user_id = Column(Integer, primary_key=True)
    login_type = Column(String(45), nullable=False)
    enabled_flag = Column(String(1), nullable=False)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'login_type': self.login_type,
            'enabled_flag': self.enabled_flag,
        }
