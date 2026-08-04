"""
매수/매도 체결 알림 — 텔레그램 우선, 실패하면 이메일 fallback.

- 텔레그램: user_detail.tele_bot_id / tele_chat_id (telegramUtils, 파일 의존 없음)
- 이메일  : user_master.email (smtpUtils.emailUtils) — import 시 ./smtp.key 를 읽으므로 **lazy import**.
  worker 컨테이너에서 이메일 fallback 을 쓰려면 smtp.key 를 마운트해야 한다(compose 참고).

전송 우선순위: ① 텔레그램 성공 → 끝. ② 텔레그램 실패/미설정 → 이메일. ③ 둘 다 안 되면 로그만.
"""
import logging

from app.common.utils.telegramUtils import telegramUtils

log = logging.getLogger("trade_worker.notify")


class Notifier:
    def __init__(self, conf: dict | None, mode_tag: str = ""):
        conf = conf or {}
        self.bot = conf.get("tele_bot_id")
        self.chat = conf.get("tele_chat_id")
        self.email = conf.get("email")
        self.mode_tag = mode_tag

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

    def trade(self, kind: str, name: str, code: str, qty, price, balance, note: str = "") -> str | None:
        """체결 알림 포맷 후 전송. kind='BUY'|'SELL'."""
        icon = "🟢" if kind == "BUY" else "🔴"
        label = "매수" if kind == "BUY" else "매도"
        subject = f"[{label} 체결] {name}({code})"
        text = (f"{icon} <b>{label} 체결</b>  {name}({code})\n"
                f"수량 {qty} @ {price}\n"
                f"잔고 {balance}"
                + (f"\n{note}" if note else ""))
        return self.send(subject, text)
