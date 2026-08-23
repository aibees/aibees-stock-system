"""
푸시 알림 발송 서비스 — broadcast / user / role 세 스코프를 지원한다.
(요청: "전체 broadcast + 권한과 worker 소유자에 따라 달라지는 것도 포함")

- broadcast(...) : 전체 활성 디바이스
- to_user(...)   : 특정 user_id (예: trade_worker 소유자 1명에게만)
- to_role(...)   : 특정 role(auth_id) 을 가진 유저 전체

세션은 이 서비스가 새로 만들지 않고 호출부가 넘긴 세션을 그대로 쓴다 —
job.py 훅에서 배치 자체가 이미 열어둔 세션 안에서 호출되기 때문(새 세션을
따로 열면 커넥션 풀을 불필요하게 더 쓰게 된다).

이 서비스의 public 메서드는 전부 예외를 삼키고 로그만 남긴다 — push 한 통
실패했다고 배치(job.py의 process())가 FAIL 로 떨어지면 안 되기 때문이다.
"""
import logging

from stock_shared.dao.devicePushTokenDao import DevicePushTokenDao

from app.common.utils.pushUtils import pushUtils

log = logging.getLogger("push.notify")
# pushUtils.py 와 동일한 이유 — root 로거 레벨(ERROR)을 그대로 물려받아
# warning 로그(발송 실패 사유)까지 씹히는 걸 막기 위해 명시적으로 올려둔다.
log.setLevel(logging.INFO)

_dao = DevicePushTokenDao()


class NotifyService:
    def broadcast(self, session, title: str, body: str, data: dict | None = None):
        try:
            tokens = _dao.select_broadcast_tokens(session)
            self._send(tokens, title, body, data)
        except Exception as e:  # noqa: BLE001
            log.warning("broadcast push 실패: %s", e)

    def to_user(self, session, user_id: int, title: str, body: str, data: dict | None = None):
        try:
            tokens = _dao.select_tokens_by_user(session, user_id)
            self._send(tokens, title, body, data)
        except Exception as e:  # noqa: BLE001
            log.warning("user(%s) push 실패: %s", user_id, e)

    def to_role(self, session, role: str, title: str, body: str, data: dict | None = None):
        try:
            tokens = _dao.select_tokens_by_role(session, role)
            self._send(tokens, title, body, data)
        except Exception as e:  # noqa: BLE001
            log.warning("role(%s) push 실패: %s", role, e)

    def _send(self, tokens, title, body, data):
        if not tokens:
            return
        pushUtils.send_to_tokens(tokens, title, body, data)


notifyService = NotifyService()
