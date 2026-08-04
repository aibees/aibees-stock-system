"""
user_interest_groups — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, Integer, PrimaryKeyConstraint, String

from stock_shared.base import Base


class UserInterestGroups(Base):
    __tablename__ = "user_interest_groups"

    __table_args__ = (PrimaryKeyConstraint("division", "group_id", "user_id"),)

    division = Column(String(45), nullable=False)
    group_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    group_name = Column(String(45), nullable=False)

    def to_dict(self):
        return {
            "division": self.division,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "group_name": self.group_name,
        }
