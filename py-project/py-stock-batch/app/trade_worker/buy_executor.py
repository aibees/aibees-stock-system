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
from app.trade_worker.repository import Repository
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

    def run(self):
        uid = self.cfg.user_id
        self.wlog.info("[매수] 시작 user_id=%s (%s)", uid, self.cfg.mode)

        # 1) 1포지션 원칙 (worker 보유분 기준)
        if self.repo.get_holding_positions(uid):
            self.wlog.info("[매수] 보유 종목 존재 → 매수 skip (1포지션)")
            return

        # 2) 현금 확인
        balance = self.repo.get_wallet_balance(uid)
        if balance <= 0:
            self.wlog.info("[매수] 잔고 %s → 매수 불가", balance)
            return

        # 3) 전날 타겟(score 내림차순 · 동률 시 rank_no 오름차순)
        #    직전 영업일을 KIS 휴장일 API로 동적 산출해 하한으로 사용(공휴일·연휴 반영).
        #    조회 실패(None)면 repo 가 요일 heuristic 으로 fallback.
        floor_ymd = self.broker.prev_trading_day()
        ymd = self.repo.get_latest_buy_target_ymd(min_ymd=floor_ymd)
        if not ymd:
            self.wlog.info("[매수] 매수타겟 없음")
            return
        targets = self.repo.get_buy_targets(ymd)

        # 4) 시세 조회 가능한 첫 종목에 시장가 매수
        budget = Decimal(balance) * Decimal(str(self.cfg.buy_budget_ratio))
        for tgt in targets:
            code = tgt["stock_code"]
            name = tgt.get("stock_name") or ""
            nxt = (tgt.get("nxt_flag") == "Y")   # NXT 대상 → 통합(UN/SOR), 아니면 KRX(J/KRX)
            try:
                price = self.broker.current_price(code, nxt=nxt)
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매수] %s 시세 조회 실패: %s → 다음 후보", code, e)
                continue
            if price <= 0:
                continue

            # 수량 산정: 매수가능조회(주문가능현금·최대매수수량) 우선, 실패 시 예수금//price fallback
            max_qty, cash = self.broker.orderable(code, price)
            if max_qty is not None:
                qty = int(int(max_qty) * Decimal(str(self.cfg.buy_budget_ratio)))
                self.wlog.info("[매수] %s 매수가능: 최대수량=%s 주문가능현금=%s → 수량=%s", code, max_qty, cash, qty)
            else:
                qty = int(budget // price)  # fallback
                self.wlog.info("[매수] %s 매수가능조회 불가 → 예산기준 수량=%s", code, qty)
            if qty < 1:
                self.wlog.info("[매수] %s 매수 가능 수량 0 (price=%s) → 다음 후보", code, price)
                continue

            res = self.broker.wait_fill(self.broker.buy_market(code, Decimal(qty), price, nxt=nxt))

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
                                    note=f"과열최저 rate={tgt.get('rate')} · {res.status}")
            return

        self.wlog.info("[매수] 체결 가능한 후보 없음 (ymd=%s, 후보=%d)", ymd, len(targets))
