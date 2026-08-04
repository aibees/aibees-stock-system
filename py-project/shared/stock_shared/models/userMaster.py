"""
user_master — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, Integer, String

from stock_shared.base import Base


class UserMaster(Base):
    __tablename__ = "user_master"

    user_id = Column(Integer, primary_key=True, nullable=False)
    user_name = Column(String(45), nullable=False)
    user_phone = Column(String(13), nullable=True)
    email = Column(String(200), nullable=True)
    gender = Column(String(2), nullable=True)
    age = Column(String(45), nullable=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_phone": self.user_phone,
            "email": self.email,
            "gender": self.gender,
            "age": self.age,
        }
