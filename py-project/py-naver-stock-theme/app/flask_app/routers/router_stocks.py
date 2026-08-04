import logging
import traceback, pprint
from flask import Blueprint, request, g

from stock_shared.dao.masterStockDao import MasterStockDao
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
