"""
양봉상회 AI 분석 라우트 — 공용 경로는 web_shared.routers.router_anthropic, 여기는 **작업 큐로 넘기는** 경로(2026-11-18 비동기화).

    POST /stock-analysis/overview|theme   (로그인) 작업 접수 202 → AI 워커가 만들고 알린다(router_ai_job.request_job 과 같음)
    GET  /stock-analysis/news             (로그인) 저장된 것(data) + 2시간 지났으면 작업 접수(news_job·stale)
API 는 Anthropic·KIS 를 부르지 않는다. 생성은 app.workers.ai_job_worker 가 한다.
"""
import logging

from flask import g

from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse
from web_shared.routers.router_anthropic import create_anthropic_blueprint, unknown_stock, get_stock_code
from app.flask_app.routers.router_ai_job import aiJobServiceImpl, request_job
from app.services.anthropic.content import yangbong_content_service

logger = logging.getLogger(__name__)

anthropic_bp = create_anthropic_blueprint(yangbong_content_service())


# POST /api/v1/anthropic/stock-analysis/overview?stock_code=005930  (로그인 필요) — 작업 접수
@anthropic_bp.route("/stock-analysis/overview", methods=["POST"])
@require_auth
def refresh_overview():
    stock_code = get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := unknown_stock(stock_code)):
        return bad
    return request_job("overview", stock_code)


# POST /api/v1/anthropic/stock-analysis/theme?stock_code=005930  (로그인 필요) — 작업 접수
@anthropic_bp.route("/stock-analysis/theme", methods=["POST"])
@require_auth
def refresh_theme():
    stock_code = get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := unknown_stock(stock_code)):
        return bad
    return request_job("theme", stock_code)


# GET /api/v1/anthropic/stock-analysis/news?stock_code=005930  (로그인 필요)
#   data 는 예전처럼 저장된 내용(없으면 null), 작업 정보는 최상위 news_job·stale 로 붙인다(옛 화면 호환).
@anthropic_bp.route("/stock-analysis/news", methods=["GET"])
@require_auth
def get_news():
    stock_code = get_stock_code()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if (bad := unknown_stock(stock_code)):
        return bad
    try:
        res = aiJobServiceImpl.news(g.db, stock_code)
        return ApiResponse.success(res["data"], extra={"stale": res["stale"], "news_job": res["job"]})
    except Exception as e:  # noqa: BLE001
        logger.error(e, exc_info=True)
        return ApiResponse.error("뉴스 요약을 불러오지 못했어요.", status=500)
