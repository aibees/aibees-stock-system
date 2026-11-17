"""
worker 로그 로거 — 의미 있는 사건만 DB 테이블(trade_worker_log)에 남긴다.

2026-11-17 사용자 결정: 매 라운드 반복되는 진행 로그('후보 없음', '시작', '타겟 N건' 등)가 테이블을 채워
정작 봐야 할 기록이 묻혔다. DB 에는 아래 세 가지만 남기고, 나머지는 콘솔(docker logs)에만 찍는다.
    fill()       : 실제 매수/매도 체결 (완료·부분체결·잔량체결)
    setting()    : 설정값 변경 (운용모드 전환, 옵션 변경 감지·재적용, 최우선타겟 소비 초기화)
    limit_sync() : 지정가 동기화 (화면에서 등록·변경·해제한 수기 지정가 매도를 worker 가 반영)
info()/warn() 은 콘솔 전용이다(예전처럼 DB 에 쌓지 않는다).

- 모두 logging 과 같은 %-포맷 인자를 받는다.  예) wlog.fill("[매수] 완료 %s qty=%s", name, qty)
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

    # ── 콘솔 전용 ────────────────────────────────────────────────────
    def info(self, msg, *args):
        self._emit("INFO", msg, args, store=False)

    def warn(self, msg, *args):
        self._emit("WARN", msg, args, store=False)

    warning = warn  # logging 호환 별칭

    # ── DB 에도 남기는 사건 ───────────────────────────────────────────
    def fill(self, msg, *args):
        """실제 매수/매도 체결."""
        self._emit("INFO", msg, args, store=True)

    def setting(self, msg, *args, level: str = "INFO"):
        """설정값 변경(실패도 변경 시도라 남긴다 — level='WARN')."""
        self._emit(level, msg, args, store=True)

    def limit_sync(self, msg, *args):
        """수기 지정가 매도 등록·변경·해제 반영."""
        self._emit("INFO", msg, args, store=True)

    def _emit(self, level: str, msg, args, store: bool):
        try:
            text = (msg % args) if args else str(msg)
        except Exception:  # noqa: BLE001  (포맷 인자 불일치 방어)
            text = str(msg)
        if store:
            try:
                self.repo.insert_worker_log(self.user_id, self.source, level, text)
            except Exception as e:  # noqa: BLE001  (DB 실패가 매매를 막지 않도록)
                self._log.warning("worker log DB 기록 실패: %s (원문: %s)", e, text)
        if self.echo:
            self._log.log(logging.WARNING if level == "WARN" else logging.INFO, text)
