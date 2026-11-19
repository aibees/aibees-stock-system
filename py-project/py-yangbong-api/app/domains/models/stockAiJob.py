"""
AI 분석 생성 비동기화 — 작업 큐·구독자·알림함·재무 캐시 (양봉상회 전용).
sql: yangbong/008_ai_job_notification.sql · 설계: meetings/설계_2026-11-18_AI분석-비동기화.md
"""
from sqlalchemy import JSON, BigInteger, Column, Computed, DateTime, Integer, SmallInteger, String, Text

from stock_shared.base import Base

STATUS_QUEUED = 'QUEUED'
STATUS_RUNNING = 'RUNNING'
STATUS_DONE = 'DONE'
STATUS_FAILED = 'FAILED'
ACTIVE_STATUSES = (STATUS_QUEUED, STATUS_RUNNING)


class StockAiJob(Base):
    __tablename__ = 'stock_ai_job'

    job_id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    section = Column(String(20), nullable=False)          # overview | theme | news | finance
    status = Column(String(10), nullable=False, default=STATUS_QUEUED)
    priority = Column(SmallInteger, nullable=False, default=5)
    created_by = Column(Integer)
    force_flag = Column(String(1), nullable=False, default='N')
    gen_log_id = Column(BigInteger)
    attempts = Column(SmallInteger, nullable=False, default=0)
    error_user = Column(String(255))
    error_detail = Column(Text)
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    # DB 가 계산하는 열(진행 중일 때만 'code:section'). INSERT·UPDATE 에 넣지 않는다.
    active_key = Column(String(40), Computed(
        "IF(status IN ('QUEUED', 'RUNNING'), CONCAT(stock_code, ':', section), NULL)", persisted=True))

    def to_dict(self):
        """API 로 내보내는 모양. error_detail(원문)은 넣지 않는다."""
        return {
            "job_id": self.job_id,
            "stock_code": self.stock_code,
            "section": self.section,
            "status": self.status,
            "error_message": self.error_user,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class StockAiJobSubscriber(Base):
    __tablename__ = 'stock_ai_job_subscriber'

    job_id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False)


class UserNotification(Base):
    __tablename__ = 'user_notification'

    notification_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    type = Column(String(20), nullable=False)             # AI_DONE | AI_FAILED
    title = Column(String(100), nullable=False)
    body = Column(String(255))
    link = Column(String(255))
    ref_id = Column(BigInteger)
    created_at = Column(DateTime, nullable=False)
    read_at = Column(DateTime)

    def to_dict(self):
        return {
            "notification_id": self.notification_id,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "link": self.link,
            "ref_id": self.ref_id,
            "created_at": self.created_at,
            "read_at": self.read_at,
        }


class StockFinanceSnapshot(Base):
    __tablename__ = 'stock_finance_snapshot'

    stock_code = Column(String(20), primary_key=True)
    data = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, nullable=False)
