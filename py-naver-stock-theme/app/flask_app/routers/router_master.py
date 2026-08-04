import threading
import datetime
from datetime import datetime
from flask import Blueprint, request, g

from app.domains.dao.masterStockDao import MasterStockDao
from app.domains.dao.masterMenuDao import MasterInfosDao
from app.flask_app.utils.apiResponse import ApiResponse

master_bp = Blueprint("master", __name__)
masterMenuDaoImpl = MasterInfosDao()
masterStockDaoImpl = MasterStockDao()

# MASTER ROUTE ROOT :: TEST
# ===============================================================================
@master_bp.route("/")
def master_index():
    return {
        'msg': 'aibees flask :: master home'
    }
    
@master_bp.route("/menus")
def select_master_menu_list():
    result_list = []
    search_params = {
        'enabled_flag': request.args.get('enabled_flag') or '',
        'display_flag': request.args.get('display_flag') or ''
    }
    results = masterMenuDaoImpl.select_master_menu_all(g.db, search_params)
    
    roots = []
    stores = {}
    
    for item in results:
        prt = item['menu_parents']
        if prt in stores:
            arr = stores[prt]
            arr.append(item)
            stores[prt] = arr
        elif prt == 'root':
            roots.append(item)
        else:
            stores[prt] = [item]
            
    for r in roots:
        code = r['menu_code']
        
        if code in stores:
            child = stores[code]
            
            r['children'] = sorted(child, key=lambda x: x['sort'])
        
        result_list.append(r)
    return ApiResponse.success(sorted(result_list, key=lambda x: x['sort']))

@master_bp.route("/menus/head")
def select_master_menu_master():
    search_params = {
        'menu_code': (request.args.get('menuCode') or '').replace(' ', '%').upper(),
        'menu_title': (request.args.get('menuTitle') or '')
    }
    
    try :
        return ApiResponse.success(sorted(masterMenuDaoImpl.select_master_menu_root(g.db, search_params), key=lambda x: x['sort']))
    except Exception as e:
        return ApiResponse.error(e.__cause__)

@master_bp.route("/menus", methods=['POST'])
def insert_master_menu():
    data = request.get_json()
    try:
        masterMenuDaoImpl.insert_master_menu(g.db, data)
        return ApiResponse.success(None)
    except Exception as e:
        return ApiResponse.error(e.__cause__)

@master_bp.route("/menus/<menu_code>", methods=['PUT'])
def update_master_menu(menu_code):
    data = request.get_json()
    data['menu_code'] = menu_code
    try:
        masterMenuDaoImpl.update_master_key(g.db, data)
        return ApiResponse.success(None)
    except Exception as e:
        return ApiResponse.error(e.__cause__)

@master_bp.route("/menus/<menu_code>", methods=['PATCH'])
def patch_menu_enabled(menu_code):
    params = {
        'menu_code': menu_code
    }
    try:
        return ApiResponse.success(masterMenuDaoImpl.fetch_menu_enabled(g.db, params))
    except Exception as e:
        return ApiResponse.error(e.__cause__)

@master_bp.route("/menus/sub")
def select_master_menu_sub():
    search_params = {
        'menu_parents': (request.args.get('menuParents') or '')
    }
    
    try :
        return ApiResponse.success(masterMenuDaoImpl.select_master_menu_sub(g.db, search_params))
    except Exception as e:
        return ApiResponse.error(e.__cause__)
    
@master_bp.route("/menus/sub/<menu_code>")
def select_master_menu_by_id(menu_code):
    search_params = {
        'menu_code': menu_code
    }
    
    try :
        return ApiResponse.success(masterMenuDaoImpl.select_master_menu_by_id(g.db, search_params))
    except Exception as e:
        return ApiResponse.error(e.__cause__)
    