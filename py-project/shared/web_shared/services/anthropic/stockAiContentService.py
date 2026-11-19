"""
종목 AI 분석 콘텐츠(기업개요+재무현황 / 테마 / 뉴스) DB 캐싱 서비스.

- overview(기업개요+재무현황), theme(현재테마): 버튼(수동) 갱신, 최소 재호출 간격 1시간.
  단, overview는 실적발표월(2·5·8·11월)에만 갱신 가능 — 전 사용자 공통, 예외 없음.
  1시간 재호출 제한은 관리자(user_id=1)만 force=True 로 우회 가능.
- news(최근 공시·뉴스): 버튼 없이 조회 시 자동 — 마지막 갱신 후 2시간 지났으면
  KIS 헤드라인을 먼저 가져와 그걸 근거로 Claude가 요약(웹서치 미사용, 비용 절감).
  뉴스용 KIS 가 없는 서버(news_kis_factory=None — 양봉상회 API)는 새로 만들지 않고 저장된 것만 보여 준다.

하루 생성 한도(2026-11-16) — 양봉상회는 누구나 가입하므로, 로그인만으로 Anthropic 비용을 쓸 수 있으면 안 된다.
  - 사용자별: 하루 GEN_PER_USER_DAY 건(관리자 user_id=1 은 제외)
  - 서버 전체: 하루 GEN_TOTAL_DAY 건(관리자 생성분도 센다, 관리자는 막지 않는다)
  - 값은 공통코드 stock/setting/ai → 환경변수 AI_GEN_PER_USER_DAY·AI_GEN_TOTAL_DAY → 기본값 순.
  - 생성 기록은 stock_ai_gen_log. 테이블이 없으면(SQL 미적용) 관리자 외에는 생성을 막는다(fail closed).
  - 기록은 AI 를 부르기 **전에** 남기고(동시에 여러 번 눌러도 한도를 넘지 않게), AI 호출이 실패하면 지운다.
"""
import logging
import os
from datetime import datetime, timedelta

from web_shared.dao.stockAiContentDao import StockAiContentDao
from web_shared.dao.stockAiGenLogDao import StockAiGenLogDao
from web_shared.dao.masterCodesDao import MasterCodesDao
from stock_shared.dao.masterStockDao import MasterStockDao
from web_shared.ext_services.kis.KisEngine import KisEngine
from web_shared.services.anthropic.anthropicService import AnthropicService
from web_shared.services.anthropic.stockAnalysisTemplate import (
    STOCK_ANALYSIS_SYSTEM,
    build_overview_messages,
    build_theme_messages,
    build_news_messages,
)

logger = logging.getLogger(__name__)

MIN_REFRESH_INTERVAL = timedelta(hours=1)
NEWS_TTL = timedelta(hours=2)
ANNOUNCEMENT_MONTHS = {2, 5, 8, 11}

# 하루 생성 한도 기본값. 양봉상회는 공개 가입이라 낮게, 비밀상회는 private 회원뿐이라 넉넉하게.
#   어느 쪽인지는 서비스를 만드는 서버가 정한다(StockAiContentService(default_limits=...)).
YANGBONG_LIMITS = {'GEN_PER_USER_DAY': 5, 'GEN_TOTAL_DAY': 100}
SECRET_LIMITS = {'GEN_PER_USER_DAY': 30, 'GEN_TOTAL_DAY': 300}
_LIMIT_CODES_KEY = {'system': 'stock', 'source': 'setting', 'category': 'ai'}


class GenerationQuotaError(Exception):
    """하루 생성 한도 초과(또는 한도를 셀 수 없음)."""


class RefreshCooldownError(Exception):
    """1시간 최소 재호출 간격 내 재요청 (관리자 force=True 로만 우회 가능)."""

    def __init__(self, next_available_at: datetime):
        self.next_available_at = next_available_at
        super().__init__(f"1시간 이내에 이미 갱신되었습니다. 다음 갱신 가능: {next_available_at:%H:%M}")


class AnnouncementMonthRequiredError(Exception):
    """실적발표월(2·5·8·11월)이 아닐 때 overview 갱신 시도."""

    def __init__(self):
        super().__init__("기업개요·재무현황은 실적발표월(2·5·8·11월)에만 갱신할 수 있습니다.")


class StockAiContentService:
    """
    default_limits    : 하루 생성 한도 기본값(YANGBONG_LIMITS·SECRET_LIMITS). 공통코드·환경변수가 있으면 그것이 우선.
    news_kis_factory  : 동기 뉴스 생성(get_or_refresh_news)에 쓸 KisEngine 을 만드는 함수. None 이면 저장된 뉴스만 보여 준다.
                        (양봉상회 API 는 None — 뉴스는 AI 워커가 generate_now(kis=...) 로 만든다)
    """

    def __init__(self, default_limits: dict, news_kis_factory=None):
        self._default_limits = dict(default_limits)
        self._news_kis_factory = news_kis_factory
        self._dao = StockAiContentDao()
        self._masterStockDao = MasterStockDao()
        self._anthropic = AnthropicService()
        self._genLogDao = StockAiGenLogDao()
        self._codesDao = MasterCodesDao()

    # ── 조회 (DB 캐시만, AI 미호출) ─────────────────────────────
    def get_cached(self, session, stock_code: str, section: str) -> dict | None:
        return self._dao.select_by_stock_section(session, stock_code, section)

    # ── 기업개요 + 재무현황 (버튼) ───────────────────────────────
    def refresh_overview(self, session, stock_code: str, user_id: int, is_admin: bool, force: bool) -> dict:
        cached = self._dao.select_by_stock_section(session, stock_code, "overview")

        # 한 번도 생성된 적 없는 종목(null)은 발표월 여부와 무관하게 최초 1회는 허용.
        # 이미 내용이 있는 종목의 "재생성"부터 실적발표월 제한이 걸린다.
        if cached and datetime.now().month not in ANNOUNCEMENT_MONTHS:
            raise AnnouncementMonthRequiredError()

        self._check_cooldown(cached, is_admin, force)

        return self._generate(session, stock_code, "overview", user_id, is_admin, lambda: self._anthropic.chat(
            messages=build_overview_messages(stock_code),
            system=STOCK_ANALYSIS_SYSTEM,
            use_web_search=True,
        ))

    # ── 현재 테마 (버튼) ─────────────────────────────────────────
    def refresh_theme(self, session, stock_code: str, user_id: int, is_admin: bool, force: bool) -> dict:
        cached = self._dao.select_by_stock_section(session, stock_code, "theme")
        self._check_cooldown(cached, is_admin, force)

        return self._generate(session, stock_code, "theme", user_id, is_admin, lambda: self._anthropic.chat(
            messages=build_theme_messages(stock_code),
            system=STOCK_ANALYSIS_SYSTEM,
            use_web_search=True,
        ))

    # ── 최근 공시·뉴스 (자동, 2시간 TTL) ──────────────────────────
    def get_or_refresh_news(self, session, stock_code: str, user_id: int, is_admin: bool) -> dict | None:
        cached = self._dao.select_by_stock_section(session, stock_code, "news")
        if cached and (datetime.now() - cached["updated_at"]) < NEWS_TTL:
            return cached
        if self._news_kis_factory is None:
            # 뉴스 헤드라인은 KIS 로만 받는다 — KIS 를 쓰지 않는 서버는 저장된 것만(없으면 None).
            return cached

        stock = self._masterStockDao.select_master_stock_by_id(session, {"stock_code": stock_code})
        stock_name = stock["stock_name"] if stock else None

        try:
            # 뉴스는 버튼이 아니라 조회만으로 만들어진다. 한도를 넘으면 오류 대신 지난 내용을 보여 준다.
            return self._generate(session, stock_code, "news", user_id, is_admin, lambda: self._anthropic.chat(
                messages=build_news_messages(
                    stock_code, self._news_kis_factory().get_news_title(stock_code, stock_name=stock_name)),
                system=STOCK_ANALYSIS_SYSTEM,
                use_web_search=True,
            ))
        except GenerationQuotaError as e:
            logger.info(f"[ai-news] {stock_code} 새로 만들지 않음: {e}")
            return cached

    # ── 비동기 작업(양봉상회, AiJobService·AI 워커)이 쓰는 조각 ────────────
    #   요청 시점 검사(check_refresh_allowed·check_quota)와 실제 생성(generate_now)을 나눈다.
    #   비밀상회의 동기 경로(refresh_*·get_or_refresh_news)는 위 메서드를 그대로 쓴다.
    def check_refresh_allowed(self, session, stock_code: str, section: str, is_admin: bool, force: bool):
        """버튼 갱신을 지금 받아도 되는지. 안 되면 AnnouncementMonthRequiredError·RefreshCooldownError."""
        cached = self._dao.select_by_stock_section(session, stock_code, section)
        if section == "overview" and cached and datetime.now().month not in ANNOUNCEMENT_MONTHS:
            raise AnnouncementMonthRequiredError()
        self._check_cooldown(cached, is_admin, force)
        return cached

    @staticmethod
    def news_is_stale(cached: dict | None) -> bool:
        return not cached or (datetime.now() - cached["updated_at"]) >= NEWS_TTL

    def check_quota(self, session, user_id: int | None, is_admin: bool):
        """하루 한도 검사만(기록은 남기지 않는다). user_id 가 None 이면(자동 작업) 서버 전체 한도만 본다."""
        if is_admin:
            return
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        limits = self._limits(session)
        if user_id is not None and \
                self._genLogDao.count_since(session, today, user_id=user_id) >= limits['GEN_PER_USER_DAY']:
            raise GenerationQuotaError(
                f"오늘 AI 분석을 새로 만들 수 있는 횟수({limits['GEN_PER_USER_DAY']}번)를 다 썼어요. 내일 다시 시도해 주세요.")
        if self._genLogDao.count_since(session, today) >= limits['GEN_TOTAL_DAY']:
            raise GenerationQuotaError("오늘은 AI 분석 요청이 많아 새로 만들 수 없어요. 내일 다시 시도해 주세요.")

    def record_generation(self, session, stock_code: str, section: str, user_id: int | None) -> int:
        """생성 기록 1행(한도 차감). 커밋은 호출자. 자동 작업은 user_id 0 으로 남긴다."""
        return self._genLogDao.insert(session, user_id or 0, stock_code, section, datetime.now())

    def refund_generation(self, session, log_id: int | None):
        """생성이 실패했으면 차감한 기록을 지운다. 커밋은 호출자."""
        if log_id is not None:
            self._genLogDao.delete(session, log_id)

    def generate_now(self, session, stock_code: str, section: str, kis: KisEngine | None = None) -> dict:
        """AI 를 불러 만들고 저장한다(한도 검사·기록 없음 — 호출자 몫). news 는 kis 가 필요하다."""
        if section == "overview":
            messages = build_overview_messages(stock_code)
        elif section == "theme":
            messages = build_theme_messages(stock_code)
        elif section == "news":
            if kis is None:
                raise ValueError("news 생성에는 KIS 엔진이 필요합니다.")
            stock = self._masterStockDao.select_master_stock_by_id(session, {"stock_code": stock_code})
            stock_name = stock["stock_name"] if stock else None
            messages = build_news_messages(stock_code, kis.get_news_title(stock_code, stock_name=stock_name))
        else:
            raise ValueError(f"알 수 없는 섹션: {section}")
        # AI 호출(수십 초) 동안 DB 연결을 쥐지 않게 읽기 트랜잭션을 끝낸다(양봉 계정 연결 수 한도 15).
        session.commit()
        result = self._anthropic.chat(messages=messages, system=STOCK_ANALYSIS_SYSTEM, use_web_search=True)
        return self._save(session, stock_code, section, result)

    # ── 내부 ──────────────────────────────────────────────────
    def _limits(self, session) -> dict:
        limits = dict(self._default_limits)
        try:
            codes = {r['code']: r['desc'] for r in self._codesDao.select_master_code(session, _LIMIT_CODES_KEY)}
        except Exception as e:   # 공통코드를 못 읽어도 환경변수·기본값으로 센다
            logger.warning(f"[ai-limit] 공통코드 조회 실패 — 기본값 사용: {e}")
            codes = {}
        for code in limits:
            raw = codes.get(code) or os.environ.get(f"AI_{code}")
            try:
                if raw not in (None, ''):
                    limits[code] = max(0, int(str(raw).strip()))
            except ValueError:
                logger.warning(f"[ai-limit] {code}={raw!r} 숫자가 아님 — 기본값 {limits[code]}")
        return limits

    def _reserve(self, session, stock_code: str, section: str, user_id: int, is_admin: bool):
        """한도를 확인하고 생성 기록을 먼저 남긴다. 기록 id(관리자이고 기록에 실패하면 None)."""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            if not is_admin:
                limits = self._limits(session)
                if self._genLogDao.count_since(session, today, user_id=user_id) >= limits['GEN_PER_USER_DAY']:
                    raise GenerationQuotaError(
                        f"오늘 AI 분석을 새로 만들 수 있는 횟수({limits['GEN_PER_USER_DAY']}번)를 다 썼어요. 내일 다시 시도해 주세요.")
                if self._genLogDao.count_since(session, today) >= limits['GEN_TOTAL_DAY']:
                    raise GenerationQuotaError("오늘은 AI 분석 요청이 많아 새로 만들 수 없어요. 내일 다시 시도해 주세요.")
            log_id = self._genLogDao.insert(session, user_id, stock_code, section, now)
            session.commit()
            return log_id
        except GenerationQuotaError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"[ai-limit] 생성 기록 실패(stock_ai_gen_log 적용 여부 확인): {e}")
            if is_admin:
                return None
            raise GenerationQuotaError("지금은 AI 분석을 새로 만들 수 없어요. 잠시 후 다시 시도해 주세요.")

    def _generate(self, session, stock_code: str, section: str, user_id: int, is_admin: bool, call) -> dict:
        log_id = self._reserve(session, stock_code, section, user_id, is_admin)
        try:
            result = call()
        except Exception:
            # AI 호출이 실패했으면 횟수에서 빼 준다(기록 삭제 실패는 한도가 1 줄어드는 것뿐이라 무시).
            if log_id is not None:
                try:
                    self._genLogDao.delete(session, log_id)
                    session.commit()
                except Exception:
                    session.rollback()
            raise
        return self._save(session, stock_code, section, result)

    def _check_cooldown(self, cached: dict | None, is_admin: bool, force: bool):
        if is_admin and force:
            return

        if not cached:
            return

        next_available_at = cached["updated_at"] + MIN_REFRESH_INTERVAL
        if datetime.now() < next_available_at:
            raise RefreshCooldownError(next_available_at)

    def _save(self, session, stock_code: str, section: str, result: dict) -> dict:
        self._dao.upsert(session, {
            "stock_code": stock_code,
            "section": section,
            "content": result["content"],
            "model": result["model"],
            "input_tokens": result["usage"]["input_tokens"],
            "output_tokens": result["usage"]["output_tokens"],
        })
        session.commit()
        return self._dao.select_by_stock_section(session, stock_code, section)
