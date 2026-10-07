import re
import threading
import datetime
from datetime import datetime
from flask import Blueprint, request, g

from stock_shared.dao.masterStockDao import MasterStockDao
from functools import wraps

from app.domains.dao.masterMenuDao import MasterInfosDao
from app.domains.dao.roleMenuDao import RoleMenuDao, ADMIN_AUTH_ID, is_super_user
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

master_bp = Blueprint("master", __name__)
masterMenuDaoImpl = MasterInfosDao()
masterStockDaoImpl = MasterStockDao()
roleMenuDaoImpl = RoleMenuDao()


def require_admin(f):
    """ADMIN 권한 사용자만 통과. JWT 검증(@require_auth)을 포함한다."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        auth_ids = roleMenuDaoImpl.select_user_auth_ids(g.db, g.current_user_id)
        if ADMIN_AUTH_ID not in auth_ids:
            return ApiResponse.error("관리자 권한이 필요합니다.", status=403)
        return f(*args, **kwargs)
    return decorated

def optional_auth(f):
    """토큰이 없으면 게스트(g.current_user_id=None)로 통과, 있으면 @require_auth 와 동일하게 검증.

    토큰이 있는데 만료/위조면 401 이 나가야 프런트의 silent refresh 가 동작한다
    (게스트로 조용히 강등하면 로그인 사용자의 메뉴가 사라진 채 새로고침 루프가 생긴다).
    """
    authed = require_auth(f)

    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.headers.get('Authorization', '').startswith('Bearer '):
            g.current_user_id = None
            return f(*args, **kwargs)
        return authed(*args, **kwargs)
    return decorated


def require_super(f):
    """슈퍼유저(SUPER_USER_IDS, 기본 user_id=1)만 통과. JWT 검증을 포함한다."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not is_super_user(g.current_user_id):
            return ApiResponse.error("권한이 없습니다.", status=403)
        return f(*args, **kwargs)
    return decorated


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
    


# ROLE ↔ MENU 권한 매핑
# ===============================================================================
@master_bp.route("/menus/my")
@optional_auth
def select_my_menu_list():
    """접근 가능한 메뉴 트리 + 기능 플래그. 비로그인(토큰 없음)이면 공개 메뉴(public_flag)만.

    - 메뉴: ADMIN 전체 / 그 외 common_flag='Y' 또는 role_menu 매핑(리프). 부모는 보이는
      자식이 있거나 common_flag='Y' 일 때만 노출(파생).
    - 기능(features): ADMIN 도 role_feature 에 명시된 것만(AD_FREE 등).
    - master_menu.admin_only 는 이 API 에서 더 이상 보지 않는다(role_menu 로 대체).
    """
    user_id = g.current_user_id
    search_params = {
        'enabled_flag': request.args.get('enabled_flag') or 'Y',
        'display_flag': request.args.get('display_flag') or ''
    }
    auth_ids = roleMenuDaoImpl.select_user_auth_ids(g.db, user_id) if user_id is not None else []
    rows = roleMenuDaoImpl.select_menus_for_user(g.db, user_id, auth_ids, search_params)
    is_admin = ADMIN_AUTH_ID in auth_ids

    children_of = {}
    roots = []
    for item in rows:
        if item['menu_parents'] == 'root':
            roots.append(item)
        else:
            children_of.setdefault(item['menu_parents'], []).append(item)

    tree = []
    for r in roots:
        kids = sorted(children_of.get(r['menu_code'], []), key=lambda x: x['sort'])
        if kids:
            r['children'] = kids
        if kids or r['common_flag'] == 'Y' or r['public_flag'] == 'Y' or is_admin:
            tree.append(r)

    return ApiResponse.success({
        'menus': sorted(tree, key=lambda x: x['sort']),
        'features': roleMenuDaoImpl.select_features_for_user(g.db, auth_ids),
        'roles': auth_ids,
    })


@master_bp.route("/roles")
@require_admin
def select_role_list():
    return ApiResponse.success(roleMenuDaoImpl.select_role_list(g.db))


# 권한 ID 는 코드·SQL·환경변수에서 그대로 쓰이므로 대문자 식별자로 제한한다.
AUTH_ID_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]{1,63}$')


@master_bp.route("/roles", methods=['POST'])
@require_admin
def insert_role():
    """권한 생성. body: { "auth_id": "TRADE_USER", "auth_nm": "자동매매 사용자" }"""
    body = request.get_json(silent=True) or {}
    auth_id = str(body.get('auth_id') or '').strip().upper()
    auth_nm = str(body.get('auth_nm') or '').strip()
    if not AUTH_ID_PATTERN.match(auth_id):
        return ApiResponse.error("권한 ID 는 영문 대문자로 시작하고 대문자·숫자·_ 만 쓸 수 있습니다(2~64자).", status=400)
    if not auth_nm or len(auth_nm) > 200:
        return ApiResponse.error("권한 이름(1~200자)이 필요합니다.", status=400)
    if roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("이미 있는 권한 ID 입니다.", status=409)
    roleMenuDaoImpl.insert_role(g.db, auth_id, auth_nm)
    return ApiResponse.success({'auth_id': auth_id, 'auth_nm': auth_nm, 'user_count': 0})


@master_bp.route("/roles/<auth_id>", methods=['PUT'])
@require_admin
def update_role(auth_id):
    """권한 이름 변경. ID 는 매핑/부여의 키라 바꾸지 않는다. body: { "auth_nm": "..." }"""
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    auth_nm = str((request.get_json(silent=True) or {}).get('auth_nm') or '').strip()
    if not auth_nm or len(auth_nm) > 200:
        return ApiResponse.error("권한 이름(1~200자)이 필요합니다.", status=400)
    roleMenuDaoImpl.update_role_name(g.db, auth_id, auth_nm)
    return ApiResponse.success(None)


@master_bp.route("/roles/<auth_id>", methods=['DELETE'])
@require_admin
def delete_role(auth_id):
    """권한 삭제. ADMIN 은 불가, 부여 중인 사용자가 있으면 먼저 회수해야 한다
    (사용자의 메뉴가 예고 없이 사라지는 것을 막는다)."""
    if auth_id == ADMIN_AUTH_ID:
        return ApiResponse.error("ADMIN 권한은 삭제할 수 없습니다.", status=400)
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    users = roleMenuDaoImpl.count_role_users(g.db, auth_id)
    if users:
        return ApiResponse.error(f"이 권한을 가진 사용자가 {users}명 있습니다. 사용자 권한 부여 화면에서 먼저 회수하세요.", status=409)
    roleMenuDaoImpl.delete_role(g.db, auth_id)
    return ApiResponse.success(None)


@master_bp.route("/roles/<auth_id>/menus")
@require_admin
def select_role_menus(auth_id):
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    return ApiResponse.success(roleMenuDaoImpl.select_role_menu_codes(g.db, auth_id))


@master_bp.route("/roles/<auth_id>/menus", methods=['PUT'])
@require_admin
def replace_role_menus(auth_id):
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    body = request.get_json(silent=True) or {}
    codes = body.get('menu_codes')
    if not isinstance(codes, list):
        return ApiResponse.error("menu_codes 배열이 필요합니다.", status=400)
    return ApiResponse.success(roleMenuDaoImpl.replace_role_menus(g.db, auth_id, codes))


@master_bp.route("/roles/<auth_id>/features")
@require_admin
def select_role_features(auth_id):
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    return ApiResponse.success(roleMenuDaoImpl.select_role_feature_codes(g.db, auth_id))


@master_bp.route("/roles/<auth_id>/features", methods=['PUT'])
@require_admin
def replace_role_features(auth_id):
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    body = request.get_json(silent=True) or {}
    codes = body.get('feature_codes')
    if not isinstance(codes, list):
        return ApiResponse.error("feature_codes 배열이 필요합니다.", status=400)
    return ApiResponse.success(roleMenuDaoImpl.replace_role_features(g.db, auth_id, codes))


# 사용자별 권한 부여 (슈퍼유저 전용)
# ===============================================================================
@master_bp.route("/admin/users")
@require_super
def select_users_with_roles():
    """사용자 목록 + 각자의 권한, 부여 가능한 권한(role) 목록."""
    return ApiResponse.success({
        'users': roleMenuDaoImpl.select_users_with_roles(g.db, request.args.get('keyword')),
        'roles': roleMenuDaoImpl.select_role_list(g.db),
    })


@master_bp.route("/admin/users/<int:user_id>/roles/<auth_id>", methods=['PUT'])
@require_super
def set_user_role(user_id, auth_id):
    """권한 부여/회수. body: { "enabled": true|false }"""
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get('enabled'), bool):
        return ApiResponse.error("enabled(true/false) 가 필요합니다.", status=400)
    enabled = body['enabled']

    if not roleMenuDaoImpl.user_exists(g.db, user_id):
        return ApiResponse.error("존재하지 않는 사용자입니다.", status=404)
    if not roleMenuDaoImpl.role_exists(g.db, auth_id):
        return ApiResponse.error("존재하지 않는 권한입니다.", status=404)
    # 본인의 ADMIN 을 실수로 회수해 관리 화면에서 스스로 잠기는 것을 막는다.
    if not enabled and auth_id == ADMIN_AUTH_ID and user_id == g.current_user_id:
        return ApiResponse.error("본인의 ADMIN 권한은 회수할 수 없습니다.", status=400)

    roleMenuDaoImpl.set_user_role(g.db, user_id, auth_id, enabled)
    return ApiResponse.success(None)
