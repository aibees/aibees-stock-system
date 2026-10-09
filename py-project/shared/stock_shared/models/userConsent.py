"""
user_consent — DB(stock) 스키마 기준 모델 (sql/28_user_consent.sql).
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, Integer, PrimaryKeyConstraint, String

from stock_shared.base import Base


class UserConsent(Base):
    __tablename__ = "user_consent"

    __table_args__ = (PrimaryKeyConstraint("user_id", "consent_type"),)

    user_id = Column(Integer, nullable=False)
    consent_type = Column(String(30), nullable=False)
    version = Column(String(20), nullable=False)
    agreed_date = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "consent_type": self.consent_type,
            "version": self.version,
            "agreed_date": self.agreed_date,
        }
