"""
worker 로그를 전용 DB 테이블(trade_worker_log)에 시간순으로 적재하는 로거.

매수/매도 executor 의 로그를 log.info 대신 이 로거로 남기면,
user_id·source(buy/sell)·level·message·created_at 이 DB 에 쌓여 시간대별 조회가 가능하다.

- info()/warn() 은 logging 과 동일하게 %-포맷 인자를 받는다.
  예) wlog.info("[매수] 완료 %s qty=%s", name, qty)
- DB 기록 실패해도 예외를 삼키고 콘솔로만 남긴다(매매 흐름 보호).
- echo=True 면 표준 logger 로도 출력(운영 가시성). 필요 시 False.
"""
import logging


class WorkerLogger:
    def __init__(self, repo, user_id: int, source: str, echo: bool = True):
        self.repo = repo
        self.user_id = user_id
        self.source = source                 # "buy" | "sell"
        self.echo = echo
        self._log = logging.getLogger(f"trade_worker.{source}")

    def info(self, msg, *args):
        self._emit("INFO", msg, args)

    def warn(self, msg, *args):
        self._emit("WARN", msg, args)

    warning = warn  # logging 호환 별칭

    def _emit(self, level: str, msg, args):
        try:
            text = (msg % args) if args else str(msg)
        except Exception:  # noqa: BLE001  (포맷 인자 불일치 방어)
            text = str(msg)
        try:
            self.repo.insert_worker_log(self.user_id, self.source, level, text)
        except Exception as e:  # noqa: BLE001  (DB 실패가 매매를 막지 않도록)
            self._log.warning("worker log DB 기록 실패: %s (원문: %s)", e, text)
        if self.echo:
            self._log.log(logging.WARNING if level == "WARN" else logging.INFO, text)
