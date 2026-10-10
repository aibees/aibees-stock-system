"""
홈 상단 '시장 요약' 띠 데이터 서비스.
KOSPI / KOSDAQ 지수와 원/달러 환율의 현재가(장중) 또는 최근 종가를 yfinance 에서 가져온다.
※ 야후 지수 시세는 실시간이 아니라 수 분~15분가량 지연될 수 있다.
"""
import logging
import time

import yfinance as yf

SNAPSHOT_ITEMS = [
    {"key": "kospi",  "symbol": "^KS11", "label": "코스피",  "code": "KOSPI",   "digits": 2},
    {"key": "kosdaq", "symbol": "^KQ11", "label": "코스닥",  "code": "KOSDAQ",  "digits": 2},
    {"key": "usdkrw", "symbol": "KRW=X", "label": "원/달러", "code": "USD/KRW", "digits": 2},
]

# 스파크라인 점 개수(최근 N거래일 종가). 20일 수익률과 같은 구간 + 시작점.
_SPARK_POINTS = 21

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

        payload = {"key": meta["key"], "label": meta["label"], "code": meta["code"],
                   "price": None, "change": None, "rate": None, "ymd": None,
                   "rate_5d": None, "rate_20d": None, "spark": []}
        try:
            # 20거래일 전 종가까지 필요하다 → 휴장일을 감안해 두 달치를 받는다.
            closes = yf.Ticker(symbol).history(period="2mo")["Close"].dropna()
            if len(closes) >= 1:
                last = float(closes.iloc[-1])
                payload["price"] = round(last, meta["digits"])
                payload["ymd"] = closes.index[-1].strftime("%Y-%m-%d")
                payload["spark"] = [round(float(v), meta["digits"]) for v in closes.iloc[-_SPARK_POINTS:]]
            if len(closes) >= 2:
                prev = float(closes.iloc[-2])
                payload["change"] = round(last - prev, meta["digits"])
                payload["rate"] = self._rate(last, prev)
            # N거래일 수익률: 오늘 종가 vs N거래일 전 종가
            if len(closes) >= 6:
                payload["rate_5d"] = self._rate(last, float(closes.iloc[-6]))
            if len(closes) >= 21:
                payload["rate_20d"] = self._rate(last, float(closes.iloc[-21]))
        except Exception as e:
            # 한 항목이 실패해도 나머지는 보여줄 수 있게 값만 비워 둔다(실패는 캐시하지 않음).
            logging.warning(f"market snapshot fetch failed: {symbol} {e}")
            return payload

        _cache[symbol] = (now, payload)
        return payload

    @staticmethod
    def _rate(last: float, base: float):
        return round((last - base) / base * 100, 2) if base else None
