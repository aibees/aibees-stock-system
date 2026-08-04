"""
공용 매매 전략 패키지.

py-stock-batch(실전 worker·배치·시뮬)와 py-naver-stock-theme(웹 백테스트)이
같은 전략 코드를 쓰도록 이관한 것. **정본은 py-stock-batch 버전**이다.

구성:
  base        StockStrategy(ABC) + Action(Enum)   ← 매매 액션 코드의 유일한 정의
  kospi1      KospiStrategy1  (EMA/ATR/OBV 기반, 실전 worker 가 쓰는 전략)
  kospi2      KospiStrategy2  (HMA/OBV/MACD/체결강도 조합)
  backtester  KisBacktester   (일봉 순회 백테스트 엔진)

규칙:
  · 이 패키지는 **순수 계산**만 한다. DB 세션·설정·외부 API 를 import 하지 않는다.
    (import 시점에 커넥션을 만들면 shared 를 쓰는 모든 프로세스가 물린다)
  · Action enum 값은 DB 에 적재되므로 기존 숫자를 바꾸지 말 것.
  · 여기를 고치면 py-stock-worker 이미지 재빌드가 필요하고 실매매 판정이 즉시 바뀐다.
"""
from stock_shared.strategy.base import StockStrategy, Action
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.strategy.kospi2 import KospiStrategy2
from stock_shared.strategy.backtester import KisBacktester

__all__ = [
    "StockStrategy",
    "Action",
    "KospiStrategy1",
    "KospiStrategy2",
    "KisBacktester",
]
