from flask import Blueprint, request, g

from app.flask_app.utils.apiResponse import ApiResponse
from app.domains.dao.masterCodesDao import MasterCodesDao

common_bp = Blueprint('common-codes', __name__)

masterCodesDaoImpl = MasterCodesDao()

def select_common_code(session, param):
    return masterCodesDaoImpl.select_master_code(session, param)

@common_bp.route("/category")
def select_common_code_category():
    search_param = {
        'system': request.args.get('system'),
        'source': request.args.get('source'),
        'category': request.args.get('category')
    }

    try :
        return ApiResponse.success(select_common_code(g.db, search_param))
    except Exception as e:
        return ApiResponse.error(str(e))
    
@common_bp.route("/no-reason")
def select_common_code_noreason():
    search_param = {
        'system': request.args.get('system'),
        'source': request.args.get('source'),
        'category': request.args.get('category')
    }

    try :
        return ApiResponse.success(select_common_code(g.db, search_param))
    except Exception as e:
        return ApiResponse.error(str(e))