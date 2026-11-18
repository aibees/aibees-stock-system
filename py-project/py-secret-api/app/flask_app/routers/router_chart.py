import threading
import datetime
from datetime import datetime
from flask import Blueprint, request, g

from app.flask_app.utils.apiResponse import ApiResponse
from app.services.stocks.StockService import StockService

chart_bp = Blueprint("charts", __name__)

stockServiceImpl = StockService()

# CHART ROUTE ROOT :: TEST
# ===============================================================================
@chart_bp.route("/")
def chart_index():
    return {
        'msg': 'aibees flask :: chart home'
    }


# CHART ROUTE :: STOCK CHART
# ===============================================================================
@chart_bp.route("/stock", methods=['GET'])
def chart_stock_stick():
    search_param = {
        'stock_code': request.args.get('stock_code'),
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'period': request.args.get('period'),
    }
    results = stockServiceImpl.get_stock_chart_data(g.db, search_param)

    return ApiResponse.success(results)

