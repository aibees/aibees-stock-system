"""
홈 상단 '시장 요약' 띠 데이터 서비스.
KOSPI / KOSDAQ 지수와 원/달러 환율의 현재가(장중) 또는 최근 종가를 yfinance 에서 가져온다.
※ 야후 지수 시세는 실시간이 아니라 수 분~15분가량 지연될 수 있다.
"""
import logging
import time

import yfinance as yf

SNAPSHOT_ITEMS = [
    {"key": "kospi",  "symbol": "^KS11", "label": "코스피",  "digits": 2},
    {"key": "kosdaq", "symbol": "^KQ11", "label": "코스닥",  "digits": 2},
    {"key": "usdkrw", "symbol": "KRW=X", "label": "원/달러", "digits": 2},
]

# 홈을 열 때마다 야후를 두드리지 않도록 짧게 캐시한다(장중 갱신 주기를 감안해 1분).
_CACHE_TTL_SECONDS = 60
_cache = {}  # {symbol: (fetched_at, payload)}


class MarketSnapshotService:

    def get_market_snapshot(self) -> list:
        return [self._build_item(meta) for meta in SNAPSHOT_ITEMS]

    # ── 내부 ──────────────────────────────────────────────

    def _build_item(self, meta: dict) -> dict:
        symbol = meta["symbol"]

        now = time.time()
        cached = _cache.get(symbol)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        payload = {"key": meta["key"], "label": meta["label"],
                   "price": None, "change": None, "rate": None, "ymd": None}
        try:
            closes = yf.Ticker(symbol).history(period="5d")["Close"].dropna()
            if len(closes) >= 1:
                last = float(closes.iloc[-1])
                payload["price"] = round(last, meta["digits"])
                payload["ymd"] = closes.index[-1].strftime("%Y-%m-%d")
            if len(closes) >= 2:
                prev = float(closes.iloc[-2])
                payload["change"] = round(last - prev, meta["digits"])
                payload["rate"] = round((last - prev) / prev * 100, 2) if prev else None
        except Exception as e:
            # 한 항목이 실패해도 나머지는 보여줄 수 있게 값만 비워 둔다(실패는 캐시하지 않음).
            logging.warning(f"market snapshot fetch failed: {symbol} {e}")
            return payload

        _cache[symbol] = (now, payload)
        return payload
