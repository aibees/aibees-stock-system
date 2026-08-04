import logging
from flask import Blueprint, request, Response
from app.flask_app.utils.apiResponse import ApiResponse
from app.services.anthropic.anthropicService import AnthropicService
from app.services.anthropic.stockAnalysisTemplate import build_stock_analysis_messages, STOCK_ANALYSIS_SYSTEM

logger = logging.getLogger(__name__)

anthropic_bp = Blueprint("anthropic", __name__)

# 모듈 레벨에서 한 번만 생성 → 동일 client 재사용
anthropicServiceImpl = AnthropicService()


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
#     "model":    "claude-sonnet-4-6",             (optional)
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
            model=body.get("model", "claude-sonnet-4-6"),
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
                model=body.get("model", "claude-sonnet-4-6"),
                system=body.get("system"),
                max_tokens=body.get("max_tokens", 8096),
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(e, exc_info=True)
            yield f"data: [ERROR] {str(e)[:255]}\n\n"

    return Response(generate(), content_type="text/event-stream; charset=utf-8")


# ANTHROPIC ROUTE :: STOCK ANALYSIS (고정 템플릿)
# ===============================================================================
# GET /api/v1/anthropic/stock-analysis?stock_code=005930
@anthropic_bp.route("/stock-analysis", methods=["GET"])
def stock_analysis():
    stock_code = request.args.get("stock_code", "").strip()

    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")

    try:
        result = anthropicServiceImpl.chat(
            messages=build_stock_analysis_messages(stock_code),
            system=STOCK_ANALYSIS_SYSTEM,
            cache_key=f"stock-analysis:{stock_code}",
            use_web_search=False,  # True로 바꾸면 최신 정보 검색 (토큰 대량 소비 주의)
        )
        return ApiResponse.success(result)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])
