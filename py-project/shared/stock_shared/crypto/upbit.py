"""업비트 캔들(OHLCV) 조회 — ccxt 기반.

d0cbcbd 에서 삭제된 CcxtUpbit.getOHLCV 를 복원하면서 두 가지를 바꿨다.
  - 기간 페이징(fetch_ohlcv_range) 추가: 업비트는 1회 최대 200봉이라, 예전 구현으로는
    백테스트용 장기 데이터를 받을 수 없었다.
  - datetime 을 문자열이 아니라 KST tz-naive Timestamp 로 돌려준다(리샘플/조인용).

시세 조회는 키가 필요 없다. access/secret 은 나중에 주문을 붙일 때를 위한 자리다.
업비트 일봉 경계는 KST 09:00(=UTC 00:00) 이다.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from stock_shared.crypto.ohlcv import fetch_range, to_frame

MAX_LIMIT = 200          # 업비트 캔들 API 1회 최대 개수
PAGE_SLEEP_SEC = 0.15    # 업비트 시세 API 는 초당 10회 제한 — 여유를 둔다


def _market(symbol: str) -> str:
    """'BTC' → 'BTC/KRW'. 이미 'BTC/KRW' 형태면 그대로."""
    return symbol if "/" in symbol else f"{symbol}/KRW"


class UpbitClient:
    def __init__(self, access: Optional[str] = None, secret: Optional[str] = None):
        import ccxt  # 지연 import — 이 모듈을 import 하는 것만으로는 ccxt 가 필요 없다

        config = {"enableRateLimit": True}
        if access and secret:
            config.update(apiKey=access, secret=secret)
        self.exchange = ccxt.upbit(config=config)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = MAX_LIMIT) -> pd.DataFrame:
        """최근 limit 봉(최대 200). 마지막 행은 진행 중인 봉일 수 있다."""
        rows = self.exchange.fetch_ohlcv(_market(symbol), timeframe=timeframe,
                                         limit=min(limit, MAX_LIMIT))
        return to_frame(rows)

    def fetch_ohlcv_range(self, symbol: str, timeframe: str, since, until=None,
                          drop_incomplete: bool = True) -> pd.DataFrame:
        """since ~ until 구간을 200봉씩 페이징. 규약은 ohlcv.fetch_range 참고."""
        return fetch_range(self.exchange, _market(symbol), timeframe, since, until,
                           page_limit=MAX_LIMIT, page_sleep=PAGE_SLEEP_SEC,
                           drop_incomplete=drop_incomplete)
