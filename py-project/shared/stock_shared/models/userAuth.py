"""
user_auth — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, Integer, PrimaryKeyConstraint, String, text

from stock_shared.base import Base


class UserAuth(Base):
    __tablename__ = "user_auth"

    __table_args__ = (PrimaryKeyConstraint("user_id", "auth_id"),)

    user_id = Column(Integer, nullable=False)
    auth_id = Column(String(64), nullable=False)
    enabled_flag = Column(String(1), nullable=False, server_default=text("Y"))
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "auth_id": self.auth_id,
            "enabled_flag": self.enabled_flag,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
        }
