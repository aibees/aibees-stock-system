import logging
import traceback

from flask import Blueprint, g

from app.flask_app.utils.apiResponse import ApiResponse
from app.services.indicators.WorldIndicatorService import WorldIndicatorService
from app.services.indicators.MarketSnapshotService import MarketSnapshotService

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
# ===============================================================================
@indicators_bp.route("/market-snapshot")
def select_market_snapshot():
    try:
        results = marketSnapshotServiceImpl.get_market_snapshot()
        return ApiResponse.success(results)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])
