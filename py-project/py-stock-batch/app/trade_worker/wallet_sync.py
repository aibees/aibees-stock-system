"""
user_wallet 잔고 동기화 헬퍼.

체결 직후/부팅 시 DB user_wallet 을 **실제 KIS 예수금**과 맞춘다.
실제 조회가 가능하고 sync=True 면 실제값을 정본(source of truth)으로 삼고,
그렇지 않으면 계산값(computed)으로 대체한다.

계좌 실보유(user_holdings) 중 worker 미추적 종목 흡수 (2026-08-21, §11.4 대체 구현):
  reconcile_wallet 에 sell_executor 를 넘기면, 실제 계좌 보유 종목 전체를
  trade_worker_position(HOLDING) 과 대조해 **아직 worker 가 모르는 종목**(HTS/MTS
  등 타채널 매수분 포함)을 trade_worker_position 에 새로 편입한다.
  ⚠ 편입되는 순간부터 그 종목은 활성 운용모드(M1 등)의 손절/익절/트레일링/
  타임스탑 자동매도 판정 대상이 된다 — 사용자가 자동매매에 맡길 생각이 없던
  종목까지 알고리즘이 팔 수 있다는 뜻이다. 매도 수기등록(trade_worker_manual_sell)을
  걸어두면 그 종목은 이 자동판정 대신 지정가만 보므로(BaseSellExecutor 선제 확인)
  안전하지만, 등록 없이 그냥 보유만 하고 있던 종목도 이 폴링(WALLET_POLL_SEC,
  기본 30초) 한 번으로 동일하게 편입되어 모드 rule 의 대상이 된다 — 계좌 보유
  전체를 worker 감시하에 두겠다는 명시적 선택(2026-08-21)에 따른 동작이다.

  단, 편입된 포지션은 exclusive_flag='Y' 로 등록되어 BuyExecutor.allow_buy() 의
  "1포지션 원칙" 카운트에서는 빠진다 — 계좌에 있던 종목이 편입됐다고 worker
  자신의 09:00 자동매수까지 멈추면 안 되기 때문이다(매도 감시는 exclusive_flag
  와 무관하게 그대로 적용됨). repository.open_position_if_absent 참고.
"""
import logging
from decimal import Decimal
from typing import Optional

log = logging.getLogger("trade_worker.wallet")


def _stock_snapshot(broker, repo, user_id):
    """실제 보유종목을 user_holdings 에 갱신하고 (평가금액 합계, holdings 목록) 반환.
    조회 실패 시 (None, None)."""
    holdings = broker.account_holdings()
    if holdings is None:
        return None, None
    try:
        repo.replace_holdings(user_id, holdings)   # 종목별 내역 갱신
    except Exception as e:  # noqa: BLE001
        log.warning("user_holdings 갱신 실패: %s", e)
    stock_amount = sum((h["eval_amount"] for h in holdings), Decimal(0))
    return stock_amount, holdings


def _absorb_untracked_holdings(repo, user_id, sell_executor, holdings):
    """user_holdings(계좌 실보유) 에는 있는데 trade_worker_position(HOLDING) 에는
    없는 종목을 worker 감시 대상으로 편입한다.

    ⚠ 편입 직후부터 그 종목은 활성 운용모드의 자동 손절/익절/트레일링/타임스탑
    판정 대상이 된다(모듈 docstring 참고). sell_executor 가 없으면(호출부가 안
    넘겼으면) 아무것도 하지 않는다 — 초기 라인을 세울 strategy 가 없는 채로
    HOLDING 만 만들면 다음 daily 평가 전까지 무방비로 방치되기 때문이다.
    """
    if not holdings or sell_executor is None or sell_executor.strategy is None:
        return
    try:
        tracked = {p["stock_code"] for p in repo.get_holding_positions(user_id)}
    except Exception as e:  # noqa: BLE001
        log.warning("[편입] worker 포지션 조회 실패 → 편입 skip: %s", e)
        return

    absorbed = []
    for h in holdings:
        code = h.get("symbol")
        qty = h.get("qty")
        if not code or code in tracked or not qty or Decimal(str(qty)) <= 0:
            continue
        entry_price = Decimal(str(h.get("avg_price") or h.get("cur_price") or 0))
        if entry_price <= 0:
            continue
        try:
            inserted = repo.open_position_if_absent(user_id, code, h.get("name") or "",
                                                     entry_price, Decimal(str(qty)))
        except Exception as e:  # noqa: BLE001
            log.warning("[편입] %s open_position 실패: %s", code, e)
            continue
        if not inserted:
            continue   # 그 사이 다른 경로로 이미 편입됨(레이스) — 정상 진행
        log.info("[편입] %s(%s) %s주 @%s → worker 감시 대상 편입(외부보유 흡수, 모드 자동매도 대상됨)",
                 h.get("name"), code, qty, entry_price)
        try:
            lines = sell_executor.strategy.initial_lines(code, float(entry_price))
            repo.update_position_state(user_id, code, lines)
            log.info("[편입] %s 초기라인 stop=%s target=%s atr=%s",
                     code, lines.get("stop_price"), lines.get("target_price"),
                     lines.get("entry_atr"))
        except Exception as e:  # noqa: BLE001
            log.warning("[편입] %s 초기 라인 계산 실패(라인 없이 HOLDING 상태로 남음): %s", code, e)
        absorbed.append(code)

    if absorbed:
        # 방금 편입한 종목을 즉시 실시간 감시(소켓 구독)에 태운다.
        # 안 하면 다음 reload_positions(개장 루틴/재기동)까지 실시간 감시 사각지대가 생긴다.
        try:
            sell_executor.reload_positions(reset_sold=False)
        except Exception as e:  # noqa: BLE001
            log.warning("[편입] reload_positions 실패: %s", e)


def reconcile_wallet(broker, repo, user_id: int,
                     computed: Optional[Decimal] = None,
                     sync: bool = True, tag: str = "",
                     sell_executor=None) -> Decimal:
    """실제 계좌 기준으로 user_wallet 스냅샷(예수금·보유주식평가·총자산)을 갱신하고 예수금을 반환.

    예수금:
      1) 실제 예수금 조회 성공 & sync=True → 실제값(정본)
      2) 아니면 computed 값(수수료/세금 미반영 근사)
      3) 둘 다 없으면 DB 현재값
    보유주식평가/총자산: 실제 보유종목 조회로 함께 갱신(조회 실패 시 예수금만).

    sell_executor 를 넘기면 계좌 실보유 중 worker 미추적 종목을 trade_worker_position
    으로 편입한다(_absorb_untracked_holdings 참고 — ⚠ 모드 자동매도 대상이 됨).
    """
    actual = broker.account_cash()
    if actual is not None and sync:
        cash = Decimal(actual)
    elif computed is not None:
        cash = Decimal(computed)
    else:
        return repo.get_wallet_balance(user_id)

    stock_amount, holdings = _stock_snapshot(broker, repo, user_id)
    total = (cash + stock_amount) if stock_amount is not None else None
    repo.set_wallet_snapshot(user_id, cash=cash, stock_amount=stock_amount, total_asset=total)
    log.info("[%s] user_wallet ← 예수금 %s · 보유평가 %s · 총자산 %s (실제조회=%s,sync=%s)",
             tag, cash, stock_amount, total, actual, sync)

    _absorb_untracked_holdings(repo, user_id, sell_executor, holdings)

    return cash
