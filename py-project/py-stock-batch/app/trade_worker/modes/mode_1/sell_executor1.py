"""
M1 (추천 1순위) 매도 — 손절 / 익절 / 트레일링 라인 감시.

BaseSellExecutor 에서 갈리는 지점은 **팔 조건 하나**뿐이다.
구독·고점추적·세션가드·쿨다운·체결반영은 전부 베이스가 처리한다.

판정 우선순위는 docs_buy_target_sim_spec.md §4 와 동일하며,
리팩터링 전 SellExecutor._hit_line 을 **동작 변경 없이** 그대로 옮긴 것이다.
일봉 신호(OBV 데드크로스·타임스탑)는 실시간 판정 대상이 아니라
개장 시 refresh_positions() 가 전략 evaluate 로 처리한다.
"""
from decimal import Decimal

from app.trade_worker.sell_executor import BaseSellExecutor, _toDecimal


class SellExecutor1(BaseSellExecutor):
    """M1 : 추천 1순위 자동매매의 매도 감시."""

    MODE_CODE = "M1"

    def hit_line(self, pos: dict, price: Decimal) -> str | None:
        """손절 > 익절 > 트레일링 순으로 먼저 걸리는 것이 발동.

        순서를 바꾸면 안 된다. 손절이 익절보다 뒤로 가면 급락 구간에서
        익절선을 스치고 내려간 틱이 SELL_PROFIT 으로 잡힐 수 있다.
        """
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
