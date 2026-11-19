"""
AI(Anthropic) 공용 라우트(양봉상회·비밀상회 웹서버 공용, 2026-11-19 py-secret-api router_anthropic 에서 옮김).

    anthropic_bp = create_anthropic_blueprint(content_service)   # url_prefix /api/v1/anthropic

공용 경로
    GET  ""                                  인덱스
    POST /chat · /stream                     관리자(user_id=1)만 — 화면에서 쓰지 않는다
    GET  /stock-analysis/overview|theme      저장된 분석(DB 캐시, AI 미호출)
서버마다 다른 경로(각 서버가 덧붙인다)
    POST /stock-analysis/overview|theme      비밀상회: 요청 안에서 바로 생성 / 양봉상회: 작업 접수(202) → AI 워커
    GET  /stock-analysis/news                비밀상회: 2시간 지났으면 바로 재생성 / 양봉상회: 저장된 것 + 작업 접수

AI 를 새로 부르는(비용이 드는) 엔드포인트의 공통 규칙 (2026-11-15):
  - 로그인 필요. /chat·/stream 은 관리자만(예전에는 인증 없이 열려 주소만 알면 회사 키로 호출할 수 있었다).
  - 종목 분석은 master_stock 에 있는 종목코드만 생성한다(unknown_stock).
  - 하루 생성 한도(사용자별·서버 전체) — StockAiContentService 머리말 참고. 넘으면 429.
"""
import logging

from flask import Blueprint, request, Response, g

from stock_shared.dao.masterStockDao import MasterStockDao
from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse
from web_shared.services.anthropic.anthropicService import AnthropicService

logger = logging.getLogger(__name__)

# 모듈 레벨에서 한 번만 생성 → 동일 client 재사용
anthropicServiceImpl = AnthropicService()
masterStockDaoImpl = MasterStockDao()

ADMIN_USER_ID = 1


def admin_only():
    """관리자가 아니면 403 응답, 관리자면 None."""
    if g.current_user_id != ADMIN_USER_ID:
        return ApiResponse.error("관리자만 사용할 수 있습니다.", status=403)
    return None


def unknown_stock(stock_code: str):
    """master_stock 에 없는 종목이면 400 응답, 있으면 None."""
    if not masterStockDaoImpl.select_master_stock_by_id(g.db, {"stock_code": stock_code}):
        return ApiResponse.error("없는 종목코드입니다.", status=400)
    return None


def get_stock_code() -> str:
    return request.args.get("stock_code", "").strip()


def create_anthropic_blueprint(content_service) -> Blueprint:
    anthropic_bp = Blueprint("anthropic", __name__)

    @anthropic_bp.route("")
    def anthropic_index():
        return {"msg": "aibees flask :: anthropic home"}

    # CHAT (단순 요청/응답) — body: {messages, system?, model?, max_tokens?}
    @anthropic_bp.route("/chat", methods=["POST"])
    @require_auth
    def chat():
        if (denied := admin_only()):
            return denied
        body = request.get_json(silent=True) or {}
        messages = body.get("messages")
        if not messages:
            return ApiResponse.error("messages 필드가 필요합니다.")
        try:
            result = anthropicServiceImpl.chat(
                messages=messages,
                model=body.get("model", "claude-sonnet-5"),
                system=body.get("system"),
                max_tokens=body.get("max_tokens", 8096),
            )
            return ApiResponse.success(result)
        except Exception as e:
            logger.error(e, exc_info=True)
            return ApiResponse.error(str(e)[:255])

    # STREAM (SSE) — body: chat 와 같음. 응답: data: <chunk>\n\n … data: [DONE]\n\n
    @anthropic_bp.route("/stream", methods=["POST"])
    @require_auth
    def stream():
        if (denied := admin_only()):
            return denied
        body = request.get_json(silent=True) or {}
        messages = body.get("messages")
        if not messages:
            return ApiResponse.error("messages 필드가 필요합니다.")

        def generate():
            try:
                for chunk in anthropicServiceImpl.stream(
                    messages=messages,
                    model=body.get("model", "claude-sonnet-5"),
                    system=body.get("system"),
                    max_tokens=body.get("max_tokens", 8096),
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(e, exc_info=True)
                yield f"data: [ERROR] {str(e)[:255]}\n\n"

        return Response(generate(), content_type="text/event-stream; charset=utf-8")

    # GET /stock-analysis/overview?stock_code=005930 — 저장된 기업개요·재무현황
    @anthropic_bp.route("/stock-analysis/overview", methods=["GET"])
    def get_overview():
        stock_code = get_stock_code()
        if not stock_code:
            return ApiResponse.error("stock_code 파라미터가 필요합니다.")
        return ApiResponse.success(content_service.get_cached(g.db, stock_code, "overview"))

    # GET /stock-analysis/theme?stock_code=005930 — 저장된 현재 테마
    @anthropic_bp.route("/stock-analysis/theme", methods=["GET"])
    def get_theme():
        stock_code = get_stock_code()
        if not stock_code:
            return ApiResponse.error("stock_code 파라미터가 필요합니다.")
        return ApiResponse.success(content_service.get_cached(g.db, stock_code, "theme"))

    return anthropic_bp
