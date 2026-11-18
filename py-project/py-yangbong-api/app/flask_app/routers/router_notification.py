"""
앱 내 알림함 + 푸시 토큰 등록 — 양봉상회 전용 (sql/yangbong/008)

notification_bp (url_prefix = /api/v1/notifications), 모두 로그인 필요
  GET   ?page=0&size=20       → {items:[…], total, unread_count}
  GET   /unread-count         → {unread_count}
  PATCH /<id>/read            → 읽음
  POST  /read-all             → 모두 읽음

notify_bp (url_prefix = /api/v1/notify) — 예전엔 비밀상회 배치 서버(py-stock-batch)로 갔다.
  POST /register   {device_token, platform: ios|android}  → yangbong.device_push_token
       로그인 상태면 토큰의 user_id 를 accessToken 에서 정한다(본문의 user_id 는 믿지 않는다).
       비로그인이면 user_id 없이 등록한다(로그인하면 앱이 다시 올린다).
  POST /unregister {device_token}
"""
import logging

from flask import Blueprint, g, request

from web_shared.auth.decorators import optional_auth
from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse
from app.services.common.notificationService import NotificationService
from stock_shared.dao.devicePushTokenDao import DevicePushTokenDao

logger = logging.getLogger(__name__)

notification_bp = Blueprint("notification", __name__)
notify_bp = Blueprint("notify", __name__)

notificationServiceImpl = NotificationService()
_tokenDao = DevicePushTokenDao()

MAX_PAGE_SIZE = 50


@notification_bp.route("", methods=["GET"])
@require_auth
def list_notifications():
    try:
        page = max(0, int(request.args.get("page", 0)))
        size = min(MAX_PAGE_SIZE, max(1, int(request.args.get("size", 20))))
    except ValueError:
        return ApiResponse.error("page·size 는 숫자여야 합니다.")
    try:
        return ApiResponse.success(notificationServiceImpl.list(g.db, g.current_user_id, page, size))
    except Exception as e:  # noqa: BLE001
        logger.error(f"[notification] list: {e}", exc_info=True)
        return ApiResponse.error("알림을 불러오지 못했어요.", status=500)


@notification_bp.route("/unread-count", methods=["GET"])
@require_auth
def unread_count():
    try:
        return ApiResponse.success({"unread_count": notificationServiceImpl.unread_count(g.db, g.current_user_id)})
    except Exception as e:  # noqa: BLE001
        logger.error(f"[notification] unread-count: {e}", exc_info=True)
        return ApiResponse.error("알림을 불러오지 못했어요.", status=500)


@notification_bp.route("/<int:notification_id>/read", methods=["PATCH"])
@require_auth
def read_one(notification_id):
    try:
        notificationServiceImpl.mark_read(g.db, g.current_user_id, notification_id)
        return ApiResponse.success(None)
    except Exception as e:  # noqa: BLE001
        g.db.rollback()
        logger.error(f"[notification] read {notification_id}: {e}", exc_info=True)
        return ApiResponse.error("읽음 처리를 하지 못했어요.", status=500)


@notification_bp.route("/read-all", methods=["POST"])
@require_auth
def read_all():
    try:
        return ApiResponse.success({"updated": notificationServiceImpl.mark_all_read(g.db, g.current_user_id)})
    except Exception as e:  # noqa: BLE001
        g.db.rollback()
        logger.error(f"[notification] read-all: {e}", exc_info=True)
        return ApiResponse.error("읽음 처리를 하지 못했어요.", status=500)


@notify_bp.route("/register", methods=["POST"])
@optional_auth
def register_token():
    body = request.get_json(silent=True) or {}
    device_token = body.get("device_token")
    platform = body.get("platform")
    if not device_token or platform not in ("ios", "android"):
        return ApiResponse.error("device_token, platform(ios|android) 이 필요합니다.", status=400)
    try:
        _tokenDao.upsert_token(g.db, {
            "device_token": device_token,
            "platform": platform,
            "user_id": g.current_user_id,
            "roles": None,   # 양봉상회는 역할별 발송이 없다
        })
        g.db.commit()
    except Exception as e:  # noqa: BLE001
        g.db.rollback()
        logger.error(f"[notify] register: {e}", exc_info=True)
        return ApiResponse.error("알림 등록을 하지 못했어요.", status=500)
    return ApiResponse.success(None)


@notify_bp.route("/unregister", methods=["POST"])
def unregister_token():
    body = request.get_json(silent=True) or {}
    device_token = body.get("device_token")
    if not device_token:
        return ApiResponse.error("device_token 이 필요합니다.", status=400)
    try:
        _tokenDao.deactivate_token(g.db, device_token)
        g.db.commit()
    except Exception as e:  # noqa: BLE001
        g.db.rollback()
        logger.error(f"[notify] unregister: {e}", exc_info=True)
        return ApiResponse.error("알림 해제를 하지 못했어요.", status=500)
    return ApiResponse.success(None)
