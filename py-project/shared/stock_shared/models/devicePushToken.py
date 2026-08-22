"""
device_push_token — 푸시 알림 대상 디바이스 토큰(FCM).
※ sql/10_notification_device_token_ddl.sql 과 짝을 이룬다. 스키마 변경 시
   함께 갱신할 것.
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from stock_shared.base import Base


class DevicePushToken(Base):
    __tablename__ = "device_push_token"

    token_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True)
    device_token = Column(String(255), nullable=False)
    platform = Column(String(10), nullable=False)
    user_id = Column(Integer, nullable=True)
    roles = Column(String(200), nullable=True)
    enabled_flag = Column(String(1), nullable=False, default="Y")
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            "token_id": self.token_id,
            "device_token": self.device_token,
            "platform": self.platform,
            "user_id": self.user_id,
            "roles": self.roles,
            "enabled_flag": self.enabled_flag,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
