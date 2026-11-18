"""
앱 내 알림함(user_notification) + FCM 푸시 — 양봉상회 전용(sql/yangbong/008).

알림함 기록이 먼저고 푸시는 덤이다. 푸시가 실패해도(키 없음·토큰 만료) 알림함에는 남아 있으므로
호출자에게 예외를 올리지 않는다. 다시는 성공할 수 없는 토큰은 비활성화한다.
"""
import logging

from app.domains.dao.stockAiJobDao import UserNotificationDao
from stock_shared.dao.devicePushTokenDao import DevicePushTokenDao
from stock_shared.push.fcm import pushUtils

logger = logging.getLogger(__name__)


class NotificationService:

    def __init__(self):
        self._dao = UserNotificationDao()
        self._tokenDao = DevicePushTokenDao()

    # ── 조회·읽음 (API) ─────────────────────────────────────
    def list(self, session, user_id, page: int, size: int) -> dict:
        rows, total = self._dao.list(session, user_id, page, size)
        return {
            "items": rows,
            "total": total,
            "unread_count": self._dao.count_unread(session, user_id),
        }

    def unread_count(self, session, user_id) -> int:
        return self._dao.count_unread(session, user_id)

    def mark_read(self, session, user_id, notification_id) -> int:
        n = self._dao.mark_read(session, user_id, notification_id)
        session.commit()
        return n

    def mark_all_read(self, session, user_id) -> int:
        n = self._dao.mark_all_read(session, user_id)
        session.commit()
        return n

    # ── 보내기 (AI 워커) ────────────────────────────────────
    def notify(self, session, user_ids, type_, title, body, link=None, ref_id=None):
        """user_ids 각각에게 알림함 1행 + 푸시. 알림함은 커밋까지 하고, 푸시 실패는 로그만."""
        user_ids = sorted({int(u) for u in user_ids if u is not None})
        if not user_ids:
            return
        for uid in user_ids:
            self._dao.insert(session, uid, type_, title, body=body, link=link, ref_id=ref_id)
        session.commit()

        try:
            tokens = []
            for uid in user_ids:
                tokens.extend(self._tokenDao.select_tokens_by_user(session, uid))
            if not tokens:
                return
            data = {"type": type_}
            if link:
                data["link"] = link
            if ref_id is not None:
                data["ref_id"] = ref_id
            result = pushUtils.send_to_tokens(tokens, title, body or "", data)
            for t in result.get("invalid_tokens") or []:
                self._tokenDao.deactivate_token(session, t)
            session.commit()
        except Exception as e:  # noqa: BLE001 — 푸시는 실패해도 알림함에 남아 있다
            session.rollback()
            logger.warning(f"[notify] 푸시 실패(알림함에는 기록됨) users={user_ids}: {e}")
