"""
매도 엔진 — 실시간 소켓 감시.

판정 분리 (docs_buy_target_sim_spec.md §4 기준):
  - 실시간(소켓): 체결가가 stop_price / target_price / trail_line 을 돌파하면 즉시 매도.
    (라인 값은 daily 배치 StockSellCheckJob 이 미리 계산·저장)
  - 개장 시(apply_open_signals): 일봉 신호(OBV 데드크로스·타임스탑 등으로 action_type 이
    SELL 계열로 마킹된) 포지션을 정리. (일봉 지표는 실시간 판정 불가)

거래 세션 분리 (broker.market_session):
  - NXT 대상(master_stock.nxt_flag='Y'): 08:00~08:50 프리마켓(지정가) · 09:00~15:20 메인(시장가)
    · 15:20~15:30 KRX 단독(시장가) · 15:30~20:00 애프터마켓(지정가)
  - KRX 전용: 09:00~15:30 만 (시장가)
  통합 실시간 스트림(H0UNCNT0)은 장외에도 틱이 오므로, 세션 가드 없이는 KRX 가 닫힌
  시간에 SOR 시장가가 나가 거부되고 연속 실패로 종목이 자동 비활성된다.

체결 → sold 처리 · 잔고 증가 · trade_log.
"""
import threading
import time
from decimal import Decimal

from app.trade_worker.broker import Broker
from app.trade_worker.config import WorkerConfig
from app.trade_worker.repository import Repository
from app.trade_worker.wallet_sync import reconcile_wallet
from app.trade_worker.worklog import WorkerLogger

# Decimal 로 변경
def _toDecimal(v):
    return Decimal(str(v)) if v is not None else None


class SellExecutor:
    def __init__(self, cfg: WorkerConfig, broker: Broker, repo: Repository, notifier=None, strategy=None):
        self.cfg = cfg
        self.broker = broker
        self.repo = repo
        self.notifier = notifier
        self.strategy = strategy          # SellStrategy (일별 라인/액션 계산)
        # 모든 로그는 trade_worker_log DB 테이블에 시간순 적재
        self.wlog = WorkerLogger(repo, cfg.user_id, "sell")
        self.positions: dict[str, dict] = {}   # symbol -> position row
        self._tickets: dict[str, object] = {}  # symbol -> 구독 티켓(종목별 해제용)
        self._subscribed: set[str] = set()     # 이미 시세 구독한 종목(중복 구독 방지)
        self._sold: set[str] = set()           # 당일 매도 완료(개장 reload 시 초기화)
        self._inflight: set[str] = set()       # 매도 주문 진행중(동시 중복주문 방지)
        self._cooldown: dict[str, float] = {}  # 실패 후 재시도 금지 만료시각(폭주 방지)
        self._fail_count: dict[str, int] = {}  # 종목별 연속 실패 횟수
        self._disabled: set[str] = set()       # 연속 실패로 자동 비활성(수동 확인 필요)
        self._untradable_log: dict[str, float] = {}  # 장외 라인돌파 로그 throttle 만료시각
        self._lock = threading.Lock()

    # ── 구독 시작 ────────────────────────────────────────────────────
    def start(self):
        # 체결통보 구독은 broker.start_fill_tracking() 이 담당(main). 여기선 시세만.
        self.reload_positions()

    """
    worker 보유(trade_worker_position HOLDING) 종목을 감시 대상으로 갱신.
    - 감시 대상 = worker 가 직접 매수한 HOLDING 만 (trade_sell_target_stock 과 무관)
    - _sold 초기화(당일 리셋), 미구독 종목만 신규 시세 구독
    """
    def reload_positions(self, reset_sold: bool = True):
        """reset_sold=False 는 **매수 직후 재적재 전용**.
        당일 이미 판 종목의 _sold 마킹을 지우지 않기 위해서다."""
        # trade_worker_position 에서 HOLDING 상태의 종목들
        holding = self.repo.get_holding_positions(self.cfg.user_id)

        self.positions = {p["stock_code"]: p for p in holding}
        if reset_sold:
            self._sold = set()
        # self.wlog.info("[매도] HOLDING(감시대상) %d종목 · 실시간시세 구독중 %d종목",
        #                len(holding), len(self._subscribed))
        for code, pos in self.positions.items():
            if code in self._subscribed:
                continue
            try:
                nxt = (pos.get("nxt_flag") == "Y")   # NXT 대상 → 통합 스트림(H0UNCNT0)
                self._tickets[code] = self.broker.subscribe_price(code, self.on_price, nxt=nxt)
                self._subscribed.add(code)
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s price 구독 실패: %s", code, e)

    def _unsubscribe(self, symbol: str):
        """보유 종료(매도 완료/외부청산) 종목의 실시간 시세 구독 해제.
        보유중(active)일 때만 소켓 감시하고, 팔고 나면 즉시 구독을 끊어 리소스를 정리한다."""
        ticket = self._tickets.pop(symbol, None)
        self._subscribed.discard(symbol)
        if ticket is not None:
            try:
                ticket.unsubscribe()
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s 구독 해제 실패: %s", symbol, e)

    # ── 세션 가드 ────────────────────────────────────────────────────
    def _session(self, pos: dict):
        """이 종목이 지금 주문 가능한 세션인지. NXT 대상과 KRX 전용은 창이 다르다.
          - NXT 대상 : 08:00~08:50(지정가) · 09:00~15:20 · 15:20~15:30 · 15:30~20:00(지정가)
          - KRX 전용 : 09:00~15:30 만
        통합 스트림(H0UNCNT0)은 장외에도 틱을 뿜기 때문에 이 가드가 없으면
        KRX 닫힌 시간에 SOR 시장가가 나가 '장운영시간이 아닙니다'로 거부되고,
        _register_fail 이 쌓여 종목이 자동 비활성(_disabled)까지 간다."""
        return self.broker.market_session(pos.get("nxt_flag") == "Y")

    # ── 실시간 라인 돌파 ─────────────────────────────────────────────
    def on_price(self, symbol: str, price: Decimal):
        pos = self.positions.get(symbol)
        if not pos or symbol in self._sold or symbol in self._inflight or symbol in self._disabled:
            return
        # 실패 쿨다운 중이면 재시도 금지(폭주 방지)
        cd = self._cooldown.get(symbol)
        if cd and time.time() < cd:
            return
        reason = self._hit_line(pos, price)
        if not reason:
            return
        sess = self._session(pos)
        if not sess.tradable:
            # 주문 불가 시간대(예: NXT 08:50~09:00 휴식, 20:00 이후). 실패로 세지 않는다.
            self._warn_untradable(symbol, reason, sess)
            return
        self.wlog.info("[매도] 라인 돌파 %s @%s (%s · %s)", symbol, price, reason, sess.name)
        self._do_sell(symbol, pos, price, reason, sess)

    def _warn_untradable(self, symbol: str, reason: str, sess):
        """장외 라인돌파 로그 — 소켓 틱마다 찍히면 폭주하므로 종목당 60초 1회로 제한."""
        now = time.time()
        if now < self._untradable_log.get(symbol, 0):
            return
        self._untradable_log[symbol] = now + 60
        self.wlog.info("[매도] %s 라인 돌파(%s) 감지했으나 %s → 주문 보류",
                       symbol, reason, sess.name)

    @staticmethod
    def _hit_line(pos: dict, price: Decimal) -> str | None:
        stop = _toDecimal(pos.get("stop_price"))
        target = _toDecimal(pos.get("target_price"))
        trail = _toDecimal(pos.get("trail_line"))
        if stop and price <= stop:
            return "SELL_STOP_LOSS"
        if target and price >= target:
            return "SELL_PROFIT"
        if trail and price <= trail:
            return "SELL_TRAIL"
        return None

    # ── 일별 전략 평가 (KospiStrategy1 재사용) ───────────────────────
    def refresh_positions(self):
        """HOLDING 포지션마다 KospiStrategy1 로 라인/액션 재계산 → DB 갱신.
        일봉 신호(OBV 데드크로스·타임스탑 등)로 SELL 판정되면 개장 시 즉시 매도.
        realtime stop/target/trail 라인도 이 값으로 갱신됨."""
        if not self.strategy:
            return
        for code, pos in list(self.positions.items()):
            if code in self._sold or code in self._disabled:
                continue
            try:
                result, state = self.strategy.evaluate(pos)
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s 전략 평가 실패: %s", code, e)
                continue
            if state is None:
                self.wlog.warn("[매도] %s 데이터 부족 → 평가 skip", code)
                continue
            # DB 라인/상태 갱신 + 메모리 포지션 갱신(realtime 감시에 반영)
            self.repo.update_position_state(self.cfg.user_id, code, state)
            pos.update({
                "stop_price": state.get("stop_price"),
                "target_price": state.get("target_price"),
                "trail_line": state.get("trail_line"),
                "bars_held": state.get("bars_held"),
                "peak_close": state.get("peak_close"),
                "peak_high": state.get("peak_high"),
            })
            action = (result or {}).get("action_type", "HOLD")
            self.wlog.info("[매도] %s 평가: %s (stop=%s target=%s trail=%s bars=%s)",
                           code, action, state.get("stop_price"), state.get("target_price"),
                           state.get("trail_line"), state.get("bars_held"))
            if action != "HOLD":
                nxt = (pos.get("nxt_flag") == "Y")
                sess = self._session(pos)
                if not sess.tradable:
                    self.wlog.info("[매도] %s 일봉신호(%s) 이지만 %s → 주문 보류", code, action, sess.name)
                    continue
                try:
                    price = self.broker.current_price(code, nxt=nxt)
                except Exception as e:  # noqa: BLE001
                    self.wlog.warn("[매도] %s 개장 시세 실패: %s", code, e)
                    price = _toDecimal(state.get("target_price")) or Decimal(0)
                self._do_sell(code, pos, price, action, sess)

    # ── 실제 보유수량 조회 ───────────────────────────────────────────
    def _actual_qty(self, symbol: str):
        """실제 계좌 보유수량. 조회 실패 시 None, 목록에 없으면 0."""
        holdings = self.broker.account_holdings()
        if holdings is None:
            return None
        for h in holdings:
            if h.get("symbol") == symbol:
                return Decimal(str(h.get("qty") or 0))
        return Decimal(0)

    def _register_fail(self, symbol: str, msg: str):
        """매도 실패 → 쿨다운 설정. 연속 실패가 임계 도달 시 자동 비활성."""
        self._cooldown[symbol] = time.time() + self.cfg.sell_retry_cooldown_sec
        c = self._fail_count.get(symbol, 0) + 1
        self._fail_count[symbol] = c
        self.wlog.warn("[매도] %s 실패(%d회) → %ds 쿨다운: %s",
                       symbol, c, self.cfg.sell_retry_cooldown_sec, msg)
        if c >= self.cfg.sell_max_fails:
            self._disabled.add(symbol)
            self.wlog.warn("[매도] %s 연속 %d회 실패 → 자동 비활성(수동 확인 필요)", symbol, c)
            if self.notifier:
                self.notifier.send("⚠ 매도 실패 경보", f"{symbol} 매도 {c}회 실패로 자동 비활성됨")

    # ── 매도 실행 ────────────────────────────────────────────────────
    def _do_sell(self, symbol: str, pos: dict, price: Decimal, reason: str, sess=None):
        # 동시성 가드: 소켓 콜백이 여러 틱 동시 진입해도 종목당 1건만 진행.
        with self._lock:
            if symbol in self._sold or symbol in self._inflight or symbol in self._disabled:
                return
            cd = self._cooldown.get(symbol)
            if cd and time.time() < cd:
                return
            self._inflight.add(symbol)
        try:
            # ── 실제 보유수량으로 매도량 보정(‘주문가능수량 초과’ 방지) ──
            db_qty = _toDecimal(pos.get("hold_qty")) or Decimal(0)
            actual = self._actual_qty(symbol)
            if actual is not None and actual <= 0:
                # 실제 보유 없음 = 이미 청산됨 → 포지션 종료(정리)
                self.repo.close_position(self.cfg.user_id, symbol, price, Decimal(0), "EXTERNAL_CLOSED")
                self.positions.pop(symbol, None)
                self._sold.add(symbol)
                self._unsubscribe(symbol)   # 보유 종료 → 실시간 감시 비활성
                self.wlog.warn("[매도] %s 실제 보유 0 → 청산된 것으로 간주하고 정리", symbol)
                return
            qty = db_qty if actual is None else min(db_qty, actual)
            if qty <= 0:
                self.wlog.warn("[매도] %s 매도수량 0 (db=%s actual=%s) → skip", symbol, db_qty, actual)
                self._register_fail(symbol, "매도수량 0")
                return

            sess = sess or self._session(pos)
            if not sess.tradable:
                self.wlog.info("[매도] %s %s → 주문 보류(실패로 세지 않음)", symbol, sess.name)
                return

            # 지정가 세션(NXT 프리/애프터마켓)은 시장가가 없다.
            # 손절/익절은 체결 속도가 생명이므로 체결가보다 한 틱 아래로 걸어 즉시 체결을 유도한다.
            order_px = price
            if sess.limit_only:
                order_px = self.broker.align_price(
                    price * (1 - Decimal(str(self.cfg.sell_limit_slip_pct)) / 100))
                if order_px <= 0:
                    self._register_fail(symbol, f"지정가 산출 실패(price={price})")
                    return
                self.wlog.info("[매도] %s %s 지정가=%s (체결가=%s -%s%%)",
                               symbol, sess.name, order_px, price, self.cfg.sell_limit_slip_pct)
            try:
                res = self.broker.wait_fill(
                    self.broker.order_in_session("SELL", symbol, qty, order_px, sess))
            except Exception as e:  # noqa: BLE001  (KIS API 오류·수량초과·rate limit 등)
                self._register_fail(symbol, f"주문 예외: {e}")
                return

            # 체결 실패/미체결/거부 → 쿨다운(폭주 방지), 보유 유지
            if res.status == "REJECTED" or res.filled_qty <= 0:
                self._register_fail(symbol, f"status={res.status} reason={res.reason}")
                return

            fill_px = res.avg_price or price
            proceeds = fill_px * res.filled_qty
            computed_balance = self.repo.get_wallet_balance(self.cfg.user_id) + proceeds

            # 부분체결(PARTIAL)은 스켈레톤에서 청산 처리 — 잔여수량 관리는 TODO
            self.repo.close_position(self.cfg.user_id, symbol, fill_px, res.filled_qty, reason)
            self.positions.pop(symbol, None)
            self._unsubscribe(symbol)   # 매도 완료 → 실시간 감시 비활성
            final_balance = reconcile_wallet(self.broker, self.repo, self.cfg.user_id,
                                             computed=computed_balance,
                                             sync=self.cfg.sync_wallet_on_trade, tag="매도")
            self.repo.insert_trade_log(self.cfg.user_id, symbol, "SELL", fill_px, res.filled_qty,
                                       final_balance, note=f"{reason}/{res.status}")
            self._sold.add(symbol)
            self._fail_count.pop(symbol, None)
            self._cooldown.pop(symbol, None)
            self.wlog.info("[매도] 완료 %s qty=%s @~%s 잔고=%s (%s/%s)",
                           symbol, res.filled_qty, fill_px, final_balance, reason, res.status)
            if self.notifier:
                self.notifier.trade("SELL", pos.get("stock_name") or "", symbol,
                                    res.filled_qty, fill_px, final_balance,
                                    note=f"{reason} · {res.status}")
        except Exception as e:  # noqa: BLE001  (예상 밖 오류도 폭주 없이 쿨다운)
            self._register_fail(symbol, f"예외: {e}")
        finally:
            self._inflight.discard(symbol)

    def _on_execution(self, execution):
        # 실시간 체결통보 수신(정밀 체결 로그용 훅). 스켈레톤에선 로깅만.
        try:
            self.wlog.info("[체결통보] %s executed_qty=%s price=%s",
                           getattr(execution, "symbol", "?"),
                           getattr(execution, "executed_qty", "?"),
                           getattr(execution, "price", "?"))
        except Exception:  # noqa: BLE001
            pass
