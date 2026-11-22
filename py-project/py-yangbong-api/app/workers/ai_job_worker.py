"""
양봉 AI 워커 — stock_ai_job 큐를 꺼내 AI 분석·재무 지표를 만들고, 기다리던 사람에게 알린다.
설계: meetings/설계_2026-11-18_AI분석-비동기화.md · sql/yangbong/008

실행:  python -m app.workers.ai_job_worker        (py-yangbong-api/docker-compose.yml 의 ai-worker 서비스)

왜 프로세스 1개인가
  KIS 는 토큰 발급을 1분 1회로 제한한다(EGW00133). API 서버(gunicorn 워커 4개)가 각자 토큰을 받으면
  만료 직전마다 서로 부딪힌다. KIS 를 부르는 곳을 이 프로세스 하나로 모으면 PyKis·토큰도 하나다.
  그래도 같은 앱키를 쓰는 다른 서비스와 부딪힐 수 있어, EGW00133 이면 61초 쉬고 한 번 더 한다.

동작
  - 우선순위(사용자 요청 1 > 재무 3 > 뉴스 자동 5) 순으로 동시 실행 수만큼 가져와 RUNNING 으로 바꾼다.
    동시 실행 수: 공통코드 stock/setting/ai 의 AI_WORKER_CONCURRENCY → 환경변수 → 기본 3 (1분마다 다시 읽는다).
  - 성공: 저장 → DONE → 구독자에게 알림함 + 푸시(AI_DONE).
  - 실패: 하루 한도 환불 → FAILED(error_user=사용자용 문구, error_detail=원문) → 구독자에게 AI_FAILED.
  - 시작할 때와 5분마다, 10분 넘게 RUNNING 인 작업(워커가 죽었던 흔적)은 attempts < 2 면 다시 줄 세우고 아니면 실패 처리.
  - SIGTERM: 새 작업을 더 가져오지 않고, 돌던 작업이 끝나길 최대 STOP_GRACE_SECONDS 기다린다.

DB 연결: 양봉 계정은 MAX_USER_CONNECTIONS 15 이고 API 가 최대 12 를 쓴다. AI 호출(수십 초) 동안에는
  연결을 쥐고 있지 않도록 호출 전에 트랜잭션을 끝낸다(StockAiContentService.generate_now 참고).
"""
import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlencode

log = logging.getLogger("ai_worker")

POLL_SECONDS = 2
CONCURRENCY_REFRESH_SECONDS = 60
RECOVER_EVERY_SECONDS = 300
DAILY_ISSUE_CHECK_SECONDS = 60     # 오늘의 경제 이슈: 1분마다 만들 차례인지 본다(daily_issue_service.run_due)
STALE_AFTER = timedelta(minutes=10)
MAX_ATTEMPTS = 2
MAX_CONCURRENCY = 8                 # 공통코드에 큰 값을 넣어도 이 이상은 돌리지 않는다
DEFAULT_CONCURRENCY = 3
STOP_GRACE_SECONDS = 150
KIS_TOKEN_WAIT_SECONDS = 61

SECTION_LABEL = {'overview': '기업 개요', 'theme': '현재 테마', 'news': '최근 뉴스', 'finance': '재무 지표'}
FAIL_MESSAGE = {
    'finance': '재무 지표를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
}
DEFAULT_FAIL_MESSAGE = 'AI 분석을 만들지 못했어요. 잠시 후 다시 시도해 주세요.'


def _setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s", force=True)


def _is_kis_token_limit(e: Exception) -> bool:
    return 'EGW00133' in str(e)


class AiJobWorker:

    def __init__(self):
        # 무거운 import(pykis·anthropic·DB 엔진)는 여기서 — 모듈 import 만으로 DB 에 붙지 않게.
        from web_shared.dao.masterCodesDao import MasterCodesDao
        from app.domains.dao.stockAiJobDao import StockAiJobDao, StockFinanceSnapshotDao
        from app.services.anthropic.content import yangbong_content_service
        from app.services.common.notificationService import NotificationService
        from stock_shared.dao.masterStockDao import MasterStockDao
        from stock_shared.db.database import dbConn

        self._db = dbConn
        self._jobDao = StockAiJobDao()
        self._financeDao = StockFinanceSnapshotDao()
        self._codesDao = MasterCodesDao()
        self._stockDao = MasterStockDao()
        self._content = yangbong_content_service()
        self._notify = NotificationService()

        self._kis = None
        self._kis_lock = threading.Lock()
        self._stop = threading.Event()
        self._running: dict = {}            # job_id → Future
        self._concurrency = DEFAULT_CONCURRENCY
        self._concurrency_read_at = 0.0
        self._recovered_at = 0.0
        self._issue_checked_at = 0.0
        self._issue_future = None

    # ── KIS (프로세스당 1개) ───────────────────────────────────
    @property
    def kis(self):
        with self._kis_lock:
            if self._kis is None:
                from web_shared.ext_services.kis.KisEngine import KisEngine
                self._kis = KisEngine(virtual=False)
            return self._kis

    def _with_kis_retry(self, fn):
        """EGW00133(토큰 발급 1분 1회)이면 61초 쉬고 한 번 더."""
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if not _is_kis_token_limit(e) or self._stop.is_set():
                raise
            log.warning(f"KIS 토큰 발급 제한(EGW00133) — {KIS_TOKEN_WAIT_SECONDS}초 뒤 재시도")
            time.sleep(KIS_TOKEN_WAIT_SECONDS)
            return fn()

    # ── 설정 ──────────────────────────────────────────────────
    def _read_concurrency(self):
        if time.monotonic() - self._concurrency_read_at < CONCURRENCY_REFRESH_SECONDS:
            return self._concurrency
        self._concurrency_read_at = time.monotonic()
        raw = None
        session = self._db.get_session()
        try:
            rows = self._codesDao.select_master_code(
                session, {'system': 'stock', 'source': 'setting', 'category': 'ai'})
            raw = next((r['desc'] for r in rows if r['code'] == 'AI_WORKER_CONCURRENCY'), None)
            session.commit()
        except Exception as e:  # noqa: BLE001
            session.rollback()
            log.warning(f"공통코드 AI_WORKER_CONCURRENCY 조회 실패 — 이전 값 유지: {e}")
        finally:
            session.remove()
        raw = raw if raw not in (None, '') else os.environ.get('AI_WORKER_CONCURRENCY')
        try:
            value = int(str(raw).strip()) if raw not in (None, '') else DEFAULT_CONCURRENCY
        except ValueError:
            log.warning(f"AI_WORKER_CONCURRENCY={raw!r} 숫자가 아님 — 기본 {DEFAULT_CONCURRENCY}")
            value = DEFAULT_CONCURRENCY
        value = max(1, min(MAX_CONCURRENCY, value))
        if value != self._concurrency:
            log.info(f"동시 실행 수 {self._concurrency} → {value}")
        self._concurrency = value
        return value

    # ── 복구 ──────────────────────────────────────────────────
    def _recover_stale(self):
        self._recovered_at = time.monotonic()
        session = self._db.get_session()
        failed = []
        try:
            for job in self._jobDao.stale_running(session, datetime.now() - STALE_AFTER):
                if job.job_id in self._running:
                    continue   # 이 프로세스가 아직 돌리는 중(오래 걸리는 것뿐)
                if (job.attempts or 0) < MAX_ATTEMPTS:
                    log.warning(f"job {job.job_id} RUNNING 이 오래됨 → 다시 줄 세움")
                    self._jobDao.requeue(session, job.job_id)
                else:
                    log.warning(f"job {job.job_id} RUNNING 이 오래됨, 재시도 다 씀 → 실패 처리")
                    failed.append((job.job_id, job.stock_code, job.section, job.gen_log_id))
            session.commit()
        except Exception as e:  # noqa: BLE001
            session.rollback()
            log.error(f"오래된 작업 복구 실패: {e}")
        finally:
            session.remove()
        for job_id, code, section, gen_log_id in failed:
            self._fail(job_id, code, section, gen_log_id, RuntimeError("워커가 처리 도중 멈춤(시간 초과)"))

    # ── 메인 루프 ─────────────────────────────────────────────
    def run(self):
        log.info(f"AI 워커 시작 pid={os.getpid()}")
        self._recover_stale()
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="ai-job") as pool:
            while not self._stop.is_set():
                self._running = {jid: f for jid, f in self._running.items() if not f.done()}
                if time.monotonic() - self._recovered_at >= RECOVER_EVERY_SECONDS:
                    self._recover_stale()
                self._maybe_daily_issue(pool)

                free = self._read_concurrency() - len(self._running)
                claimed = self._claim(free) if free > 0 else []
                for job_id in claimed:
                    self._running[job_id] = pool.submit(self._process, job_id)
                if not claimed:
                    self._stop.wait(POLL_SECONDS)

            log.info(f"종료 신호 — 진행 중 {len(self._running)}건이 끝나길 최대 {STOP_GRACE_SECONDS}초 기다림")
            deadline = time.monotonic() + STOP_GRACE_SECONDS
            for f in list(self._running.values()):
                try:
                    f.result(timeout=max(0.0, deadline - time.monotonic()))
                except Exception:  # noqa: BLE001 — 남은 건 다음 기동 때 복구된다
                    pass
        log.info("AI 워커 종료")

    # ── 오늘의 경제 이슈(sql/yangbong/014) ─────────────────────
    def _maybe_daily_issue(self, pool):
        """1분마다 한 번. AI 호출이 길어 작업 풀에서 돌리고, 돌고 있으면 다시 넣지 않는다."""
        if time.monotonic() - self._issue_checked_at < DAILY_ISSUE_CHECK_SECONDS:
            return
        self._issue_checked_at = time.monotonic()
        if self._issue_future is not None and not self._issue_future.done():
            return
        self._issue_future = pool.submit(self._run_daily_issue)

    def _run_daily_issue(self):
        from app.services import daily_issue_service
        session = self._db.get_session()
        try:
            if daily_issue_service.run_due(session):
                log.info("오늘의 경제 이슈 만들기 완료")
        except Exception as e:  # noqa: BLE001 — FAILED 로 남고 10분 뒤 다시(하루 3번까지)
            session.rollback()
            log.error(f"오늘의 경제 이슈 만들기 실패: {e}")
        finally:
            session.remove()

    def stop(self, *_):
        self._stop.set()

    def _claim(self, limit) -> list[int]:
        session = self._db.get_session()
        try:
            jobs = self._jobDao.claim_next(session, limit)
            ids = [j.job_id for j in jobs]
            session.commit()
            for j in jobs:
                log.info(f"job {j.job_id} 시작 {j.stock_code}/{j.section} (시도 {j.attempts})")
            return ids
        except Exception as e:  # noqa: BLE001
            session.rollback()
            log.error(f"작업 가져오기 실패: {e}")
            return []
        finally:
            session.remove()

    # ── 작업 1건 ──────────────────────────────────────────────
    def _process(self, job_id: int):
        session = self._db.get_session()
        code = section = gen_log_id = None
        try:
            job = self._jobDao.get(session, job_id)
            if job is None:
                return
            code, section, gen_log_id = job.stock_code, job.section, job.gen_log_id
            session.commit()   # 읽기 트랜잭션을 끝내 둔다(아래 KIS·AI 호출 동안 연결을 쥐지 않게)

            started = time.monotonic()
            if section == 'finance':
                data = self._with_kis_retry(lambda: self.kis.get_fundamentals(code))
                data = json.loads(json.dumps(data, default=float))   # Decimal·numpy 값이 섞여도 JSON 열에 들어가게
                self._financeDao.upsert(session, code, data)
                session.commit()
            elif section == 'news':
                self._with_kis_retry(lambda: self._content.generate_now(session, code, section, kis=self.kis))
            else:
                self._content.generate_now(session, code, section)

            self._jobDao.finish(session, job_id, 'DONE')
            session.commit()
            log.info(f"job {job_id} 완료 {code}/{section} {time.monotonic() - started:.1f}s")
            self._notify_subscribers(session, job_id, code, section, ok=True)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            log.error(f"job {job_id} 실패 {code}/{section}: {e}")
            if code is not None:
                self._fail(job_id, code, section, gen_log_id, e)
        finally:
            session.remove()

    def _fail(self, job_id, code, section, gen_log_id, exc: Exception):
        session = self._db.get_session()
        try:
            self._content.refund_generation(session, gen_log_id)
            detail = ''.join(traceback.format_exception(exc))[-4000:]
            self._jobDao.finish(session, job_id, 'FAILED',
                                error_user=FAIL_MESSAGE.get(section, DEFAULT_FAIL_MESSAGE), error_detail=detail)
            session.commit()
            self._notify_subscribers(session, job_id, code, section, ok=False)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            log.error(f"job {job_id} 실패 기록 실패: {e}")
        finally:
            session.remove()

    def _notify_subscribers(self, session, job_id, code, section, ok: bool):
        try:
            user_ids = self._jobDao.subscriber_ids(session, job_id)
            if not user_ids:
                return
            stock = self._stockDao.select_master_stock_by_id(session, {"stock_code": code})
            name = (stock or {}).get("stock_name") or code
            label = SECTION_LABEL.get(section, 'AI 분석')
            link = '/stock/info?' + urlencode({'stock_code': code, 'stock_name': name, 'tab': 'basis'})
            if ok:
                self._notify.notify(session, user_ids, 'AI_DONE', f"{name} {label} 분석이 준비됐어요",
                                    "눌러서 확인해 보세요.", link=link, ref_id=job_id)
            else:
                self._notify.notify(session, user_ids, 'AI_FAILED', f"{name} {label} 분석을 만들지 못했어요",
                                    "오늘 횟수에서는 빠졌어요. 잠시 후 다시 시도해 주세요.", link=link, ref_id=job_id)
        except Exception as e:  # noqa: BLE001 — 알림 실패가 작업 결과를 바꾸지 않는다
            session.rollback()
            log.error(f"job {job_id} 알림 실패: {e}")


def main():
    _setup_logging()
    worker = AiJobWorker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run()


if __name__ == "__main__":
    main()
