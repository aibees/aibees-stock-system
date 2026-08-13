"""
매수 엔진 — 장 시작(09:00) 1회 실행.

로직 (docs_buy_target_sim_spec.md §3, §6):
  1. 1포지션 원칙: **worker 보유분**(trade_worker_position HOLDING)이 있으면 매수 안 함.
     수동매수 보유종목은 worker 관심사가 아니므로 카운트하지 않는다(예수금만 공유).
  2. 매수 가능 판정: user_wallet 잔고 > 0 (현금/watch 상태).
  3. 전날 매수타겟 중 **score 내림차순**(동률 시 rank_no 오름차순) 1종목 선택.
  4. 시장가(시초가)로 가용 예산 전량 매수.
  5. 체결 → active 등록 · 잔고 차감 · trade_log.
"""
from decimal import Decimal

from app.trade_worker.broker import Broker
from app.trade_worker.config import WorkerConfig
from app.trade_worker.repository import Repository, describe_buy_order
from app.trade_worker.wallet_sync import reconcile_wallet
from app.trade_worker.worklog import WorkerLogger


class BuyExecutor:
    def __init__(self, cfg: WorkerConfig, broker: Broker, repo: Repository, notifier=None, strategy=None):
        self.cfg = cfg
        self.broker = broker
        self.repo = repo
        self.notifier = notifier
        self.strategy = strategy          # SellStrategy (초기 라인 계산용)
        # 모든 로그는 trade_worker_log DB 테이블에 시간순 적재
        self.wlog = WorkerLogger(repo, cfg.user_id, "buy")

    def _buy_order_spec(self) -> str | None:
        """유저 매수타겟 정렬 스펙(user_options.s1_buy_order).

        user_meta 는 SellStrategy 가 이미 들고 있어(UserService.get_user_options)
        재조회하지 않는다. strategy 미주입(단위테스트 등)이면 None → repo 기본값.
        """
        meta = getattr(self.strategy, "user_meta", None)
        return getattr(meta, "s1_buy_order", None) if meta else None

    def run(self, premarket: bool = False):
        """premarket=False: KRX 정규장 09:00 · 시장가 · 후보 전체를 순회.
        premarket=True : NXT 프리마켓 08:00 · **지정가** · score 1위가 NXT 대상일 때만 1회 시도.

        프리마켓에서 1위만 보는 이유: 후보를 훑어 내려가면 score 1위(KRX 전용)를 두고
        하위 종목을 사버리게 되고, 1포지션 원칙 때문에 09:00 에 1위를 살 기회가 사라진다.
        프리마켓 라운드는 '1위가 마침 NXT면 일찍 잡는다'는 보너스로만 동작한다."""
        uid = self.cfg.user_id
        tag = "NXT프리마켓" if premarket else "정규장"
        self.wlog.info("[매수] 시작 user_id=%s (%s · %s)", uid, self.cfg.mode, tag)

        # 1) 1포지션 원칙 (worker 보유분 기준)
        #    exclusive_flag='Y' 는 카운트에서 제외 — 신규 매수를 막지 않는 포지션이다.
        #    (매도 감시·부팅 대조는 이 플래그와 무관하게 전량을 본다)
        blocking = self.repo.get_holding_positions(uid, exclude_exclusive=True)
        if blocking:
            self.wlog.info("[매수] 보유 종목 존재 → 매수 skip (1포지션): %s",
                           ", ".join(p["stock_code"] for p in blocking))
            return

        # 2) 현금 확인
        balance = self.repo.get_wallet_balance(uid)
        if balance <= 0:
            self.wlog.info("[매수] 잔고 %s → 매수 불가", balance)
            return

        # 3) 전날 타겟을 유저 정렬 기준(user_options.s1_buy_order)으로 정렬
        #    직전 영업일을 KIS 휴장일 API로 동적 산출해 하한으로 사용(공휴일·연휴 반영).
        #    조회 실패(None)면 repo 가 요일 heuristic 으로 fallback.
        floor_ymd = self.broker.prev_trading_day()
        ymd = self.repo.get_latest_buy_target_ymd(min_ymd=floor_ymd)
        if not ymd:
            self.wlog.info("[매수] 매수타겟 없음")
            return

        # 정렬 1순위 = 매수 종목이므로, 설정값이 아니라 **실제 적용된** 정렬을 남긴다
        # (오타·미지원 필드는 repo 가 조용히 걸러내고 기본값으로 되돌리기 때문).
        order_spec = self._buy_order_spec()
        targets = self.repo.get_buy_targets(ymd, order_spec=order_spec)
        self.wlog.info("[매수] 타겟 %d건 (ymd=%s · 정렬=%s)",
                       len(targets), ymd, describe_buy_order(order_spec))

        # 3-1) 프리마켓 라운드는 정렬 1위가 NXT 대상일 때만 성립
        if premarket:
            if not targets:
                self.wlog.info("[매수] 매수타겟 없음")
                return
            top = targets[0]
            if top.get("nxt_flag") != "Y":
                self.wlog.info("[매수] 1위 %s(%s) NXT 미대상(nxt_flag=%s) → 프리마켓 skip, 09:00 대기",
                               top.get("stock_name"), top["stock_code"], top.get("nxt_flag"))
                return
            targets = [top]

        # 4) 시세 조회 가능한 첫 종목에 매수 (정규장=시장가 / 프리마켓=지정가)
        budget = Decimal(balance) * Decimal(str(self.cfg.buy_budget_ratio))
        for tgt in targets:
            code = tgt["stock_code"]
            name = tgt.get("stock_name") or ""
            nxt = (tgt.get("nxt_flag") == "Y")   # NXT 대상 → 통합(UN/SOR), 아니면 KRX(J/KRX)

            if premarket:
                # 프리마켓 지정가 = 전일 종가 × (1+slip%) → 호가단위 내림.
                # 현재가(UN) 조회는 프리마켓 초반 체결 전이면 비어 있을 수 있어 쓰지 않는다.
                close = tgt.get("close")
                if not close or Decimal(str(close)) <= 0:
                    self.wlog.warn("[매수] %s 전일종가 없음 → 프리마켓 skip", code)
                    return
                price = self.broker.align_price(
                    Decimal(str(close)) * (1 + Decimal(str(self.cfg.nxt_limit_slip_pct)) / 100))
                self.wlog.info("[매수] %s 프리마켓 지정가=%s (전일종가=%s +%s%%)",
                               code, price, close, self.cfg.nxt_limit_slip_pct)
            else:
                try:
                    price = self.broker.current_price(code, nxt=nxt)
                except Exception as e:  # noqa: BLE001
                    self.wlog.warn("[매수] %s 시세 조회 실패: %s → 다음 후보", code, e)
                    continue
            if price <= 0:
                continue

            # 수량 산정: 매수가능조회(주문가능현금·최대매수수량) 우선, 실패 시 예수금//price fallback
            #   프리마켓은 실제로 낼 지정가(ORD_DVSN=00) 기준으로 조회해야 수량이 맞는다.
            max_qty, cash = self.broker.orderable(code, price,
                                                  ord_dvsn="00" if premarket else "01")
            if max_qty is not None:
                qty = int(int(max_qty) * Decimal(str(self.cfg.buy_budget_ratio)))
                self.wlog.info("[매수] %s 매수가능: 최대수량=%s 주문가능현금=%s → 수량=%s", code, max_qty, cash, qty)
            else:
                qty = int(budget // price)  # fallback
                self.wlog.info("[매수] %s 매수가능조회 불가 → 예산기준 수량=%s", code, qty)
            if qty < 1:
                self.wlog.info("[매수] %s 매수 가능 수량 0 (price=%s) → 다음 후보", code, price)
                continue

            if premarket:
                order = self.broker.buy_limit_nxt(code, Decimal(qty), price)
            else:
                order = self.broker.buy_market(code, Decimal(qty), price, nxt=nxt)

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
                return

            fill_px = res.avg_price or price
            filled_amount = fill_px * res.filled_qty
            computed_balance = Decimal(balance) - filled_amount

            # 5) 체결 반영 (부분체결이면 체결수량만) → trade_worker_position 에 HOLDING 신규
            self.repo.open_position(uid, code, name, fill_px, res.filled_qty)
            # 초기 손절/익절 라인 즉시 세팅(진입일에도 매도판정 대상 — 3.3 규칙 폐기)
            if self.strategy:
                try:
                    lines = self.strategy.initial_lines(code, float(fill_px))
                    self.repo.update_position_state(uid, code, lines)
                    self.wlog.info("[매수] %s 초기라인 stop=%s target=%s atr=%s",
                                   code, lines.get("stop_price"), lines.get("target_price"), lines.get("entry_atr"))
                except Exception as e:  # noqa: BLE001
                    self.wlog.warn("[매수] %s 초기 라인 계산 실패: %s", code, e)
            # 체결 직후 실제 예수금으로 재동기화(실패 시 계산값 사용)
            final_balance = reconcile_wallet(self.broker, self.repo, uid,
                                             computed=computed_balance,
                                             sync=self.cfg.sync_wallet_on_trade, tag="매수")
            self.repo.insert_trade_log(uid, code, "BUY", fill_px, res.filled_qty, final_balance,
                                       note=f"buy target ymd={ymd} rate={tgt.get('rate')} {res.status}")
            self.wlog.info("[매수] 완료 %s(%s) 매수수량=%s @~%s 잔고=%s (%s)",
                           name, code, res.filled_qty, fill_px, final_balance, res.status)
            if self.notifier:
                self.notifier.trade("BUY", name, code, res.filled_qty, fill_px, final_balance,
                                    note=f"{tag} score={tgt.get('score')} · {res.status}")

            # 동기 처리 완료 → 추적 개시. 여기서부터 도착하는 체결분만 _on_late_fill 로 온다.
            # 전량 체결이면 arm_watch 가 False 를 돌려주고 추적은 즉시 끝난다.
            if self.broker.arm_watch(res):
                self.wlog.info("[매수] %s 잔량 %s주 체결 대기(이벤트 추적)",
                               code, res.qty - res.filled_qty)
            return

        self.wlog.info("[매수] 체결 가능한 후보 없음 (ymd=%s, 후보=%d)", ymd, len(targets))

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
            if self.strategy:
                try:
                    lines = self.strategy.initial_lines(ev.symbol, float(ev.avg_price))
                    self.repo.update_position_state(uid, ev.symbol, lines)
                except Exception as e:  # noqa: BLE001
                    self.wlog.warn("[매수] %s 잔량체결 후 라인 재계산 실패: %s", ev.symbol, e)
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
