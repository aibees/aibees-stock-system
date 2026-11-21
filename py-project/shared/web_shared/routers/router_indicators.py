import logging
import traceback

from flask import Blueprint, g, request

from web_shared.http.response import ApiResponse
from web_shared.services.indicators.WorldIndicatorService import WorldIndicatorService
from web_shared.services.indicators.MarketSnapshotService import MarketSnapshotService

indicators_bp = Blueprint("indicators", __name__)

worldIndicatorServiceImpl = WorldIndicatorService()
marketSnapshotServiceImpl = MarketSnapshotService()

# INDICATORS ROUTE :: 세계주요지표 (FRED) — 카테고리별 그룹 목록
# ===============================================================================
@indicators_bp.route("/world")
def select_world_indicators():
    try:
        results = worldIndicatorServiceImpl.get_world_indicators(g.db)
        return ApiResponse.success(results)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


# INDICATORS ROUTE :: 홈 시장 요약 — KOSPI / KOSDAQ / 원달러 환율
#   ?extra=us10y : 달러 금리(미국 10년물 국채금리)를 맨 앞에 더한다(양봉상회 홈, 2026-11-22).
#                  비밀상회 홈은 원/달러가 아닌 항목을 모두 지수 카드로 그려서 기본으로는 넣지 않는다.
# ===============================================================================
@indicators_bp.route("/market-snapshot")
def select_market_snapshot():
    try:
        extra = [k.strip() for k in (request.args.get("extra") or "").split(",") if k.strip()]
        results = marketSnapshotServiceImpl.get_market_snapshot(extra=extra)
        return ApiResponse.success(results)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])
