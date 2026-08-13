"""
M4 (지정가 감시) 매도 — **미구현 스켈레톤**.

BaseSellExecutor 를 상속해 hit_line() 만 채우면 된다.
비율 매도가 필요하면 sell_qty() 도 재정의한다(기본은 전량).

설계: py-stock-batch/spec_docs/docs_worker_mode_runtime_spec.md
"""
from decimal import Decimal

from app.trade_worker.sell_executor import BaseSellExecutor


class SellExecutor4(BaseSellExecutor):
    """M4 : 지정가 감시 의 매도 감시."""

    MODE_CODE = "M4"

    def hit_line(self, pos: dict, price: Decimal) -> str | None:
        # TODO: 현재가 >= sell_price (use_stop_loss=1 이면 stop_price 병행)
        raise NotImplementedError("SellExecutor4.hit_line 미구현")
