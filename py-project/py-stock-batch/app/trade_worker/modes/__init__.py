"""운용모드별 executor 구현.

  mode_1  M1  추천매수    ← 구현 완료 (실전)
  mode_2  M2  ETF 교대    ← 스켈레톤 (전략 KospiStrategy2 는 구현됨, executor 훅만 미구현)

운용모드는 이 둘뿐이다. 종목 단위 지정가 매도는 별도 모드가 아니라 모드 무관
공용 기능("매도 수기등록")으로 sell_executor.py(BaseSellExecutor)에 있다 —
M1/M2 어느 모드가 활성이든 등록된 종목은 그 모드의 자동 매도 rule 보다
이 지정가가 우선(선제 적용) 한다. 자세한 내용은 docs_worker_mode_runtime_spec.md §6·§11 참고.

공통 뼈대는 app/trade_worker/buy_executor.py(BaseBuyExecutor) 와
sell_executor.py(BaseSellExecutor) 에 있다. 여기 있는 것은 모드별 훅 구현뿐이다.

※ 모드 → executor 매핑(RUNNER_BY_MODE)은 다음 단계에서 추가한다.
  지금은 main.py 가 M1 을 직접 생성한다.
"""
