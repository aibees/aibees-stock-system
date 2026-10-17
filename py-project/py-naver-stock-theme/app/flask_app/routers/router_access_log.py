"""
router_access_log.py — 메뉴(화면) 접근 기록 (sql/37_user_access_log.sql)

    POST /api/v1/access-logs/menu : 프런트 router.afterEach 가 화면 진입마다 보낸다(로그인 사용자만).
"""
from flask import Blueprint, request, g

from app.domains.dao.accessLogDao import AccessLogDao
from app.flask_app.routers.router_oauth import require_auth
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
