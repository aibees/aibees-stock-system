"""
router_access_log.py — 로그인·메뉴(화면) 접근 기록 (sql/37_user_access_log.sql)

    POST /api/v1/access-logs/menu  : 프런트 router.afterEach 가 화면 진입마다 보낸다(로그인 사용자만).
    GET  /api/v1/access-logs/login : 로그인/로그아웃 기록 조회 (AccessLogSetting.vue, ADMIN 전용)
    GET  /api/v1/access-logs/menu  : 메뉴 접근 기록 조회 (AccessLogSetting.vue, ADMIN 전용)
"""
from flask import Blueprint, request, g

from app.domains.dao.accessLogDao import AccessLogDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.routers.router_master import require_admin
from app.flask_app.utils.apiResponse import ApiResponse


accessLogDaoImpl = AccessLogDao()

access_log_bp = Blueprint("access_log", __name__)


@access_log_bp.route("/menu", methods=['POST'])
@require_auth
def log_menu_access():
    """
    Request : { "path": "/stock/sector", "menuCode": "StockSector" | null }
    Response: { "success": true, "data": null }  (기록 실패해도 성공 — 화면 이동과 무관)
    """
    data = request.get_json(silent=True) or {}
    path = str(data.get('path') or '').strip()
    if not path.startswith('/'):
        return ApiResponse.error("path 가 올바르지 않습니다.", status=400)
    menu_code = data.get('menuCode')
    accessLogDaoImpl.insert_menu_access_log(g.current_user_id, path.split('?')[0],
                                            str(menu_code) if menu_code else None)
    return ApiResponse.success(None)


def _page_args():
    page = max(int(request.args.get('page', 0) or 0), 0)
    size = int(request.args.get('size', 20) or 20)
    return page, size if size > 0 else 20


@access_log_bp.route("/login", methods=['GET'])
@require_admin
def select_login_log_list():
    """GET /api/v1/access-logs/login?page=&size=&loginType=&result=&keyword=&from=&to="""
    try:
        page, size = _page_args()
    except (TypeError, ValueError):
        return ApiResponse.error("page / size 파라미터는 숫자여야 합니다.", status=400)

    try:
        items, total = accessLogDaoImpl.select_login_log_page(
            g.db, page, size,
            login_type=request.args.get('loginType') or None,
            result=request.args.get('result') or None,
            keyword=request.args.get('keyword') or None,
            date_from=request.args.get('from') or None,
            date_to=request.args.get('to') or None,
        )
    except ValueError:
        return ApiResponse.error("from / to 기간 형식이 올바르지 않습니다.", status=400)

    total_pages = (total + size - 1) // size if size else 0
    return ApiResponse.success(items, extra={
        'totalPages': total_pages, 'totalElements': total, 'page': page, 'size': size,
    })


@access_log_bp.route("/menu", methods=['GET'])
@require_admin
def select_menu_access_log_list():
    """GET /api/v1/access-logs/menu?page=&size=&menuCode=&keyword=&from=&to="""
    try:
        page, size = _page_args()
    except (TypeError, ValueError):
        return ApiResponse.error("page / size 파라미터는 숫자여야 합니다.", status=400)

    try:
        items, total = accessLogDaoImpl.select_menu_access_log_page(
            g.db, page, size,
            menu_code=request.args.get('menuCode') or None,
            keyword=request.args.get('keyword') or None,
            date_from=request.args.get('from') or None,
            date_to=request.args.get('to') or None,
        )
    except ValueError:
        return ApiResponse.error("from / to 기간 형식이 올바르지 않습니다.", status=400)

    total_pages = (total + size - 1) // size if size else 0
    return ApiResponse.success(items, extra={
        'totalPages': total_pages, 'totalElements': total, 'page': page, 'size': size,
    })
