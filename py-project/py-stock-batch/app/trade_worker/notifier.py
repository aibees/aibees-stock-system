"""
매수/매도 체결 알림 — 텔레그램 우선, 실패하면 이메일 fallback.

- 텔레그램: user_detail.tele_bot_id / tele_chat_id (telegramUtils, 파일 의존 없음)
- 이메일  : user_master.email (smtpUtils.emailUtils) — import 시 ./smtp.key 를 읽으므로 **lazy import**.
  worker 컨테이너에서 이메일 fallback 을 쓰려면 smtp.key 를 마운트해야 한다(compose 참고).

전송 우선순위: ① 텔레그램 성공 → 끝. ② 텔레그램 실패/미설정 → 이메일. ③ 둘 다 안 되면 로그만.

push(FCM)는 위 우선순위와 **별개로 항상** 나가는 별도 채널이다(텔레그램이 성공해도 보냄).
  - trade(...) : 매수/매도 체결
  - alert(...) : 운영 경보(외부청산 등) — send() 만 쓰는 호출부는 push 가 안 나간다.
둘 다 worker 소유자(user_id) 1명 스코프다.
"""
import logging
import re

from app.common.utils.telegramUtils import telegramUtils
# 체결/경보 push — worker 소유자(user_id) 1명에게만 보낸다.
# get_session()은 job.py 가 쓰는 것과 같은 dbConn(stock_shared.db.database)을 감싼
# contextmanager 라 커넥션 풀을 새로 만들지 않는다.
from stock_shared.db.contextManager import get_session
from app.batches.services.notifyService import notifyService

log = logging.getLogger("trade_worker.notify")

# 텔레그램 본문은 parse_mode=HTML 이라 <b> 등이 섞여 있다. push 는 OS 배너에 평문으로
# 뜨므로 태그가 그대로 보이면 안 된다 — push 본문을 따로 주지 않은 경우에만 쓴다.
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    return _TAG_RE.sub("", text or "")


class Notifier:
    def __init__(self, conf: dict | None, mode_tag: str = "", user_id: int | None = None):
        conf = conf or {}
        self.bot = conf.get("tele_bot_id")
        self.chat = conf.get("tele_chat_id")
        self.email = conf.get("email")
        self.mode_tag = mode_tag
        # [추가] push 발송 대상 — 이 worker 가 담당하는 유저 1명.
        self.user_id = user_id

    def send(self, subject: str, text: str) -> str | None:
        """텔레그램 → 이메일 순서로 시도. 성공 채널명('telegram'|'email') 또는 None 반환."""
        prefix = f"[{self.mode_tag}] " if self.mode_tag else ""
        body = prefix + text

        # ① 텔레그램
        if self.bot and self.chat:
            r = telegramUtils.sendMessage(self.bot, self.chat, body)
            if r.get("result") == "success":
                log.info("알림 텔레그램 전송 성공")
                return "telegram"
            log.warning("텔레그램 전송 실패(%s) → 이메일 fallback", r.get("msg"))
        else:
            log.info("텔레그램 미설정 → 이메일 fallback")

        # ② 이메일 fallback
        if self.email:
            try:
                from app.common.utils.smtpUtils import emailUtils  # lazy: ./smtp.key 의존
                r = emailUtils.sendMail(subject=prefix + subject,
                                        body=body.replace("\n", "<br>"),
                                        receipt=self.email)
                if r.get("result") == "success":
                    log.info("알림 이메일 전송 성공 → %s", self.email)
                    return "email"
                log.warning("이메일 전송 실패: %s", r.get("msg"))
            except Exception as e:  # noqa: BLE001  (smtp.key 미마운트 등)
                log.warning("이메일 발송 불가(smtp.key/설정 확인): %s", e)
        else:
            log.info("이메일도 미설정 → 알림 skip")

        return None

    def _push(self, title: str, body: str, data: dict | None = None) -> None:
        """worker 소유자(user_id) 1명에게 push. 실패해도 매매/대조 흐름을 절대
        막으면 안 되므로 통째로 감싼다(notifyService.to_user 내부에서도 이미
        예외를 삼키지만 이중 방어)."""
        if not self.user_id:
            return
        try:
            with get_session() as s:
                notifyService.to_user(s, self.user_id, title, body, data)
        except Exception as e:  # noqa: BLE001
            log.warning("push 실패(%s): %s", title, e)

    def alert(self, subject: str, text: str, push_body: str | None = None,
              data: dict | None = None) -> str | None:
        """운영 경보 — send(텔레그램/이메일) + worker 소유자 push.

        체결(trade)과 달리 포맷이 자유로운 경보용이다. push 본문을 text 로
        그대로 쓰지 않고 push_body 를 따로 받는 이유는, 텔레그램 본문은 여러 줄
        + HTML 태그 + 조치 안내까지 길게 쓰는데 push 는 OS 배너 한두 줄로
        잘리기 때문. 생략하면 text 에서 태그만 떼어 쓴다."""
        channel = self.send(subject, text)
        self._push(subject, push_body or _strip_tags(text), data)
        return channel

    def trade(self, kind: str, name: str, code: str, qty, price, balance, note: str = "") -> str | None:
        """체결 알림 포맷 후 전송. kind='BUY'|'SELL'.
        텔레그램/이메일(send)과 별개로, worker 소유자에게 push 도 보낸다
        (운영자 1명에게 가는 배치 시작/종료 push 와 달리 이건 worker 소유자 스코프)."""
        icon = "🟢" if kind == "BUY" else "🔴"
        label = "매수" if kind == "BUY" else "매도"
        subject = f"[{label} 체결] {name}({code})"
        text = (f"{icon} <b>{label} 체결</b>  {name}({code})\n"
                f"수량 {qty} @ {price}\n"
                f"잔고 {balance}"
                + (f"\n{note}" if note else ""))
        channel = self.send(subject, text)
        self._push(f"{label} 체결",
                   f"{name}({code}) {qty}주 @{price} · 잔고 {balance}",
                   {"event": "TRADE", "kind": kind, "stock_code": code})
        return channel
