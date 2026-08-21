"""운용모드별 executor 구현.

  mode_1  M1  추천 1순위     ← 구현 완료 (실전)
  mode_2  M2  단일 종목 고정   ← 스켈레톤
  mode_3  M3  ETF 정/역 교대   ← 스켈레톤
  mode_4  M4  지정가 감시     ← 폐기(설계 단계에서 중단). 아래 참고

공통 뼈대는 app/trade_worker/buy_executor.py(BaseBuyExecutor) 와
sell_executor.py(BaseSellExecutor) 에 있다. 여기 있는 것은 모드별 훅 구현뿐이다.

※ 모드 → executor 매핑(RUNNER_BY_MODE)은 다음 단계에서 추가한다.
  지금은 main.py 가 M1 을 직접 생성한다.

※ M4(지정가 감시) 폐기:
  독립 운용모드로 만들 필요가 없었다 — 필요한 건 모드 전환이 아니라
  "이 종목만은 자동 rule 대신 내가 정한 가격에 팔아달라"는 종목 단위 오버라이드였다.
  그래서 M4 의 매도 슬롯(docs_worker_mode_runtime_spec.md §6.2)만 모드 무관 공용
  기능("매도 수기등록")으로 떼어 sell_executor.py(BaseSellExecutor)에 넣었다 —
  M1/M2/M3 어느 모드가 활성이든 등록된 종목은 그 모드의 자동 매도 rule 보다
  이 지정가가 우선(선제 적용) 한다.
  이번 변경은 **표기만** 이다 — mode_4 스켈레톤과 STRATEGY_BY_MODE 의 M4 등록
  (stock_shared/strategy/__init__.py, 여전히 NotImplementedError 스켈레톤)은
  코드상 그대로 둔다. 더 이상 구현 대상이 아니라는 것만 여기·spec 문서에 표기한다.
  자세한 내용은 docs_worker_mode_runtime_spec.md §6·§11 참고.
"""
