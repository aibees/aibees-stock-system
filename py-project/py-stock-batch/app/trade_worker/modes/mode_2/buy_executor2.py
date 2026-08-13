"""
M2 (단일 종목 고정) 매수 — **미구현 스켈레톤**.

BaseBuyExecutor 를 상속해 pick_candidates() 만 채우면 된다.
시세·수량·주문·체결추적·포지션반영은 베이스가 처리하므로 여기서 다시 쓰지 말 것.

설계: py-stock-batch/spec_docs/docs_worker_mode_runtime_spec.md
"""
from app.trade_worker.buy_executor import BaseBuyExecutor, BuyCandidate


class BuyExecutor2(BaseBuyExecutor):
    """M2 : 단일 종목 고정."""

    MODE_CODE = "M2"

    def pick_candidates(self, premarket: bool) -> list[BuyCandidate]:
        # TODO: user_option_m2.stock_code 1종목. entry_rule(IMMEDIATE/SIGNAL) 에 따라 진입.
        raise NotImplementedError("BuyExecutor2.pick_candidates 미구현")
