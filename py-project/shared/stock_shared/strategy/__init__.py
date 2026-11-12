"""
공용 매매 전략 패키지.

py-stock-batch(실전 worker·배치·시뮬)와 py-naver-stock-theme(웹 백테스트)이
같은 전략 코드를 쓰도록 이관한 것. **정본은 py-stock-batch 버전**이다.

구성:
  base        StockStrategy(ABC) + Action(Enum)   ← 매매 액션 코드의 유일한 정의
  backtester  KisBacktester   (일봉 순회 백테스트 엔진)

전략 ↔ 운용모드(user_trade_mode.active_mode) 매핑. 매매하는 운용모드는 두 가지다
(코드 정의는 stock_shared.trade_mode):
  reco        RecoStrategy       RECO        추천매수  (EMA/ATR/OBV. 실전 worker 현행 전략)
  etf_switch  EtfSwitchStrategy  ETF_SWITCH  ETF 교대  (30분봉. 전략 로직 구현됨, 실전 executor 는 스켈레톤)

  · 두 클래스 모두 StockStrategy 를 직접 상속한다(상호 상속 없음).
  · 모듈 이름 = 모드 코드 소문자 = worker modes/ 하위 디렉터리 이름 으로 셋이 일치한다.
  · 종목 단위 지정가 매도는 별도 운용모드가 아니라 모드 무관 공용 기능인
    app/trade_worker/sell_executor.py 의 "매도 수기등록"이다.
    자세한 배경은 docs_worker_mode_runtime_spec.md §6·§11.

규칙:
  · 이 패키지는 **순수 계산**만 한다. DB 세션·설정·외부 API 를 import 하지 않는다.
    (import 시점에 커넥션을 만들면 shared 를 쓰는 모든 프로세스가 물린다)
  · Action enum 값은 DB 에 적재되므로 기존 숫자를 바꾸지 말 것.
  · 여기를 고치면 py-stock-worker 이미지 재빌드가 필요하고 실매매 판정이 즉시 바뀐다.
"""
from stock_shared.strategy.base import StockStrategy, Action
from stock_shared.strategy.reco import RecoStrategy
from stock_shared.strategy.etf_switch import EtfSwitchStrategy
from stock_shared.strategy.backtester import KisBacktester
from stock_shared.trade_mode import RECO, ETF_SWITCH

# 운용모드 코드 → 전략 클래스. worker mode router 가 이 맵으로 분기한다.
STRATEGY_BY_MODE = {
    RECO: RecoStrategy,
    ETF_SWITCH: EtfSwitchStrategy,
}

__all__ = [
    "StockStrategy",
    "Action",
    "RecoStrategy",
    "EtfSwitchStrategy",
    "STRATEGY_BY_MODE",
    "KisBacktester",
]
