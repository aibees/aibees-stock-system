"""
user_wallet 잔고 동기화 헬퍼.

체결 직후/부팅 시 DB user_wallet 을 **실제 KIS 예수금**과 맞춘다.
실제 조회가 가능하고 sync=True 면 실제값을 정본(source of truth)으로 삼고,
그렇지 않으면 계산값(computed)으로 대체한다.
"""
import logging
from decimal import Decimal
from typing import Optional

log = logging.getLogger("trade_worker.wallet")


def _stock_snapshot(broker, repo, user_id):
    """실제 보유종목을 user_holdings 에 갱신하고 평가금액 합계를 반환. 조회 실패 시 None."""
    holdings = broker.account_holdings()
    if holdings is None:
        return None
    try:
        repo.replace_holdings(user_id, holdings)   # 종목별 내역 갱신
    except Exception as e:  # noqa: BLE001
        log.warning("user_holdings 갱신 실패: %s", e)
    return sum((h["eval_amount"] for h in holdings), Decimal(0))


def reconcile_wallet(broker, repo, user_id: int,
                     computed: Optional[Decimal] = None,
                     sync: bool = True, tag: str = "") -> Decimal:
    """실제 계좌 기준으로 user_wallet 스냅샷(예수금·보유주식평가·총자산)을 갱신하고 예수금을 반환.

    예수금:
      1) 실제 예수금 조회 성공 & sync=True → 실제값(정본)
      2) 아니면 computed 값(수수료/세금 미반영 근사)
      3) 둘 다 없으면 DB 현재값
    보유주식평가/총자산: 실제 보유종목 조회로 함께 갱신(조회 실패 시 예수금만).
    """
    actual = broker.account_cash()
    if actual is not None and sync:
        cash = Decimal(actual)
    elif computed is not None:
        cash = Decimal(computed)
    else:
        return repo.get_wallet_balance(user_id)

    stock_amount = _stock_snapshot(broker, repo, user_id)
    total = (cash + stock_amount) if stock_amount is not None else None
    repo.set_wallet_snapshot(user_id, cash=cash, stock_amount=stock_amount, total_asset=total)
    log.info("[%s] user_wallet ← 예수금 %s · 보유평가 %s · 총자산 %s (실제조회=%s,sync=%s)",
             tag, cash, stock_amount, total, actual, sync)
    return cash
