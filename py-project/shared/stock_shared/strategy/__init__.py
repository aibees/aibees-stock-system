"""
공용 매매 전략 패키지.

py-stock-batch(실전 worker·배치·시뮬)와 py-naver-stock-theme(웹 백테스트)이
같은 전략 코드를 쓰도록 이관한 것. **정본은 py-stock-batch 버전**이다.

구성:
  base        StockStrategy(ABC) + Action(Enum)   ← 매매 액션 코드의 유일한 정의
  backtester  KisBacktester   (일봉 순회 백테스트 엔진)

전략 ↔ 운용모드(user_trade_mode.active_mode) 매핑:
  kospi1      KospiStrategy1  M1  추천 1순위     (EMA/ATR/OBV. 실전 worker 현행 전략)
  kospi2      KospiStrategy2  M2  단일 종목 고정   ← 스켈레톤
  kospi3      KospiStrategy3  M3  ETF 정/역 교대   ← 스켈레톤
  kospi4      KospiStrategy4  M4  지정가 감시     ← 스켈레톤. 운용모드로는 폐기(표기만, 코드는 유지)

  · 네 클래스 모두 StockStrategy 를 직접 상속한다(상호 상속 없음).
  · M2~M4 는 인터페이스만 있고 호출 시 NotImplementedError 를 던진다.
  · 모드 코드는 M1 부터 시작한다(구 M0~M3 체계에서 한 칸씩 이동).
    클래스 번호 = 모드 번호 = 파일 번호 로 셋이 일치한다.
  · M4(지정가 감시)는 별도 운용모드로 더 이상 구현하지 않는다. 필요했던 건
    모드 전환이 아니라 종목 단위 매도가 오버라이드였다 — 그 부분은
    app/trade_worker/sell_executor.py 의 "매도 수기등록"(모드 무관)으로
    옮겨 구현했다. 자세한 배경은 docs_worker_mode_runtime_spec.md §6·§11.

규칙:
  · 이 패키지는 **순수 계산**만 한다. DB 세션·설정·외부 API 를 import 하지 않는다.
    (import 시점에 커넥션을 만들면 shared 를 쓰는 모든 프로세스가 물린다)
  · Action enum 값은 DB 에 적재되므로 기존 숫자를 바꾸지 말 것.
  · 여기를 고치면 py-stock-worker 이미지 재빌드가 필요하고 실매매 판정이 즉시 바뀐다.
"""
from stock_shared.strategy.base import StockStrategy, Action
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.strategy.kospi2 import KospiStrategy2
from stock_shared.strategy.kospi3 import KospiStrategy3
from stock_shared.strategy.kospi4 import KospiStrategy4
from stock_shared.strategy.backtester import KisBacktester

# 운용모드 코드 → 전략 클래스. worker mode router 가 이 맵으로 분기한다.
STRATEGY_BY_MODE = {
    'M1': KospiStrategy1,
    'M2': KospiStrategy2,
    'M3': KospiStrategy3,
    'M4': KospiStrategy4,
}

__all__ = [
    "StockStrategy",
    "Action",
    "KospiStrategy1",
    "KospiStrategy2",
    "KospiStrategy3",
    "KospiStrategy4",
    "STRATEGY_BY_MODE",
    "KisBacktester",
]
