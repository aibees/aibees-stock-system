"""
푸시 디바이스 토큰 등록/해제 — Capacitor 앱이 FCM 토큰을 발급받으면 이
엔드포인트로 올린다(usePushNotifications.js 참고).

인증 관련 주의 (router_auto_trade.py 와 동일):
  이 Flask 앱에는 JWT 디코드/사용자 식별 미들웨어가 전혀 없다. user_id/roles 는
  프런트가 로그인 세션에서 그대로 실어보낸다 — 이 앱의 기존 보안 수준(무인증
  내부망 batch-admin 서비스)을 그대로 따른다. 비로그인 상태(user_id=null)로도
  등록할 수 있게 허용한 이유는 "전체 broadcast" 요구사항 때문 — 로그인 여부와
  무관하게 배치 시작/종료 알림 정도는 받을 수 있어야 한다.
"""
from flask import Blueprint, request

from app.flask_app.utils.apiResponse import ApiResponse
from app.config.database import dbConn
from stock_shared.dao.devicePushTokenDao import DevicePushTokenDao
from app.batches.services.notifyService import notifyService

notify_bp = Blueprint("notify", __name__)
_dao = DevicePushTokenDao()


@notify_bp.route("/register", methods=["POST"])
def register_token():
    body = request.get_json(silent=True) or {}
    device_token = body.get("device_token")
    platform = body.get("platform")
    if not device_token or platform not in ("ios", "android"):
        return ApiResponse.error("device_token, platform(ios|android) 이 필요합니다.", status=400)

    raw_user_id = body.get("user_id")
    try:
        user_id = int(raw_user_id) if raw_user_id not in (None, "") else None
    except (TypeError, ValueError):
        user_id = None

    roles = body.get("roles")
    roles_csv = ",".join(str(r) for r in roles) if isinstance(roles, list) and roles else None

    session = dbConn.get_session()
    try:
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
