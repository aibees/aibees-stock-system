"""
종목 차트 공용 라우트(양봉상회·비밀상회 웹서버 공용, 2026-11-19 py-secret-api router_chart 에서 옮김).

    chart_bp = create_chart_blueprint(stock_service)   # url_prefix /api/v1/charts
시세 출처는 stock_service 의 bar_source 가 정한다(양봉상회 DB 일봉 / 비밀상회 KIS).
"""
from flask import Blueprint, request, g

from web_shared.http.response import ApiResponse


def create_chart_blueprint(stock_service) -> Blueprint:
    chart_bp = Blueprint("charts", __name__)

    @chart_bp.route("/")
    def chart_index():
        return {'msg': 'aibees flask :: chart home'}

    @chart_bp.route("/stock", methods=['GET'])
    def chart_stock_stick():
        search_param = {
            'stock_code': request.args.get('stock_code'),
            'start_date': request.args.get('start_date'),
            'end_date': request.args.get('end_date'),
            'period': request.args.get('period'),
        }
        results = stock_service.get_stock_chart_data(g.db, search_param)
        return ApiResponse.success(results)

    return chart_bp
