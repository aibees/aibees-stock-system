"""
user_login_type — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, Integer, PrimaryKeyConstraint, String, text

from stock_shared.base import Base


class UserLoginType(Base):
    __tablename__ = "user_login_type"

    __table_args__ = (PrimaryKeyConstraint("user_id", "login_type"),)

    user_id = Column(Integer, nullable=False)
    login_type = Column(String(45), nullable=False)
    enabled_flag = Column(String(1), nullable=False, server_default=text("Y"))

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "login_type": self.login_type,
            "enabled_flag": self.enabled_flag,
        }
