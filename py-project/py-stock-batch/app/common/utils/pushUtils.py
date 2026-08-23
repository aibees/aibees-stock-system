"""
FCM(Firebase Cloud Messaging) 푸시 발송 유틸 — telegramUtils.py 와 같은 위치/스타일.

firebase_admin 초기화는 lazy + 1회다. 이유:
  - 서비스 계정 키(JSON)는 배포 서버에만 있는 비밀 파일이라 저장소엔 없다.
    FCM_CREDENTIALS_PATH 환경변수로 경로만 받는다(.env / docker-compose 참고).
  - 이 모듈은 job.py 에서 배치 클래스마다 매번 import 되는데, 키 파일이 없는
    로컬 개발/CI 환경에서 import 시점에 죽어버리면 그 자체로 배치 전체가
    막힌다. 그래서 실제 send 호출 시점까지 초기화를 미루고, 그마저 실패하면
    로그만 남기고 조용히 skip 한다 — push 실패가 배치 실행을 막아선 안 된다.
"""
import logging
import os

log = logging.getLogger("push.fcm")
# job.py/runner.py 가 앱 부팅 시 logging.basicConfig(level=logging.ERROR) 를 걸어버려서
# (force=True 가 아니므로 root 레벨이 ERROR로 고정됨) 이 로거가 부모(root) 레벨을
# 그대로 물려받아 info/warning 로그가 전부 조용히 씹힌다. push 발송 성공/실패 여부를
# 로그로 확인할 수 있어야 하므로 이 로거만 명시적으로 INFO로 올려둔다.
log.setLevel(logging.INFO)

_app = None
_init_failed = False


def _get_app():
    global _app, _init_failed
    if _app is not None:
        return _app
    if _init_failed:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = os.getenv("FCM_CREDENTIALS_PATH")
        if not cred_path or not os.path.exists(cred_path):
            log.warning("FCM_CREDENTIALS_PATH 미설정/파일없음 → push 미발송")
            _init_failed = True
            return None

        cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred)
        return _app
    except Exception as e:  # noqa: BLE001
        log.warning("firebase_admin 초기화 실패(push 미발송): %s", e)
        _init_failed = True
        return None


class PushSender:
    def send_to_tokens(self, tokens: list, title: str, body: str, data: dict | None = None) -> dict:
        """토큰 목록에 개별 발송(send_each). 토큰 1개가 실패해도 나머지는 계속
        발송되며, 만료/미등록 토큰은 invalid_tokens 로 반환한다(호출부가 원하면
        DB 에서 비활성화하는 데 쓸 수 있음 — 지금은 로그만)."""
        app = _get_app()
        if app is None:
            return {"result": "skip", "reason": "firebase not initialized"}
        if not tokens:
            return {"result": "skip", "reason": "no tokens"}

        try:
            from firebase_admin import messaging
        except Exception as e:  # noqa: BLE001
            log.warning("firebase_admin.messaging import 실패: %s", e)
            return {"result": "fail", "msg": str(e)}

        messages = [
            messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in (data or {}).items()},
                token=t,
            )
            for t in tokens
        ]

        try:
            resp = messaging.send_each(messages, app=app)

            # 실패 원인을 알아야 진단이 되므로(success/failure 카운트만으로는 이유를 알 수 없음)
            # 실패한 응답마다 토큰 앞 12자 + 실제 예외 코드/메시지를 남긴다.
            for i, r in enumerate(resp.responses):
                if not r.success:
                    exc = getattr(r, "exception", None)
                    code = getattr(exc, "code", None)
                    http_resp = getattr(exc, "http_response", None)
                    err_body = None
                    if http_resp is not None:
                        try:
                            err_body = http_resp.text
                        except Exception:  # noqa: BLE001
                            err_body = None
                    log.warning(
                        "push 개별 발송 실패: token=%s... code=%s msg=%s body=%s",
                        tokens[i][:12], code, exc, err_body,
                    )

            # 영구적으로 다시 성공할 수 없는 토큰(폐기/미등록/형식오류)은 재시도해봐야
            # 계속 실패하므로 호출부(NotifyService)가 DB에서 비활성화할 수 있게 반환한다.
            # - NOT_FOUND/UNREGISTERED: 앱 삭제 등으로 APNs/FCM 쪽에서 폐기된 토큰
            # - INVALID_ARGUMENT: 애초에 FCM 토큰 형식이 아닌 값(예: 과거 iOS에서
            #   @capacitor/push-notifications 가 잘못 넘겼던 raw APNs hex token 잔재)
            PERMANENT_FAILURE_CODES = ("NOT_FOUND", "UNREGISTERED", "INVALID_ARGUMENT")
            invalid_tokens = [
                tokens[i]
                for i, r in enumerate(resp.responses)
                if not r.success and getattr(getattr(r, "exception", None), "code", None)
                in PERMANENT_FAILURE_CODES
            ]
            result = {
                "result": "success",
                "success": resp.success_count,
                "failure": resp.failure_count,
                "invalid_tokens": invalid_tokens,
            }
            log.info("push 발송 완료: success=%s failure=%s", resp.success_count, resp.failure_count)
            return result
        except Exception as e:  # noqa: BLE001
            log.warning("push 발송 실패: %s", e)
            return {"result": "fail", "msg": str(e)}


pushUtils = PushSender()
