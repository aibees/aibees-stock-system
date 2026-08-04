"""
batch_job_master — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, String

from stock_shared.base import Base


class BatchJobMaster(Base):
    __tablename__ = "batch_job_master"

    job_id = Column(String(64), primary_key=True, nullable=False)
    job_name = Column(String(255), nullable=False)
    module_name = Column(String(255), nullable=False)
    class_name = Column(String(45), nullable=False)
    cron_minute = Column(String(45), nullable=False)
    cron_hour = Column(String(45), nullable=False)
    cron_day_of_week = Column(String(45), nullable=False)
    enabled_flag = Column(String(1), nullable=False)

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "module_name": self.module_name,
            "class_name": self.class_name,
            "cron_minute": self.cron_minute,
            "cron_hour": self.cron_hour,
            "cron_day_of_week": self.cron_day_of_week,
            "enabled_flag": self.enabled_flag,
        }
