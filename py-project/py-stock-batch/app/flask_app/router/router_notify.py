"""
푸시 디바이스 토큰 등록/해제 — Capacitor 앱이 FCM 토큰을 발급받으면 이
엔드포인트로 올린다(usePushNotifications.js 참고).

인증:
  /register 의 user_id·roles 는 이제 요청 본문이 아니라 accessToken 에서 정한다
  (app.flask_app.utils.auth). 예전엔 본문 값을 그대로 믿어서, 아무나 user_id=1 로 자기
  기기를 등록해 소유자의 체결 알림을 받을 수 있었다. 토큰이 없으면(비로그인) user_id=null
  로 등록되고, 이런 기기는 /test-send scope=broadcast 로 수동 발송할 때만 대상이 된다.
  /test-send 는 관리자만.
"""
from flask import Blueprint, g, request

from app.flask_app.utils.apiResponse import ApiResponse
from app.flask_app.utils.auth import optional_user, require_admin, user_auth_ids
from stock_shared.db.database import dbConn
from stock_shared.dao.devicePushTokenDao import DevicePushTokenDao
from app.batches.services.notifyService import notifyService

notify_bp = Blueprint("notify", __name__)
_dao = DevicePushTokenDao()


@notify_bp.route("/register", methods=["POST"])
@optional_user
def register_token():
    body = request.get_json(silent=True) or {}
    device_token = body.get("device_token")
    platform = body.get("platform")
    if not device_token or platform not in ("ios", "android"):
        return ApiResponse.error("device_token, platform(ios|android) 이 필요합니다.", status=400)

    # 본문의 user_id·roles 는 무시한다(옛 앱이 아직 보내지만 믿지 않는다).
    user_id = g.current_user_id

    session = dbConn.get_session()
    try:
        roles = user_auth_ids(session, user_id) if user_id is not None else []
        roles_csv = ",".join(roles) if roles else None
        _dao.upsert_token(session, {
            "device_token": device_token,
            "platform": platform,
            "user_id": user_id,
            "roles": roles_csv,
        })
        session.commit()
    except Exception as e:  # noqa: BLE001
        session.rollback()
        return ApiResponse.error(str(e), status=500)
    finally:
        session.remove()
    return ApiResponse.success(None)


@notify_bp.route("/unregister", methods=["POST"])
def unregister_token():
    body = request.get_json(silent=True) or {}
    device_token = body.get("device_token")
    if not device_token:
        return ApiResponse.error("device_token 이 필요합니다.", status=400)

    session = dbConn.get_session()
    try:
        _dao.deactivate_token(session, device_token)
        session.commit()
    except Exception as e:  # noqa: BLE001
        session.rollback()
        return ApiResponse.error(str(e), status=500)
    finally:
        session.remove()
    return ApiResponse.success(None)


@notify_bp.route("/test-send", methods=["POST"])
@require_admin
def test_send():
    """FCM 설정 확인용 수동 발송. scope: 'broadcast'(기본) | 'user' | 'role'.
    Firebase 콘솔/APNs 키 설정을 실제 배치를 기다리지 않고 바로 검증하는 용도."""
    body = request.get_json(silent=True) or {}
    scope = body.get("scope", "broadcast")
    title = body.get("title") or "테스트 알림"
    text = body.get("body") or "푸시 설정 테스트입니다."

    session = dbConn.get_session()
    try:
        if scope == "user":
            uid = body.get("user_id")
            if uid is None:
                return ApiResponse.error("scope=user 는 user_id 가 필요합니다.", status=400)
            notifyService.to_user(session, int(uid), title, text)
        elif scope == "role":
            role = body.get("role")
            if not role:
                return ApiResponse.error("scope=role 은 role 이 필요합니다.", status=400)
            notifyService.to_role(session, role, title, text)
        else:
            notifyService.broadcast(session, title, text)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    finally:
        session.remove()
    return ApiResponse.success(None)
