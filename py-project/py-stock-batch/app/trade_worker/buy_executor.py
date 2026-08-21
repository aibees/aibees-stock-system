"""
매수 엔진 **공통 뼈대** — 모드별 구현은 modes/mode_N/buy_executorN.py 가 상속한다.

모드마다 다른 것은 단 하나, **무엇을 살지 고르는 것**뿐이다.
그 뒤의 시세 조회 · 수량 산정 · 주문 · 체결 추적 · 포지션 반영은 전부 동일하므로
여기에 한 번만 둔다. 모드별로 복사하면 체결 추적(register_watch/arm_watch) 같은
민감한 로직이 4벌로 갈라진다.

  BaseBuyExecutor.run()          ← 템플릿. 손대지 말 것.
    ├ allow_buy()                ← 훅: 1포지션 원칙 적용 여부
    ├ pick_candidates(premarket) ← 훅: **유일한 필수 구현**
    ├ budget_ratio()             ← 훅: 예수금 투입 비율
    └ supports_premarket()       ← 훅: NXT 프리마켓 라운드 참여 여부

체결 흐름 (broker 2단 구조):
  주문 → register_watch(armed=False) → wait_fill(동기 창) → 포지션 반영
       → arm_watch(기준선 확정) → 이후 잔량 체결은 _on_late_fill 로 콜백
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.trade_worker.broker import Broker
from app.trade_worker.config import WorkerConfig
from app.trade_worker.repository import Repository
from app.trade_worker.wallet_sync import reconcile_wallet
from app.trade_worker.worklog import WorkerLogger


@dataclass
class BuyCandidate:
    """모드가 고른 매수 후보 1건. 공통 루프는 이 형태만 안다.

    모드별 원본 행(trade_buy_target_stock / user_option_mN ...)의 스키마가
    공통 코드로 새지 않게 하는 경계다.
    """
    code: str
    name: str = ""
    nxt: bool = False                       # NXT 대상 → 통합(UN/SOR), 아니면 KRX(J/KRX)
    ref_close: Optional[Decimal] = None     # 프리마켓 지정가 산출용 전일종가
    limit_price: Optional[Decimal] = None   # 지정가를 모드가 직접 정하는 경우(M4)
    log_note: str = ""                      # trade_log.note 에 남길 모드별 부가정보
    notify_note: str = ""                   # 체결 알림에 남길 모드별 부가정보


class BaseBuyExecutor(ABC):
    def __init__(self, cfg: WorkerConfig, broker: Broker, repo: Repository,
                 notifier=None, strategy=None):
        self.cfg = cfg
        self.broker = broker
        self.repo = repo
        self.notifier = notifier
        self.strategy = strategy          # SellStrategy (초기 라인 계산용)
        # 모든 로그는 trade_worker_log DB 테이블에 시간순 적재
        self.wlog = WorkerLogger(repo, cfg.user_id, "buy")

    # ── 모드별 훅 ────────────────────────────────────────────────────
    @abstractmethod
    def pick_candidates(self, premarket: bool) -> list[BuyCandidate]:
        """이번 라운드에 살 후보를 순서대로 반환. 빈 리스트면 매수하지 않는다.

        앞에서부터 시도하고 **첫 체결에서 멈춘다**(1포지션). 여러 종목을 동시에
        보유해야 하는 모드는 allow_buy()/run() 를 함께 재정의할 것.
        """

    def allow_buy(self) -> bool:
        """1포지션 원칙 — worker 보유분이 있으면 신규 매수를 막는다.

        exclusive_flag='Y' 는 카운트에서 제외한다. "보유 중이어도 신규 매수를
        막지 않는다"는 뜻일 뿐, 매도 감시에서 빼겠다는 뜻이 아니다.
        동시 보유가 필요한 모드(M4 등)는 True 고정으로 재정의한다.
        """
        blocking = self.repo.get_holding_positions(self.cfg.user_id, exclude_exclusive=True)
        if blocking:
            self.wlog.info("[매수] 보유 종목 존재 → 매수 skip (1포지션): %s",
                           ", ".join(p["stock_code"] for p in blocking))
            return False
        return True

    def budget_ratio(self) -> Decimal:
        """예수금 대비 투입 비율. 기본은 env(BUY_BUDGET_RATIO)."""
        return Decimal(str(self.cfg.buy_budget_ratio))

    def supports_premarket(self) -> bool:
        """NXT 프리마켓(08:00) 선매수 라운드에 참여하는 모드인지."""
        return False

    # ── 템플릿 ───────────────────────────────────────────────────────
    def run(self, premarket: bool = False):
        """premarket=False: 정규장 · 시장가 / True: NXT 프리마켓 · 지정가."""
        uid = self.cfg.user_id
        tag = "NXT프리마켓" if premarket else "정규장"
        self.wlog.info("[매수] 시작 user_id=%s (%s)", uid, tag)

        if premarket and not self.supports_premarket():
            self.wlog.info("[매수] %s 는 프리마켓 라운드를 쓰지 않음 → skip", type(self).__name__)
            return

        # 1) 매수 가능 여부(모드별 포지션 정책)
        if not self.allow_buy():
            return

        # 2) 현금 확인
        balance = self.repo.get_wallet_balance(uid)
        if balance <= 0:
            self.wlog.info("[매수] 잔고 %s → 매수 불가", balance)
            return

        # 3) 후보 선정 (모드별)
        candidates = self.pick_candidates(premarket)
        if not candidates:
            self.wlog.info("[매수] 후보 없음")
            return

        # 4) 시세 조회 가능한 첫 종목에 매수
        ratio = self.budget_ratio()
        budget = Decimal(balance) * ratio
        for cand in candidates:
            price = self._resolve_price(cand, premarket)
            if price is None:
                continue
            if price <= 0:
                continue

            qty = self._resolve_qty(cand, price, budget, ratio, premarket)
            if qty < 1:
                continue

            if self._place_and_settle(cand, price, qty, balance, premarket, tag):
                return   # 체결 완료 → 이번 라운드 종료

        self.wlog.info("[매수] 체결 가능한 후보 없음 (후보=%d)", len(candidates))

    # ── 공통 단계 ────────────────────────────────────────────────────
    def _resolve_price(self, cand: BuyCandidate, premarket: bool) -> Optional[Decimal]:
        """주문 기준가. None 이면 이 후보를 건너뛴다."""
        if cand.limit_price is not None:
            return Decimal(str(cand.limit_price))

        if premarket:
            # 프리마켓 지정가 = 전일 종가 × (1+slip%) → 호가단위 내림.
            # 현재가(UN) 조회는 프리마켓 초반 체결 전이면 비어 있을 수 있어 쓰지 않는다.
            close = cand.ref_close
            if not close or Decimal(str(close)) <= 0:
                self.wlog.warn("[매수] %s 전일종가 없음 → 프리마켓 skip", cand.code)
                return None
            price = self.broker.align_price(
                Decimal(str(close)) * (1 + Decimal(str(self.cfg.nxt_limit_slip_pct)) / 100))
            self.wlog.info("[매수] %s 프리마켓 지정가=%s (전일종가=%s +%s%%)",
                           cand.code, price, close, self.cfg.nxt_limit_slip_pct)
            return price

        try:
            return self.broker.current_price(cand.code, nxt=cand.nxt)
        except Exception as e:  # noqa: BLE001
            self.wlog.warn("[매수] %s 시세 조회 실패: %s → 다음 후보", cand.code, e)
            return None

    def _resolve_qty(self, cand: BuyCandidate, price: Decimal, budget: Decimal,
                     ratio: Decimal, premarket: bool) -> int:
        """수량 산정: 매수가능조회 우선, 실패 시 예수금//price fallback.
        프리마켓은 실제로 낼 지정가(ORD_DVSN=00) 기준으로 조회해야 수량이 맞는다."""
        max_qty, cash = self.broker.orderable(cand.code, price,
                                              ord_dvsn="00" if premarket else "01")
        if max_qty is not None:
            qty = int(int(max_qty) * ratio)
            self.wlog.info("[매수] %s 매수가능: 최대수량=%s 주문가능현금=%s → 수량=%s",
                           cand.code, max_qty, cash, qty)
        else:
            qty = int(budget // price)
            self.wlog.info("[매수] %s 매수가능조회 불가 → 예산기준 수량=%s", cand.code, qty)
        if qty < 1:
            self.wlog.info("[매수] %s 매수 가능 수량 0 (price=%s) → 다음 후보", cand.code, price)
        return qty

    def _place_and_settle(self, cand: BuyCandidate, price: Decimal, qty: int,
                          balance, premarket: bool, tag: str) -> bool:
        """주문 → 체결 확인 → 포지션/잔고 반영.

        반환: **이번 라운드를 종료할지** 여부.
          주문이 한 번 나갔으면 체결이든 거부든 True 다 — 거부됐다고 다음 후보로
          내려가면 같은 라운드에서 주문이 두 번 나갈 수 있다(원본 run() 의 `return` 과 동일).
          후보를 건너뛰는 것은 **주문을 내기 전**(시세 없음/수량 0)에만 허용한다.
        """
        uid = self.cfg.user_id
        code, name = cand.code, cand.name

        if premarket:
            order = self.broker.buy_limit_nxt(code, Decimal(qty), price)
        else:
            order = self.broker.buy_market(code, Decimal(qty), price, nxt=cand.nxt)

        # 주문 즉시 추적 등록. 아직 armed=False 라 콜백은 나가지 않는다 —
        # 아래 wait_fill 동기 처리와 이중 계상되지 않게 하기 위함(broker.OrderWatch 참조).
        self.broker.register_watch(order, self._on_late_fill)
        res = self.broker.wait_fill(order)

        # 미체결(PENDING)이면 즉시 취소하지 않고 설정 횟수만큼 추가 대기하며 재확인.
        # wait_fill 은 재호출해도 누적 체결(_fills)을 이어서 보므로 부분→전량 체결도 반영됨.
        retries = self.cfg.buy_fill_wait_retries
        while res.status == "PENDING" and retries > 0:
            self.wlog.info("[매수] %s 미체결 → 추가 체결대기 재확인 (남은 %d회, %ss)",
                           code, retries, self.cfg.buy_fill_wait_sec)
            res = self.broker.wait_fill(res, timeout=self.cfg.buy_fill_wait_sec)
            retries -= 1

        # 체결 실패/미체결이면 포지션·잔고 반영 안 함 (유령 포지션 방지)
        if res.status == "REJECTED" or res.filled_qty <= 0:
            # 최종적으로도 미체결이면 취소 시도(유령 체결 방지) 후 중단
            if res.status == "PENDING":
                self.broker.cancel(res)
            self.broker.unregister_watch(res.order_no)
            self.wlog.warn("[매수] %s 미체결/거부 status=%s reason=%s → 중단",
                           code, res.status, res.reason)
            return True   # 주문은 나갔다 — 다음 후보로 넘어가지 않는다

        fill_px = res.avg_price or price
        filled_amount = fill_px * res.filled_qty
        computed_balance = Decimal(balance) - filled_amount

        # 체결 반영 (부분체결이면 체결수량만) → trade_worker_position 에 HOLDING 신규
        self.repo.open_position(uid, code, name, fill_px, res.filled_qty)
        self._apply_initial_lines(code, fill_px)

        # 체결 직후 실제 예수금으로 재동기화(실패 시 계산값 사용)
        final_balance = reconcile_wallet(self.broker, self.repo, uid,
                                         computed=computed_balance,
                                         sync=self.cfg.sync_wallet_on_trade, tag="매수")
        self.repo.insert_trade_log(uid, code, "BUY", fill_px, res.filled_qty, final_balance,
                                   note=f"{cand.log_note} {res.status}".strip())
        self.wlog.info("[매수] 완료 %s(%s) 매수수량=%s @~%s 잔고=%s (%s)",
                       name, code, res.filled_qty, fill_px, final_balance, res.status)
        if self.notifier:
            self.notifier.trade("BUY", name, code, res.filled_qty, fill_px, final_balance,
                                note=f"{tag} {cand.notify_note} · {res.status}".strip())

        # 동기 처리 완료 → 추적 개시. 여기서부터 도착하는 체결분만 _on_late_fill 로 온다.
        # 전량 체결이면 arm_watch 가 False 를 돌려주고 추적은 즉시 끝난다.
        if self.broker.arm_watch(res):
            self.wlog.info("[매수] %s 잔량 %s주 체결 대기(이벤트 추적)",
                           code, res.qty - res.filled_qty)
        return True

    def _apply_initial_lines(self, code: str, fill_px: Decimal):
        """초기 손절/익절 라인 즉시 세팅(진입일에도 매도판정 대상)."""
        if not self.strategy:
            return
        try:
            lines = self.strategy.initial_lines(code, float(fill_px))
            self.repo.update_position_state(self.cfg.user_id, code, lines)
            self.wlog.info("[매수] %s 초기라인 stop=%s target=%s atr=%s",
                           code, lines.get("stop_price"), lines.get("target_price"),
                           lines.get("entry_atr"))
        except Exception as e:  # noqa: BLE001
            self.wlog.warn("[매수] %s 초기 라인 계산 실패: %s", code, e)

    # ── 동기 창 밖 체결(잔량) 반영 ───────────────────────────────────
    def _on_late_fill(self, ev):
        """지정가·부분체결로 남아있던 매수 잔량이 뒤늦게 체결됐을 때 소켓 스레드에서 호출된다.

        ev.delta_qty 만 반영한다(ev.filled_qty 는 누적이라 그대로 쓰면 이중 계상).
        전환 전에는 이 경로가 없어서 잔량 체결이 다음 부팅 대조 때까지 DB 에 안 잡혔다.
        """
        uid = self.cfg.user_id
        if ev.rejected:
            self.wlog.warn("[매수] %s 잔량 거부 order=%s reason=%s", ev.symbol, ev.order_no, ev.reason)
            return
        if ev.delta_qty <= 0:
            return
        try:
            self.repo.add_position_qty(uid, ev.symbol, ev.delta_qty, ev.last_price)
            # 평단가가 바뀌었으므로 손절/익절 라인을 다시 잡는다(안 하면 옛 진입가 기준으로 남는다).
            self._apply_initial_lines(ev.symbol, ev.avg_price)
            balance = reconcile_wallet(self.broker, self.repo, uid,
                                       sync=self.cfg.sync_wallet_on_trade, tag="매수잔량")
            self.repo.insert_trade_log(uid, ev.symbol, "BUY", ev.last_price, ev.delta_qty, balance,
                                       note=f"late fill {ev.filled_qty}/{ev.order_qty}")
            self.wlog.info("[매수] %s 잔량체결 +%s주 @%s (누적 %s/%s) 평단=%s%s",
                           ev.symbol, ev.delta_qty, ev.last_price,
                           ev.filled_qty, ev.order_qty, ev.avg_price,
                           " · 전량완료" if ev.complete else "")
        except Exception as e:  # noqa: BLE001
            self.wlog.warn("[매수] %s 잔량체결 반영 실패: %s", ev.symbol, e)
