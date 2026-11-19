"""
비밀상회 AI 분석 라우트 — 공용 경로는 web_shared.routers.router_anthropic, 여기는 **요청 안에서 바로 생성**하는 경로(2026-11-19).

    POST /stock-analysis/overview|theme   (로그인) 바로 생성. body {force} — 관리자(user_id=1)만 1시간 제한 우회
    GET  /stock-analysis/news             (로그인) 2시간 지났으면 KIS 헤드라인 기반으로 바로 재생성
섹션별 갱신 규칙
  - overview(기업개요+재무현황), theme(현재테마): 버튼(수동) 갱신, 최소 재호출 간격 1시간
    · overview는 실적발표월(2·5·8·11월)에만 갱신 가능 (전 사용자 공통, 예외 없음)
  - news(최근 공시·뉴스): 버튼 없이 조회 시 자동. 조회가 곧 생성(AI + 1번 사용자 KIS 키)이라 로그인한 사용자만.
"""
import logging

from flask import request, g

from web_shared.auth.decorators import require_auth
from web_shared.ext_services.kis.KisEngine import KisEngine
from web_shared.http.response import ApiResponse
from web_shared.routers.router_anthropic import create_anthropic_blueprint, unknown_stock, get_stock_code, ADMIN_USER_ID
from web_shared.services.anthropic.stockAiContentService import (
    StockAiContentService,
    SECRET_LIMITS,
    RefreshCooldownError,
    AnnouncementMonthRequiredError,
    GenerationQuotaError,
)
from app.utils.service import KIS_ENABLED

logger = logging.getLogger(__name__)

# 뉴스 헤드라인은 KIS 로 받는다. KIS 를 끈 서버면 저장된 뉴스만 보여 준다.
stockAiContentServiceImpl = StockAiContentService(
    default_limits=SECRET_LIMITS,
    news_kis_factory=(lambda: KisEngine(virtual=False)) if KIS_ENABLED else None,
)

anthropic_bp = create_anthropic_blueprint(stockAiContentServiceImpl)


# POST /api/v1/anthropic/stock-analysis/overview?stock_code=005930  (로그인 필요)
@anthropic_bp.route("/stock-analysis/overview", methods=["POST"])
@require_auth
def refresh_overview():
    stock_code = get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := unknown_stock(stock_code)):
        return bad

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


# POST /api/v1/anthropic/stock-analysis/theme?stock_code=005930  (로그인 필요)
@anthropic_bp.route("/stock-analysis/theme", methods=["POST"])
@require_auth
def refresh_theme():
    stock_code = get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := unknown_stock(stock_code)):
        return bad

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
@anthropic_bp.route("/stock-analysis/news", methods=["GET"])
@require_auth
def get_news():
    stock_code = get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := unknown_stock(stock_code)):
        return bad

    try:
        result = stockAiContentServiceImpl.get_or_refresh_news(
            g.db, stock_code, g.current_user_id, g.current_user_id == ADMIN_USER_ID)
        return ApiResponse.success(result)
    except Exception as e:
        logger.error(e, exc_info=True)
        return ApiResponse.error(str(e)[:255])
