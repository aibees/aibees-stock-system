"""
AI 분석 작업 큐·구독자·알림함·재무 캐시 DAO (양봉상회 전용, sql/yangbong/008).

커밋은 호출자(서비스)가 한다. 여기서는 flush 까지만.
"""
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.mysql import insert

from app.domains.models.stockAiJob import (
    ACTIVE_STATUSES, STATUS_QUEUED, STATUS_RUNNING,
    StockAiJob, StockAiJobSubscriber, StockFinanceSnapshot, UserNotification,
)


class StockAiJobDao:

    # ── 조회 ──────────────────────────────────────────────────
    def get(self, session, job_id) -> StockAiJob | None:
        return session.get(StockAiJob, job_id)

    def find_active(self, session, stock_code, section) -> StockAiJob | None:
        stmt = select(StockAiJob).where(
            StockAiJob.stock_code == stock_code,
            StockAiJob.section == section,
            StockAiJob.status.in_(ACTIVE_STATUSES),
        )
        return session.execute(stmt).scalars().first()

    def is_subscribed(self, session, job_id, user_id) -> bool:
        stmt = select(func.count()).select_from(StockAiJobSubscriber).where(
            StockAiJobSubscriber.job_id == job_id, StockAiJobSubscriber.user_id == user_id)
        return bool(session.execute(stmt).scalar())

    def list_user_jobs(self, session, user_id, stock_code, since) -> list[StockAiJob]:
        """user 가 기다리는(구독한) stock_code 작업 중 since 이후 것. 최신 순."""
        stmt = (
            select(StockAiJob)
            .join(StockAiJobSubscriber, StockAiJobSubscriber.job_id == StockAiJob.job_id)
            .where(StockAiJobSubscriber.user_id == user_id,
                   StockAiJob.stock_code == stock_code,
                   StockAiJob.created_at >= since)
            .order_by(StockAiJob.job_id.desc())
        )
        return list(session.execute(stmt).scalars().all())

    def queue_position(self, session, job: StockAiJob) -> int | None:
        """대기 중이면 앞에 있는 작업 수 + 1(1 = 다음 차례), 아니면 None."""
        if job.status != STATUS_QUEUED:
            return None
        ahead = select(func.count()).select_from(StockAiJob).where(
            StockAiJob.status == STATUS_QUEUED,
            or_(StockAiJob.priority < job.priority,
                and_(StockAiJob.priority == job.priority, StockAiJob.job_id < job.job_id)),
        )
        return int(session.execute(ahead).scalar() or 0) + 1

    def subscriber_ids(self, session, job_id) -> list[int]:
        stmt = select(StockAiJobSubscriber.user_id).where(StockAiJobSubscriber.job_id == job_id)
        return [r[0] for r in session.execute(stmt).all()]

    # ── 쓰기 ──────────────────────────────────────────────────
    def insert_job(self, session, stock_code, section, priority, created_by, force, gen_log_id) -> StockAiJob:
        """active_key UNIQUE 에 걸리면 IntegrityError — 호출자가 기존 작업 구독으로 바꾼다."""
        job = StockAiJob(
            stock_code=stock_code, section=section, status=STATUS_QUEUED, priority=priority,
            created_by=created_by, force_flag='Y' if force else 'N', gen_log_id=gen_log_id,
            attempts=0, created_at=datetime.now(),
        )
        session.add(job)
        session.flush()
        return job

    def add_subscriber(self, session, job_id, user_id):
        stmt = insert(StockAiJobSubscriber).values(job_id=job_id, user_id=user_id, created_at=datetime.now())
        session.execute(stmt.prefix_with('IGNORE'))

    # ── 워커 ──────────────────────────────────────────────────
    def claim_next(self, session, limit: int) -> list[StockAiJob]:
        """대기 작업을 우선순위 순으로 limit 개 가져와 RUNNING 으로 바꾼다. 커밋은 호출자."""
        if limit <= 0:
            return []
        stmt = (
            select(StockAiJob)
            .where(StockAiJob.status == STATUS_QUEUED)
            .order_by(StockAiJob.priority, StockAiJob.job_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(session.execute(stmt).scalars().all())
        now = datetime.now()
        for job in jobs:
            job.status = STATUS_RUNNING
            job.started_at = now
            job.attempts = (job.attempts or 0) + 1
        session.flush()
        return jobs

    def finish(self, session, job_id, status, error_user=None, error_detail=None):
        session.execute(
            update(StockAiJob).where(StockAiJob.job_id == job_id).values(
                status=status, finished_at=datetime.now(),
                error_user=error_user, error_detail=error_detail,
            )
        )

    def stale_running(self, session, started_before) -> list[StockAiJob]:
        """started_before 이전에 시작해 아직 RUNNING 인 작업(워커가 죽었던 흔적)."""
        stmt = select(StockAiJob).where(
            StockAiJob.status == STATUS_RUNNING, StockAiJob.started_at < started_before)
        return list(session.execute(stmt).scalars().all())

    def requeue(self, session, job_id):
        session.execute(
            update(StockAiJob).where(StockAiJob.job_id == job_id).values(status=STATUS_QUEUED, started_at=None))


class UserNotificationDao:

    def insert(self, session, user_id, type_, title, body=None, link=None, ref_id=None):
        session.add(UserNotification(
            user_id=user_id, type=type_, title=title, body=body, link=link, ref_id=ref_id,
            created_at=datetime.now(),
        ))
        session.flush()

    def list(self, session, user_id, page: int, size: int) -> tuple[list[dict], int]:
        base = select(UserNotification).where(UserNotification.user_id == user_id)
        total = int(session.execute(select(func.count()).select_from(base.subquery())).scalar() or 0)
        rows = session.execute(
            base.order_by(UserNotification.notification_id.desc()).offset(page * size).limit(size)
        ).scalars().all()
        return [r.to_dict() for r in rows], total

    def count_unread(self, session, user_id) -> int:
        stmt = select(func.count()).select_from(UserNotification).where(
            UserNotification.user_id == user_id, UserNotification.read_at.is_(None))
        return int(session.execute(stmt).scalar() or 0)

    def mark_read(self, session, user_id, notification_id) -> int:
        res = session.execute(
            update(UserNotification)
            .where(UserNotification.notification_id == notification_id,
                   UserNotification.user_id == user_id,
                   UserNotification.read_at.is_(None))
            .values(read_at=datetime.now()))
        return res.rowcount

    def mark_all_read(self, session, user_id) -> int:
        res = session.execute(
            update(UserNotification)
            .where(UserNotification.user_id == user_id, UserNotification.read_at.is_(None))
            .values(read_at=datetime.now()))
        return res.rowcount

    def delete_older_than(self, session, before) -> int:
        res = session.execute(delete(UserNotification).where(UserNotification.created_at < before))
        return res.rowcount


class StockFinanceSnapshotDao:

    def get(self, session, stock_code) -> StockFinanceSnapshot | None:
        return session.get(StockFinanceSnapshot, stock_code)

    def upsert(self, session, stock_code, data: dict):
        now = datetime.now()
        stmt = insert(StockFinanceSnapshot).values(stock_code=stock_code, data=data, fetched_at=now)
        session.execute(stmt.on_duplicate_key_update(data=stmt.inserted.data, fetched_at=now))
