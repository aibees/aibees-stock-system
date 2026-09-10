import logging
import traceback

from flask import Blueprint, g

from app.flask_app.utils.apiResponse import ApiResponse
from app.services.indicators.WorldIndicatorService import WorldIndicatorService

indicators_bp = Blueprint("indicators", __name__)

worldIndicatorServiceImpl = WorldIndicatorService()

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
