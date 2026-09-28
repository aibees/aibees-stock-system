import logging
import traceback, pprint
from flask import Blueprint, request, g

from stock_shared.dao.masterStockDao import MasterStockDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse
from app.services.stocks.StockService import StockService
from app.utils.constants.Literal import Literal

stocks_bp = Blueprint("stocks", __name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

masterStockDaoImpl = MasterStockDao()
stockServiceImpl = StockService()

# STOCKS ROUTE :: ROOT
# ===============================================================================
@stocks_bp.route("")
def stocks_index():
    return {
        'msg': 'aibees flask :: stocks home'
    }
    
 # STOCKS ROUTE :: SELECT SEARCH
# ===============================================================================   
@stocks_bp.route('/search')
def select_master_stock_search():
    search_params = {
        'stock_name': request.args.get('searchTxt'),
        'search_option': True
    }
    
    try:
        results = masterStockDaoImpl.select_master_stock(g.db, search_params)
        return ApiResponse.success(results)
    except Exception as e:
        print(str(e))
        return ApiResponse.error(str(e)[:255])
    

@stocks_bp.route('/buy-target')
def select_buy_target_stock():

    search_params = {
        Literal.YMD: request.args.get(Literal.YMD),
    }

    try:
        results = stockServiceImpl.get_buy_target_stock_list(g.db, search_params)
        return ApiResponse.success(results)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


# ===============================================================================
# 최우선타겟 (Home.vue 매수추천 카드 select)
#   GET    /buy-target/priority  조회 — {stock_code, stock_name, set_ymd} 또는 전부 null
#   PUT    /buy-target/priority  지정 — body {ymd, stock_code}
#   DELETE /buy-target/priority  해제
# 본인 것만 다루므로 JWT 인증 필요(user_id 는 클라이언트가 보내지 않는다).
# ===============================================================================
@stocks_bp.route('/buy-target/priority', methods=['GET'])
@require_auth
def get_buy_target_priority():
    try:
        result = stockServiceImpl.get_priority_target(g.db, g.current_user_id)
        return ApiResponse.success(result)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


@stocks_bp.route('/buy-target/priority', methods=['PUT'])
@require_auth
def set_buy_target_priority():
    body = request.get_json(silent=True) or {}
    ymd = body.get(Literal.YMD)
    stock_code = body.get(Literal.STOCK_CODE)
    if not ymd or not stock_code:
        return ApiResponse.error("ymd, stock_code 는 필수입니다.", status=400)

    try:
        result = stockServiceImpl.set_priority_target(g.db, g.current_user_id, ymd, stock_code)
        return ApiResponse.success(result)
    except ValueError as e:
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


@stocks_bp.route('/buy-target/priority', methods=['DELETE'])
@require_auth
def clear_buy_target_priority():
    try:
        stockServiceImpl.clear_priority_target(g.db, g.current_user_id)
        return ApiResponse.success({'cleared': True})
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


"""
    StockInfo
    - 추천당시 종가
    - 현재 종가
    - 해당 기간 내 종가
"""
@stocks_bp.route('/rec-record')
def select_rec_recode_stock():
    search_params = {
        Literal.STOCK_CODE: request.args.get(Literal.STOCK_CODE)
    }

    try:
        results = stockServiceImpl.get_target_rec_record(g.db, search_params)

        return ApiResponse.success(results)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])

# STOCKS ROUTE :: SELECT BY ID
# ===============================================================================
@stocks_bp.route("/id/<stock_code>")
def select_stocks_by_id(stock_code):
    param = {
        'stock_code': stock_code
    }
    
    try:
        results = masterStockDaoImpl.select_master_stock_by_id(g.db, param);
        return ApiResponse.success(results)
    except Exception as e:
        print(str(e))
        return ApiResponse.error(str(e)[:255])
