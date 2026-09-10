import logging
from flask import Blueprint, request, Response, g
from app.flask_app.utils.apiResponse import ApiResponse
from app.flask_app.routers.router_oauth import require_auth
from app.services.anthropic.anthropicService import AnthropicService
from app.services.anthropic.stockAiContentService import (
    StockAiContentService,
    RefreshCooldownError,
    AnnouncementMonthRequiredError,
)

logger = logging.getLogger(__name__)

anthropic_bp = Blueprint("anthropic", __name__)

# 모듈 레벨에서 한 번만 생성 → 동일 client 재사용
anthropicServiceImpl = AnthropicService()
stockAiContentServiceImpl = StockAiContentService()

ADMIN_USER_ID = 1


# ANTHROPIC ROUTE :: ROOT
# ===============================================================================
@anthropic_bp.route("")
def anthropic_index():
    return {"msg": "aibees flask :: anthropic home"}


# ANTHROPIC ROUTE :: CHAT (단순 요청/응답)
# ===============================================================================
# Request body:
#   {
#     "messages": [{"role": "user", "content": "안녕"}],
#     "system":   "당신은 주식 전문가입니다.",   (optional)
#     "model":    "claude-sonnet-5",                (optional)
#     "max_tokens": 8096                           (optional)
#   }
@anthropic_bp.route("/chat", methods=["POST"])
def chat():
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


# ANTHROPIC ROUTE :: STREAM (SSE)
# ===============================================================================
# Request body: chat와 동일
# Response: text/event-stream  →  data: <chunk>\n\n  … data: [DONE]\n\n
@anthropic_bp.route("/stream", methods=["POST"])
def stream():
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


# ANTHROPIC ROUTE :: STOCK ANALYSIS — 기업개요·재무현황·테마·뉴스 (섹션별 DB 캐싱)
# ===============================================================================
# 섹션별 갱신 주기가 달라 하나의 /stock-analysis 대신 섹션별 엔드포인트로 분리했다.
#   - overview(기업개요+재무현황), theme(현재테마): 버튼(수동) 갱신, 최소 재호출 간격 1시간
#     · overview는 실적발표월(2·5·8·11월)에만 갱신 가능 (전 사용자 공통, 예외 없음)
#     · 1시간 제한은 관리자(user_id=1)만 force=true 로 우회 가능
#   - news(최근 공시·뉴스): 버튼 없이 조회 시 자동 — 2시간 지났으면 KIS 헤드라인 기반으로 재생성

def _get_stock_code() -> str:
    return request.args.get("stock_code", "").strip()


# GET /api/v1/anthropic/stock-analysis/overview?stock_code=005930
@anthropic_bp.route("/stock-analysis/overview", methods=["GET"])
def get_overview():
    stock_code = _get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")

    result = stockAiContentServiceImpl.get_cached(g.db, stock_code, "overview")
    return ApiResponse.success(result)


# POST /api/v1/anthropic/stock-analysis/overview?stock_code=005930  (로그인 필요)
# body: { "force": true }  — 관리자(user_id=1)가 1시간 제한을 우회할 때만 사용
@anthropic_bp.route("/stock-analysis/overview", methods=["POST"])
@require_auth
def refresh_overview():
    stock_code = _get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")

    body = request.get_json(silent=True) or {}
    is_admin = (g.current_user_id == ADMIN_USER_ID)
    force = is_admin and bool(body.get("force"))

    try:
        result = stockAiContentServiceImpl.refresh_overview(g.db, stock_code, is_admin, force)
        return ApiResponse.success(result)
    except AnnouncementMonthRequiredError as e:
        return ApiResponse.error(str(e))
    except RefreshCooldownError as e:
        return ApiResponse.error(str(e), status=429)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])


# GET /api/v1/anthropic/stock-analysis/theme?stock_code=005930
@anthropic_bp.route("/stock-analysis/theme", methods=["GET"])
def get_theme():
    stock_code = _get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")

    result = stockAiContentServiceImpl.get_cached(g.db, stock_code, "theme")
    return ApiResponse.success(result)


# POST /api/v1/anthropic/stock-analysis/theme?stock_code=005930  (로그인 필요)
# body: { "force": true }  — 관리자(user_id=1)가 1시간 제한을 우회할 때만 사용
@anthropic_bp.route("/stock-analysis/theme", methods=["POST"])
@require_auth
def refresh_theme():
    stock_code = _get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")

    body = request.get_json(silent=True) or {}
    is_admin = (g.current_user_id == ADMIN_USER_ID)
    force = is_admin and bool(body.get("force"))

    try:
        result = stockAiContentServiceImpl.refresh_theme(g.db, stock_code, is_admin, force)
        return ApiResponse.success(result)
    except RefreshCooldownError as e:
        return ApiResponse.error(str(e), status=429)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])


# GET /api/v1/anthropic/stock-analysis/news?stock_code=005930
# 버튼 없음 — 마지막 갱신 후 2시간 지났으면 서버가 알아서 KIS 헤드라인 기반으로 재생성한다.
@anthropic_bp.route("/stock-analysis/news", methods=["GET"])
def get_news():
    stock_code = _get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")

    try:
        result = stockAiContentServiceImpl.get_or_refresh_news(g.db, stock_code)
        return ApiResponse.success(result)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])
