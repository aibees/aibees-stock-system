from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserMaster(Base):
    __tablename__ = 'user_master'

    user_id = Column(Integer, primary_key=True)
    user_phone = Column(String(13), nullable=False)
    user_name = Column(String(45), nullable=False)
    email = Column(String(200), nullable=False)
    gender = Column(String(2), nullable=True)
    age = Column(String(45), nullable=True)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'user_phone': self.user_phone,
            'user_name': self.user_name,
            'email': self.email,
            'gender': self.gender,
            'age': self.age
        }
