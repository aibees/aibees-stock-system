"""
user_role — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, String

from stock_shared.base import Base


class UserRole(Base):
    __tablename__ = "user_role"

    auth_id = Column(String(64), primary_key=True, nullable=False)
    auth_nm = Column(String(200), nullable=False)

    def to_dict(self):
        return {
            "auth_id": self.auth_id,
            "auth_nm": self.auth_nm,
        }
