"""
AI 분석 생성 요청 접수(양봉상회) — 요청은 stock_ai_job 에 쌓기만 하고, AI 워커(app.workers.ai_job_worker)가 처리한다.
설계: meetings/설계_2026-11-18_AI분석-비동기화.md · sql/yangbong/008

규칙
  - 같은 종목·섹션의 진행 중(QUEUED·RUNNING) 작업은 1건뿐이다(active_key UNIQUE).
    이미 있으면 새로 만들지 않고 구독자로만 붙인다 — AI 비용 1회, 하루 한도도 차감하지 않는다.
  - 새로 만드는 사람만 하루 한도를 차감한다(stock_ai_gen_log). 생성이 실패하면 워커가 환불한다.
  - 쿨다운(1시간)·실적발표월·한도는 접수할 때 바로 검사해서 즉시 거절한다(줄을 세운 뒤에 실패시키지 않는다).
  - 자동 작업(news 2시간 경과, finance 10분 경과)은 구독자 없이 넣는다(알림 없음). news 는 서버 전체 한도만 본다.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.domains.dao.stockAiJobDao import StockAiJobDao, StockFinanceSnapshotDao
from app.services.anthropic.stockAiContentService import (
    GenerationQuotaError,
    StockAiContentService,
)

logger = logging.getLogger(__name__)

# 사용자가 버튼으로 요청하는 섹션 / 자동으로만 넣는 섹션
USER_SECTIONS = ('overview', 'theme')
AUTO_SECTIONS = ('news', 'finance')
AI_SECTIONS = ('overview', 'theme', 'news')     # Anthropic 을 부르는(한도를 세는) 섹션
PRIORITY = {'overview': 1, 'theme': 1, 'finance': 3, 'news': 5}

FINANCE_TTL = timedelta(minutes=10)
MY_JOBS_WINDOW = timedelta(hours=24)


class AiJobService:

    def __init__(self, content_service: StockAiContentService | None = None):
        self._jobDao = StockAiJobDao()
        self._financeDao = StockFinanceSnapshotDao()
        self._content = content_service or StockAiContentService()

    # ── 버튼 요청 (overview·theme) ────────────────────────────
    def request(self, session, stock_code: str, section: str, user_id: int, is_admin: bool, force: bool) -> dict:
        """접수 결과 {job…, queue_position, joined}. 거절이면 AnnouncementMonthRequiredError·
        RefreshCooldownError·GenerationQuotaError 를 그대로 올린다."""
        if section not in USER_SECTIONS:
            raise ValueError(f"요청할 수 없는 섹션: {section}")

        existing = self._jobDao.find_active(session, stock_code, section)
        if existing:
            return self._join(session, existing, user_id)

        self._content.check_refresh_allowed(session, stock_code, section, is_admin, force)
        self._content.check_quota(session, user_id, is_admin)

        try:
            log_id = self._content.record_generation(session, stock_code, section, user_id)
            job = self._jobDao.insert_job(session, stock_code, section, PRIORITY[section], user_id, force, log_id)
            self._jobDao.add_subscriber(session, job.job_id, user_id)
            session.commit()
        except IntegrityError:
            # 같은 순간 다른 사람이 먼저 만들었다 → 차감 기록까지 롤백되고 그 작업에 붙는다.
            session.rollback()
            existing = self._jobDao.find_active(session, stock_code, section)
            if not existing:
                raise
            return self._join(session, existing, user_id)
        except Exception:
            session.rollback()
            raise
        return self.view(session, job, joined=False)

    def _join(self, session, job, user_id) -> dict:
        self._jobDao.add_subscriber(session, job.job_id, user_id)
        session.commit()
        return self.view(session, job, joined=True)

    # ── 자동 작업 (news·finance) ──────────────────────────────
    def enqueue_auto(self, session, stock_code: str, section: str) -> dict | None:
        """구독자 없는 작업. 이미 진행 중이면 그 작업을, 한도에 걸리면 None 을 돌려준다."""
        if section not in AUTO_SECTIONS:
            raise ValueError(f"자동으로 넣을 수 없는 섹션: {section}")
        existing = self._jobDao.find_active(session, stock_code, section)
        if existing:
            return self.view(session, existing)
        try:
            log_id = None
            if section in AI_SECTIONS:
                self._content.check_quota(session, None, False)
                log_id = self._content.record_generation(session, stock_code, section, None)
            job = self._jobDao.insert_job(session, stock_code, section, PRIORITY[section], None, False, log_id)
            session.commit()
            return self.view(session, job)
        except GenerationQuotaError as e:
            session.rollback()
            logger.info(f"[ai-job] {stock_code}/{section} 자동 작업 안 넣음: {e}")
            return None
        except IntegrityError:
            session.rollback()
            existing = self._jobDao.find_active(session, stock_code, section)
            return self.view(session, existing) if existing else None
        except Exception as e:  # noqa: BLE001 — 자동 작업은 실패해도 화면은 저장된 내용을 보여 준다
            session.rollback()
            logger.warning(f"[ai-job] {stock_code}/{section} 자동 작업 접수 실패: {e}")
            return None

    # ── 조회 ──────────────────────────────────────────────────
    def view(self, session, job, joined: bool | None = None) -> dict:
        out = job.to_dict()
        out["queue_position"] = self._jobDao.queue_position(session, job)
        if joined is not None:
            out["joined"] = joined
        return out

    def get_job(self, session, job_id: int) -> dict | None:
        job = self._jobDao.get(session, job_id)
        return self.view(session, job) if job else None

    def my_jobs(self, session, user_id: int, stock_code: str) -> list[dict]:
        """이 종목에서 내가 기다리는(24시간 안에 요청한) 작업. 섹션마다 가장 최근 1건."""
        seen, out = set(), []
        for job in self._jobDao.list_user_jobs(session, user_id, stock_code, datetime.now() - MY_JOBS_WINDOW):
            if job.section in seen:
                continue
            seen.add(job.section)
            out.append(self.view(session, job))
        return out

    # ── 재무 (API 서버는 KIS 를 부르지 않는다) ─────────────────
    def finance(self, session, stock_code: str) -> dict:
        """{data: 재무 지표|None, fetched_at, stale, job}. 없거나 오래됐으면 finance 작업을 넣는다."""
        snap = self._financeDao.get(session, stock_code)
        fresh = bool(snap) and (datetime.now() - snap.fetched_at) < FINANCE_TTL
        job = None if fresh else self.enqueue_auto(session, stock_code, 'finance')
        return {
            "data": snap.data if snap else None,
            "fetched_at": snap.fetched_at if snap else None,
            "stale": not fresh,
            "job": job,
        }

    def news(self, session, stock_code: str) -> dict:
        """{data: 저장된 뉴스 요약|None, stale, job}. 2시간 지났으면 news 작업을 넣는다."""
        cached = self._content.get_cached(session, stock_code, 'news')
        stale = self._content.news_is_stale(cached)
        job = self.enqueue_auto(session, stock_code, 'news') if stale else None
        return {"data": cached, "stale": stale, "job": job}

