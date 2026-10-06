"""바이낸스 현물 캔들(OHLCV) 조회 — ccxt 기반.

레짐 판단(BTC 이평, TOTAL)은 달러 기준 차트로 봐야 해서 추가했다. 업비트 원화 가격은
김치 프리미엄 변동이 섞여 이평 신호가 달라진다.

시세 조회는 키가 필요 없다. 바이낸스 일봉 경계는 UTC 00:00(=KST 09:00)로 업비트와 같다.
BTC/USDT 1시간봉은 2017-08-17 부터 있다.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from stock_shared.crypto.ohlcv import fetch_range, to_frame

MAX_LIMIT = 1000         # 바이낸스 klines 1회 최대 개수
PAGE_SLEEP_SEC = 0.25    # klines weight 2, 분당 6000 weight — 넉넉하다


def _market(symbol: str) -> str:
    """'BTC' → 'BTC/USDT'. 이미 'BTC/USDT' 형태면 그대로."""
    return symbol if "/" in symbol else f"{symbol}/USDT"


class BinanceClient:
    def __init__(self, api_key: Optional[str] = None, secret: Optional[str] = None):
        import ccxt  # 지연 import

        config = {"enableRateLimit": True}
        if api_key and secret:
            config.update(apiKey=api_key, secret=secret)
        self.exchange = ccxt.binance(config=config)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = MAX_LIMIT) -> pd.DataFrame:
        """최근 limit 봉(최대 1000). 마지막 행은 진행 중인 봉일 수 있다."""
        rows = self.exchange.fetch_ohlcv(_market(symbol), timeframe=timeframe,
                                         limit=min(limit, MAX_LIMIT))
        return to_frame(rows)

    def fetch_ohlcv_range(self, symbol: str, timeframe: str, since, until=None,
                          drop_incomplete: bool = True) -> pd.DataFrame:
        """since ~ until 구간을 1000봉씩 페이징. 규약은 ohlcv.fetch_range 참고."""
        return fetch_range(self.exchange, _market(symbol), timeframe, since, until,
                           page_limit=MAX_LIMIT, page_sleep=PAGE_SLEEP_SEC,
                           drop_incomplete=drop_incomplete)
