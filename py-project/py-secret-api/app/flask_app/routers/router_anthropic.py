import logging
from flask import Blueprint, request, Response, g
from app.flask_app.utils.apiResponse import ApiResponse
from app.flask_app.routers.router_oauth import require_auth
from app.services.anthropic.anthropicService import AnthropicService
from app.services.anthropic.stockAiContentService import (
    StockAiContentService,
    RefreshCooldownError,
    AnnouncementMonthRequiredError,
    GenerationQuotaError,
)
from stock_shared.dao.masterStockDao import MasterStockDao
from app.utils.service import IS_YANGBONG

logger = logging.getLogger(__name__)

anthropic_bp = Blueprint("anthropic", __name__)

# 모듈 레벨에서 한 번만 생성 → 동일 client 재사용
anthropicServiceImpl = AnthropicService()
stockAiContentServiceImpl = StockAiContentService()
masterStockDaoImpl = MasterStockDao()

ADMIN_USER_ID = 1

# 양봉상회(2026-11-18): AI 생성은 요청을 쌓고 AI 워커가 처리한다(router_ai_job·AiJobService).
#   옛 POST /stock-analysis/<overview|theme> 는 작업 접수(202)로 바뀌고, GET news 는 저장된 것 + 2시간 지났으면 작업을 넣는다.
#   비밀상회는 지금처럼 요청 안에서 바로 만든다.
if IS_YANGBONG:
    from app.flask_app.routers.router_ai_job import aiJobServiceImpl, request_job

# AI 를 새로 부르는(비용이 드는) 엔드포인트의 공통 규칙 (2026-11-15):
#   - 로그인 필요. /chat·/stream 은 화면에서 쓰지 않으므로 관리자(user_id=1)만.
#     예전에는 인증 없이 열려 있어, 주소만 알면 누구나 모델·max_tokens 를 골라 회사 키로 호출할 수 있었다.
#   - 종목 분석은 master_stock 에 있는 종목코드만 생성한다(없는 코드로 생성 요청을 반복해 비용을 쓰게 하는 것 방지).
#   - 하루 생성 한도(사용자별·서버 전체, 2026-11-16) — StockAiContentService 머리말 참고. 넘으면 429.


def _admin_only():
    """관리자가 아니면 403 응답, 관리자면 None."""
    if g.current_user_id != ADMIN_USER_ID:
        return ApiResponse.error("관리자만 사용할 수 있습니다.", status=403)
    return None


def _unknown_stock(stock_code: str):
    """master_stock 에 없는 종목이면 400 응답, 있으면 None."""
    if not masterStockDaoImpl.select_master_stock_by_id(g.db, {"stock_code": stock_code}):
        return ApiResponse.error("없는 종목코드입니다.", status=400)
    return None


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
@require_auth
def chat():
    if (denied := _admin_only()):
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


# ANTHROPIC ROUTE :: STREAM (SSE)
# ===============================================================================
# Request body: chat와 동일
# Response: text/event-stream  →  data: <chunk>\n\n  … data: [DONE]\n\n
@anthropic_bp.route("/stream", methods=["POST"])
@require_auth
def stream():
    if (denied := _admin_only()):
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
    if (bad := _unknown_stock(stock_code)):
        return bad

    if IS_YANGBONG:
        return request_job("overview", stock_code)

    body = request.get_json(silent=True) or {}
    is_admin = (g.current_user_id == ADMIN_USER_ID)
    force = is_admin and bool(body.get("force"))

    try:
        result = stockAiContentServiceImpl.refresh_overview(g.db, stock_code, g.current_user_id, is_admin, force)
        return ApiResponse.success(result)
    except AnnouncementMonthRequiredError as e:
        return ApiResponse.error(str(e))
    except (RefreshCooldownError, GenerationQuotaError) as e:
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
    if (bad := _unknown_stock(stock_code)):
        return bad

    if IS_YANGBONG:
        return request_job("theme", stock_code)

    body = request.get_json(silent=True) or {}
    is_admin = (g.current_user_id == ADMIN_USER_ID)
    force = is_admin and bool(body.get("force"))

    try:
        result = stockAiContentServiceImpl.refresh_theme(g.db, stock_code, g.current_user_id, is_admin, force)
        return ApiResponse.success(result)
    except (RefreshCooldownError, GenerationQuotaError) as e:
        return ApiResponse.error(str(e), status=429)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])


# GET /api/v1/anthropic/stock-analysis/news?stock_code=005930  (로그인 필요)
# 버튼 없음 — 마지막 갱신 후 2시간 지났으면 서버가 알아서 KIS 헤드라인 기반으로 재생성한다.
#   조회가 곧 생성(AI 호출 + 1번 사용자의 실투자 KIS 키로 뉴스 조회)이라 로그인한 사용자만 부른다.
#   화면(StockInfo.vue)은 로그인해야 열리는 메뉴라 영향 없다.
@anthropic_bp.route("/stock-analysis/news", methods=["GET"])
@require_auth
def get_news():
    stock_code = _get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := _unknown_stock(stock_code)):
        return bad

    if IS_YANGBONG:
        # data 는 예전처럼 저장된 내용(없으면 null), 작업 정보는 최상위 news_job·stale 로 붙인다(옛 화면 호환).
        try:
            res = aiJobServiceImpl.news(g.db, stock_code)
            return ApiResponse.success(res["data"], extra={"stale": res["stale"], "news_job": res["job"]})
        except Exception as e:  # noqa: BLE001
            logger.error(e, exc_info=True)
            return ApiResponse.error("뉴스 요약을 불러오지 못했어요.", status=500)

    try:
        result = stockAiContentServiceImpl.get_or_refresh_news(
            g.db, stock_code, g.current_user_id, g.current_user_id == ADMIN_USER_ID)
        return ApiResponse.success(result)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])
