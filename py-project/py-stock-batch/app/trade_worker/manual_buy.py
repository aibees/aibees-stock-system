"""
수동 매수 실행기 — trade_worker_manual_buy(sql/50_manual_buy.sql) 를 폴링해 KIS 로 주문한다.

사용자가 화면에서 고른 종목·수량을 그대로 낸다. 추천·매수 게이트·1포지션 원칙을 보지 않고,
매매정지(HALT)여도 주문이 나간다(Broker.manual_buy 만 HALT 게이트를 건너뛴다).

주문은 한 번만 나간다:
  REQUESTED → claim(상태 조건 UPDATE) → ORDERING → 주문 → OPEN.
  주문 도중 오류·재시작이면 거래소 접수 여부를 알 수 없으므로 UNKNOWN 으로 두고 재주문하지 않는다.
  오래된 요청(REQUEST_TTL_SEC)은 주문하지 않는다 — worker 가 꺼져 있던 동안의 요청이 재기동 후 나가면 안 된다.

체결 후 처리는 HTS 매수와 같은 경로를 탄다:
  executor 가 watch 를 등록하지 않으므로 체결통보는 main._on_external_fill → reconcile_wallet 으로 가고,
  계좌 동기화가 포지션 편입(또는 수량 보정)과 초기 라인 설정을 한다. 이후 매도는 운용모드 규칙을 따른다.
  다음 날 09:00 자동매수도 평소처럼 계좌 보유 여부만 본다.

% 수량(qty_pct)은 주문 직전 KIS 주문가능수량 기준으로 확정한다. 조회가 안 되면 수량을 알 수 없으므로 주문하지 않는다.

주문 상태는 KIS 일별주문체결조회로 맞춘다. 체결통보 유실이나 재시작과 무관하게 항상 같은 답을 얻는다.
"""
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Callable, Optional

from pykis.client.exceptions import KisAPIError

from app.trade_worker.broker import Broker, MarketSession, OrderResult
from app.trade_worker.wallet_sync import reconcile_wallet
from app.trade_worker.worklog import WorkerLogger

log = logging.getLogger("trade_worker.manual_buy")

REQUEST_TTL_SEC = 60        # API 서버(manualBuyDao)와 같은 값
STATUS_SYNC_SEC = 5         # 접수된 주문 상태 조회 간격
ERROR_LOG_GAP_SEC = 60      # 테이블 미적용 등 반복 오류 로그 간격


def resolve_session(order_type: str, nxt: bool, krx_aftermarket: bool,
                    now: Optional[datetime] = None) -> tuple[Optional[MarketSession], str]:
    """(주문에 쓸 세션, 불가 사유). 시장가는 정규장만, 지정가는 거래 가능한 모든 세션."""
    sess = Broker.market_session(nxt, now, krx_aftermarket=krx_aftermarket)
    if not sess.tradable:
        return None, f"지금은 주문할 수 없는 시간이에요({sess.name})."
    if order_type == "MARKET":
        if sess.limit_only:
            return None, f"시장가는 정규장(09:00~15:30)에만 주문할 수 있어요. 지금은 {sess.name}이에요."
        return sess, ""
    if sess.limit_only:
        return sess, ""
    return MarketSession(True, sess.exchange, "00", sess.name), ""


def qty_from_pct(max_qty, pct) -> int:
    """주문가능수량의 pct% (1주 미만 버림)."""
    return int(Decimal(int(max_qty)) * Decimal(str(pct)) / 100)


def next_state(qty, status: Optional[dict], order_ymd: str, today_ymd: str) -> Optional[str]:
    """주문 조회 결과 → 최종 상태. 아직 진행 중이거나 판단할 수 없으면 None."""
    if status is None:          # 조회 실패 — 다음 폴링에 다시 본다
        return None
    past_day = bool(order_ymd) and order_ymd < today_ymd
    if not status.get("found"):
        return "EXPIRED" if past_day else None
    filled, remain = status["filled_qty"], status["remain_qty"]
    if filled >= Decimal(qty):
        return "FILLED"
    if remain <= 0:
        return "REJECTED" if status["rejected_qty"] > 0 and filled <= 0 else "CANCELLED"
    return "EXPIRED" if past_day else None   # 주문은 당일 유효 — 날이 바뀌면 잔량은 사라졌다


class ManualBuyExecutor:
    def __init__(self, cfg, broker, repo, sell, notifier=None):
        self.cfg = cfg
        self.broker = broker
        self.repo = repo
        self.sell = sell
        self.notifier = notifier
        self.wlog = WorkerLogger(repo, cfg.user_id, "buy")
        self._next_sync = 0.0
        self._next_error_log = 0.0

    def recover_after_boot(self) -> None:
        """이전 프로세스가 주문 도중 죽은 건 — 접수 여부를 모르므로 재주문하지 않는다."""
        try:
            n = self.repo.mark_ordering_manual_buys_unknown(
                self.cfg.user_id, "주문 중 서버가 재시작됐어요. 증권사 앱에서 주문 여부를 확인해 주세요.")
            if n:
                self.wlog.warn("[수동매수] 주문 중이던 %d건 → 결과 불명(재주문 안 함)", n)
        except Exception as e:  # noqa: BLE001  (테이블 미적용 — worker 는 죽지 않는다)
            log.warning("[수동매수] 부팅 복구 실패: %s", e)

    def poll(self, now_kst: datetime, is_trading_day: Callable[[], bool]) -> None:
        try:
            self._poll(now_kst, is_trading_day)
        except Exception as e:  # noqa: BLE001
            if time.monotonic() >= self._next_error_log:
                self._next_error_log = time.monotonic() + ERROR_LOG_GAP_SEC
                log.warning("[수동매수] 폴링 실패: %s", e)

    def _poll(self, now_kst: datetime, is_trading_day: Callable[[], bool]) -> None:
        uid = self.cfg.user_id
        self.repo.expire_stale_manual_buys(uid, REQUEST_TTL_SEC)
        requested = self.repo.get_requested_manual_buys(uid)
        if requested:
            trading = is_trading_day()
            for row in requested:
                if trading:
                    self._place(row, now_kst)
                else:
                    self.repo.finish_manual_buy(uid, row["id"], "REQUESTED", "REJECTED",
                                                reason="오늘은 휴장일이에요.")
        if time.monotonic() >= self._next_sync:
            self._next_sync = time.monotonic() + STATUS_SYNC_SEC
            self._sync_open(now_kst)

    # ── 주문 ─────────────────────────────────────────────────────────
    def _place(self, row: dict, now_kst: datetime) -> None:
        uid, order_id, code = self.cfg.user_id, row["id"], row["stock_code"]
        if not self.repo.claim_manual_buy(uid, order_id):
            return     # 그 사이 취소·만료됨

        def reject(reason: str):
            self.repo.finish_manual_buy(uid, order_id, "ORDERING", "REJECTED", reason=reason)
            self.wlog.warn("[수동매수] %s 거부: %s", code, reason)

        order_type = row["order_type"]
        qty_pct = row.get("qty_pct")
        price = Decimal(str(row["limit_price"])) if order_type == "LIMIT" else None
        nxt = row.get("nxt_flag") == "Y"
        sess, why = resolve_session(order_type, nxt, self.cfg.krx_aftermarket_enabled, now_kst)
        if sess is None:
            reject(why)
            return

        max_qty, _ = self.broker.orderable(code, price, ord_dvsn="01" if order_type == "MARKET" else "00")
        if qty_pct is not None:
            if max_qty is None:
                reject("주문가능수량을 확인하지 못했어요. 잠시 후 다시 시도해 주세요.")
                return
            qty = qty_from_pct(max_qty, qty_pct)
            if qty < 1:
                reject(f"주문가능수량의 {Decimal(str(qty_pct)).normalize():f}%가 1주보다 적어요(최대 {int(max_qty):,}주).")
                return
            self.repo.set_manual_buy_qty(uid, order_id, qty)
        else:
            qty = int(row["qty"])
            # 조회 실패(None)면 막지 않는다 — 초과 주문은 거래소가 거부한다
            if max_qty is not None and qty > int(max_qty):
                reject(f"주문가능수량을 넘었어요(최대 {int(max_qty):,}주).")
                return

        try:
            order = self.broker.manual_buy(code, Decimal(qty), sess, price)
        except KisAPIError as e:
            reject(str(e)[:250])
            return
        except Exception as e:  # noqa: BLE001  (네트워크 오류 등 — 접수됐을 수 있다)
            self._mark_unknown(order_id, code, e)
            return
        if not order.order_no:
            self._mark_unknown(order_id, code, "주문번호 없음")
            return

        ymd = now_kst.strftime("%Y%m%d")
        self.repo.mark_manual_buy_open(uid, order_id, order.order_no, order.branch,
                                       order.ord_dvsn, order.exchange, sess.name, ymd)
        # 오늘 판 종목을 다시 산 경우에도 운용모드 매도 감시가 돌도록 당일 매도 표시를 푼다
        self.sell.allow_resell(code)
        self._next_sync = 0.0
        self.wlog.info("[수동매수] 접수 %s(%s) %s %s주%s order=%s exch=%s (%s)",
                       row.get("stock_name"), code, order_type, qty,
                       f" @{price}" if price is not None else "",
                       order.order_no, order.exchange, sess.name)

    def _mark_unknown(self, order_id, code, error) -> None:
        reason = "주문 결과를 확인하지 못했어요. 증권사 앱에서 주문 여부를 확인해 주세요."
        self.repo.finish_manual_buy(self.cfg.user_id, order_id, "ORDERING", "UNKNOWN", reason=reason)
        self.wlog.warn("[수동매수] %s 결과 불명(재주문 안 함): %s", code, error)
        if self.notifier:
            self.notifier.send("⚠ 수동 매수 결과 불명", f"{code}: {reason}")

    # ── 접수 주문 상태 동기화 ─────────────────────────────────────────
    def _sync_open(self, now_kst: datetime) -> None:
        uid = self.cfg.user_id
        today = now_kst.strftime("%Y%m%d")
        for row in self.repo.get_open_manual_buys(uid):
            order_ymd = row.get("order_ymd") or today
            if row.get("cancel_requested") == "Y":
                self._cancel(row)
            status = self.broker.order_status(row["order_no"], row["stock_code"], order_ymd)
            state = next_state(row["qty"], status, order_ymd, today)
            if state is None:
                if status and status.get("found"):
                    self.repo.update_manual_buy_fill(uid, row["id"], status["filled_qty"], status["avg_price"])
                continue
            filled = status.get("filled_qty", Decimal(0))
            avg = status.get("avg_price")
            if self.repo.finish_manual_buy(uid, row["id"], "OPEN", state, filled_qty=filled, avg_price=avg):
                self._after_finish(row, state, filled, avg)

    def _cancel(self, row: dict) -> None:
        order = OrderResult(row["stock_code"], "BUY", Decimal(int(row["qty"])),
                            Decimal(str(row.get("limit_price") or 0)), row["order_no"],
                            filled_qty=Decimal(str(row.get("filled_qty") or 0)),
                            branch=row.get("branch"), ord_dvsn=row.get("ord_dvsn") or "00",
                            exchange=row.get("exchange") or "KRX")
        ok = self.broker.cancel(order)
        self.repo.clear_manual_buy_cancel(self.cfg.user_id, row["id"],
                                          None if ok else "취소하지 못했어요. 이미 체결됐을 수 있어요.")
        self.wlog.info("[수동매수] %s 취소 %s order=%s", row["stock_code"],
                       "요청 완료" if ok else "실패", row["order_no"])

    def _after_finish(self, row: dict, state: str, filled: Decimal, avg) -> None:
        code, name = row["stock_code"], row.get("stock_name") or ""
        self.wlog.info("[수동매수] %s(%s) 종료 state=%s 체결=%s/%s @%s",
                       name, code, state, filled, row["qty"], avg)
        if filled <= 0:
            return
        uid = self.cfg.user_id
        try:
            balance = reconcile_wallet(self.broker, self.repo, uid, sync=True, tag="수동매수",
                                       sell_executor=self.sell)
            self.repo.insert_trade_log(uid, code, "BUY", avg or Decimal(0), filled, balance,
                                       note=f"수동매수 {row['order_type']} {state} order={row['order_no']}")
            if self.notifier:
                self.notifier.trade("BUY", name, code, filled, avg or Decimal(0), balance,
                                    note=f"수동 매수 · {state}")
        except Exception as e:  # noqa: BLE001  (주문 상태는 이미 확정 — 후처리 실패로 되돌리지 않는다)
            self.wlog.warn("[수동매수] %s 체결 후처리 실패: %s", code, e)
