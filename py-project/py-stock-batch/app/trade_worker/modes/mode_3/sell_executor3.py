"""
M3 (KOSPI100 ETF ↔ 인버스 교대) 매도 — **미구현 스켈레톤**.

BaseSellExecutor 를 상속해 hit_line() 만 채우면 된다.
비율 매도가 필요하면 sell_qty() 도 재정의한다(기본은 전량).

설계: py-stock-batch/spec_docs/docs_worker_mode_runtime_spec.md
"""
from decimal import Decimal

from app.trade_worker.sell_executor import BaseSellExecutor


class SellExecutor3(BaseSellExecutor):
    """M3 : KOSPI100 ETF ↔ 인버스 교대 의 매도 감시."""

    MODE_CODE = "M3"

    def hit_line(self, pos: dict, price: Decimal) -> str | None:
        # TODO: stop/target/trailing + 반대신호 강제청산(SELL_REGIME_FLIP)
        raise NotImplementedError("SellExecutor3.hit_line 미구현")
