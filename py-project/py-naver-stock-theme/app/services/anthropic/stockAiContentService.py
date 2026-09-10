"""
종목 AI 분석 콘텐츠(기업개요+재무현황 / 테마 / 뉴스) DB 캐싱 서비스.

- overview(기업개요+재무현황), theme(현재테마): 버튼(수동) 갱신, 최소 재호출 간격 1시간.
  단, overview는 실적발표월(2·5·8·11월)에만 갱신 가능 — 전 사용자 공통, 예외 없음.
  1시간 재호출 제한은 관리자(user_id=1)만 force=True 로 우회 가능.
- news(최근 공시·뉴스): 버튼 없이 조회 시 자동 — 마지막 갱신 후 2시간 지났으면
  KIS 헤드라인을 먼저 가져와 그걸 근거로 Claude가 요약(웹서치 미사용, 비용 절감).
"""
import logging
from datetime import datetime, timedelta

from app.domains.dao.stockAiContentDao import StockAiContentDao
from stock_shared.dao.masterStockDao import MasterStockDao
from app.ext_services.kis.KisEngine import KisEngine
from app.services.anthropic.anthropicService import AnthropicService
from app.services.anthropic.stockAnalysisTemplate import (
    STOCK_ANALYSIS_SYSTEM,
    build_overview_messages,
    build_theme_messages,
    build_news_messages,
)

logger = logging.getLogger(__name__)

MIN_REFRESH_INTERVAL = timedelta(hours=1)
NEWS_TTL = timedelta(hours=2)
ANNOUNCEMENT_MONTHS = {2, 5, 8, 11}


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

    def __init__(self):
        self._dao = StockAiContentDao()
        self._masterStockDao = MasterStockDao()
        self._anthropic = AnthropicService()

    # ── 조회 (DB 캐시만, AI 미호출) ─────────────────────────────
    def get_cached(self, session, stock_code: str, section: str) -> dict | None:
        return self._dao.select_by_stock_section(session, stock_code, section)

    # ── 기업개요 + 재무현황 (버튼) ───────────────────────────────
    def refresh_overview(self, session, stock_code: str, is_admin: bool, force: bool) -> dict:
        cached = self._dao.select_by_stock_section(session, stock_code, "overview")

        # 한 번도 생성된 적 없는 종목(null)은 발표월 여부와 무관하게 최초 1회는 허용.
        # 이미 내용이 있는 종목의 "재생성"부터 실적발표월 제한이 걸린다.
        if cached and datetime.now().month not in ANNOUNCEMENT_MONTHS:
            raise AnnouncementMonthRequiredError()

        self._check_cooldown(cached, is_admin, force)

        result = self._anthropic.chat(
            messages=build_overview_messages(stock_code),
            system=STOCK_ANALYSIS_SYSTEM,
            use_web_search=True,
        )
        return self._save(session, stock_code, "overview", result)

    # ── 현재 테마 (버튼) ─────────────────────────────────────────
    def refresh_theme(self, session, stock_code: str, is_admin: bool, force: bool) -> dict:
        cached = self._dao.select_by_stock_section(session, stock_code, "theme")
        self._check_cooldown(cached, is_admin, force)

        result = self._anthropic.chat(
            messages=build_theme_messages(stock_code),
            system=STOCK_ANALYSIS_SYSTEM,
            use_web_search=True,
        )
        return self._save(session, stock_code, "theme", result)

    # ── 최근 공시·뉴스 (자동, 2시간 TTL) ──────────────────────────
    def get_or_refresh_news(self, session, stock_code: str) -> dict:
        cached = self._dao.select_by_stock_section(session, stock_code, "news")
        if cached and (datetime.now() - cached["updated_at"]) < NEWS_TTL:
            return cached

        stock = self._masterStockDao.select_master_stock_by_id(session, {"stock_code": stock_code})
        stock_name = stock["stock_name"] if stock else None

        headlines = KisEngine(virtual=False).get_news_title(stock_code, stock_name=stock_name)

        result = self._anthropic.chat(
            messages=build_news_messages(stock_code, headlines),
            system=STOCK_ANALYSIS_SYSTEM,
            use_web_search=True,
        )
        return self._save(session, stock_code, "news", result)

    # ── 내부 ──────────────────────────────────────────────────
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
