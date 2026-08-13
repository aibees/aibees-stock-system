"""운용모드별 executor 구현.

  mode_1  M1  추천 1순위     ← 구현 완료 (실전)
  mode_2  M2  단일 종목 고정   ← 스켈레톤
  mode_3  M3  ETF 정/역 교대   ← 스켈레톤
  mode_4  M4  지정가 감시     ← 스켈레톤

공통 뼈대는 app/trade_worker/buy_executor.py(BaseBuyExecutor) 와
sell_executor.py(BaseSellExecutor) 에 있다. 여기 있는 것은 모드별 훅 구현뿐이다.

※ 모드 → executor 매핑(RUNNER_BY_MODE)은 다음 단계에서 추가한다.
  지금은 main.py 가 M1 을 직접 생성한다.
"""
