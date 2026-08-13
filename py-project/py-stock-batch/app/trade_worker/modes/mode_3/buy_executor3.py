"""
M3 (KOSPI100 ETF ↔ 인버스 교대) 매수 — **미구현 스켈레톤**.

BaseBuyExecutor 를 상속해 pick_candidates() 만 채우면 된다.
시세·수량·주문·체결추적·포지션반영은 베이스가 처리하므로 여기서 다시 쓰지 말 것.

설계: py-stock-batch/spec_docs/docs_worker_mode_runtime_spec.md
"""
from app.trade_worker.buy_executor import BaseBuyExecutor, BuyCandidate


class BuyExecutor3(BaseBuyExecutor):
    """M3 : KOSPI100 ETF ↔ 인버스 교대."""

    MODE_CODE = "M3"

    def pick_candidates(self, premarket: bool) -> list[BuyCandidate]:
        # TODO: 추세 판정으로 long_code / short_code 중 한쪽만. 청산 체결 확인 후 반대편 진입.
        raise NotImplementedError("BuyExecutor3.pick_candidates 미구현")
