"""
홈 '전월 추천 성과' 조회.

계산·저장 로직은 stock_shared.analytics.reco_performance 에 있다(배치 RecoPerformanceJob 과 공유).
API 는 저장된 값(trade_buy_target_perf_monthly)을 읽는다:
  - 확정된 달 → 저장값 그대로(야후 호출 없음)
  - 미확정 달 → MAX_AGE_HOURS 안에 계산된 저장값이면 그대로(배치가 매일 밤 갱신)
  - 저장값이 없거나 오래됨 → 그 자리에서 계산해 저장(처음 한 번 약 10초)
  - 테이블이 없으면(sql/30 미적용) 계산만 해서 돌려준다
"""
from datetime import date

from stock_shared.analytics.reco_performance import get_or_compute, prev_month

MAX_AGE_HOURS = 12


class RecoPerformanceService:

    def get_monthly_performance(self, session, ym: str | None = None) -> dict:
        return get_or_compute(session, ym or prev_month(date.today()), MAX_AGE_HOURS)
