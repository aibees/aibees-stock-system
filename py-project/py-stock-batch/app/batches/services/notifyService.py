"""
푸시 알림 발송 서비스 — common / user / role / broadcast 네 스코프를 지원한다.

- to_common(...) : 배치 시작/종료처럼 "특정 유저의 일이 아닌" 공통 운영 알림.
                   COMMON_NOTIFY_USER_ID(기본 1) 한 명에게만 보낸다.
- to_user(...)   : 특정 user_id (예: trade_worker 소유자 1명에게만)
- to_role(...)   : 특정 role(auth_id) 을 가진 유저 전체
- broadcast(...) : 전체 활성 디바이스 (현재는 /notify/test-send 수동 검증용)

세션은 이 서비스가 새로 만들지 않고 호출부가 넘긴 세션을 그대로 쓴다 —
job.py 훅에서 배치 자체가 이미 열어둔 세션 안에서 호출되기 때문(새 세션을
따로 열면 커넥션 풀을 불필요하게 더 쓰게 된다).

이 서비스의 public 메서드는 전부 예외를 삼키고 로그만 남긴다 — push 한 통
실패했다고 배치(job.py의 process())가 FAIL 로 떨어지면 안 되기 때문이다.
"""
import logging
import os

from stock_shared.dao.devicePushTokenDao import DevicePushTokenDao

from app.common.utils.pushUtils import pushUtils

log = logging.getLogger("push.notify")
# pushUtils.py 와 동일한 이유 — root 로거 레벨(ERROR)을 그대로 물려받아
# warning 로그(발송 실패 사유)까지 씹히는 걸 막기 위해 명시적으로 올려둔다.
log.setLevel(logging.INFO)

_dao = DevicePushTokenDao()

# 배치 시작/종료 같은 공통 운영 알림의 수신자. 전체 broadcast 로 보내면 자동매매와
# 무관한 일반 유저(및 비로그인 디바이스)에게까지 "배치 시작/종료" 가 쏟아지므로
# 운영자 1명(user_id=1)에게만 보낸다. 운영자 계정이 바뀌면 환경변수로 덮는다.
_DEFAULT_COMMON_NOTIFY_USER_ID = 1


def _common_notify_user_id() -> int:
    """COMMON_NOTIFY_USER_ID 환경변수(미설정/비정상이면 1). 값이 바뀌면 컨테이너
    재시작이 필요하다 — 이 프로젝트의 다른 환경변수와 동일한 제약."""
    raw = os.getenv("COMMON_NOTIFY_USER_ID")
    if not raw:
        return _DEFAULT_COMMON_NOTIFY_USER_ID
    try:
        return int(raw)
    except (TypeError, ValueError):
        log.warning("COMMON_NOTIFY_USER_ID 값이 정수가 아님(%r) → 기본값 %s 사용",
                    raw, _DEFAULT_COMMON_NOTIFY_USER_ID)
        return _DEFAULT_COMMON_NOTIFY_USER_ID


class NotifyService:
    def to_common(self, session, title: str, body: str, data: dict | None = None):
        """공통 운영 알림(배치 시작/종료/실패 등) — 운영자 1명에게만."""
        self.to_user(session, _common_notify_user_id(), title, body, data)

    def broadcast(self, session, title: str, body: str, data: dict | None = None):
        try:
            tokens = _dao.select_broadcast_tokens(session)
            self._send(tokens, title, body, data, session=session)
        except Exception as e:  # noqa: BLE001
            log.warning("broadcast push 실패: %s", e)

    def to_user(self, session, user_id: int, title: str, body: str, data: dict | None = None):
        try:
            tokens = _dao.select_tokens_by_user(session, user_id)
            self._send(tokens, title, body, data, session=session)
        except Exception as e:  # noqa: BLE001
            log.warning("user(%s) push 실패: %s", user_id, e)

    def to_role(self, session, role: str, title: str, body: str, data: dict | None = None):
        try:
            tokens = _dao.select_tokens_by_role(session, role)
            self._send(tokens, title, body, data, session=session)
        except Exception as e:  # noqa: BLE001
            log.warning("role(%s) push 실패: %s", role, e)

    def _send(self, tokens, title, body, data, session=None):
        if not tokens:
            return
        result = pushUtils.send_to_tokens(tokens, title, body, data)

        # 영구 실패(폐기/미등록/형식오류) 토큰은 DB에서 비활성화 — 안 하면 다음
        # 발송 때마다 같은 토큰이 계속 실패로 걸려서 로그만 쌓이고 낭비된다.
        invalid_tokens = (result or {}).get("invalid_tokens") or []
        if invalid_tokens and session is not None:
            for t in invalid_tokens:
                try:
                    _dao.deactivate_token(session, t)
                except Exception as e:  # noqa: BLE001
                    log.warning("무효 토큰 비활성화 실패: token=%s... %s", t[:12], e)
            log.info("무효 토큰 %d개 비활성화: %s", len(invalid_tokens),
                      [t[:12] + "..." for t in invalid_tokens])


notifyService = NotifyService()
