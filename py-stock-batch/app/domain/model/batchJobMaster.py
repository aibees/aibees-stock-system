from sqlalchemy import Column, BigInteger, Integer, DateTime, String
from app.domain.model.base import Base

class BatchJobMaster(Base):
    __tablename__ = 'batch_job_master'
    
    job_id = Column(String(64), primary_key=True)
    job_name = Column(String(255), nullable=False)
    module_name = Column(String, nullable=False)
    class_name = Column(String, nullable=False)
    cron_minute = Column(String, nullable=False)
    cron_hour = Column(String, nullable=False)
    cron_day_of_week = Column(String, nullable=False)
    enabled_flag = Column(String, nullable=False)
    
    def to_dict(self):
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "module_name": self.module_name,
            "class_name": self.class_name,
            "cron_minute": self.cron_minute,
            "cron_hour": self.cron_hour,
            "cron_day_of_week": self.cron_day_of_week,
            "enabled_flag": self.enabled_flag
        }