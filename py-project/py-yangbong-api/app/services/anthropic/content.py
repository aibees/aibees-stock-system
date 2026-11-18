"""양봉상회의 AI 콘텐츠 서비스 — 공개 가입이라 하루 생성 한도를 낮게(YANGBONG_LIMITS), API 는 뉴스를 바로 만들지 않는다
(news_kis_factory 없음 — 뉴스는 AI 워커가 generate_now(kis=...) 로 만든다). 2026-11-19 web_shared 분리."""
from web_shared.services.anthropic.stockAiContentService import StockAiContentService, YANGBONG_LIMITS


def yangbong_content_service() -> StockAiContentService:
    return StockAiContentService(default_limits=YANGBONG_LIMITS)
