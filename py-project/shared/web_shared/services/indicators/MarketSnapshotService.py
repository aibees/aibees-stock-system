"""
홈 상단 '시장 요약' 띠 데이터 서비스.
KOSPI / KOSDAQ 지수와 원/달러 환율의 현재가(장중) 또는 최근 종가를 yfinance 에서 가져온다.
요청하면(extra) 달러 금리(미국 10년물 국채금리 ^TNX, 단위 %)를 맨 앞에 더한다.
※ 야후 지수 시세는 실시간이 아니라 수 분~15분가량 지연될 수 있다.
"""
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

SNAPSHOT_ITEMS = [
    {"key": "kospi",  "symbol": "^KS11", "label": "코스피",  "code": "KOSPI",   "digits": 2},
    {"key": "kosdaq", "symbol": "^KQ11", "label": "코스닥",  "code": "KOSDAQ",  "digits": 2},
    {"key": "usdkrw", "symbol": "KRW=X", "label": "원/달러", "code": "USD/KRW", "digits": 2},
]

# 요청할 때만 더하는 항목(extra key). 맨 앞에 붙는다. 비밀상회 홈은 묻지 않는다(router_indicators 참고).
#   us10y : 미국 10년물 국채금리(%). change 는 %p, rate 는 금리 자체의 변화율(%)이라 화면은 change 를 쓴다.
EXTRA_ITEMS = [
    {"key": "us10y", "symbol": "^TNX", "label": "달러 금리", "code": "US10Y", "digits": 3},
]

# 스파크라인 점 개수(최근 N거래일 종가). 20일 수익률과 같은 구간 + 시작점.
_SPARK_POINTS = 21

# 홈을 열 때마다 야후를 두드리지 않도록 캐시한다. 캐시 미스면 야후 조회에 0.5~2.7초가 걸린다(2026-11-21 실측).
#   국내 장중(평일 08:30~16:00 KST)  : 1분 — 지수가 움직인다
#   평일 그 밖의 시간                 : 10분 — 지수는 멈췄고 환율만 천천히 움직인다
#   주말                              : 60분 — 값이 바뀌지 않는다
#   (홈은 1분마다 다시 묻고 gunicorn 워커 4개가 캐시를 따로 가져서, 1분 TTL 이면 장 마감 뒤에도 미스가 잦았다)
_KST = ZoneInfo("Asia/Seoul")
_TTL_MARKET_SECONDS = 60
_TTL_OFF_HOURS_SECONDS = 10 * 60
_TTL_WEEKEND_SECONDS = 60 * 60
_cache = {}  # {symbol: (fetched_at, payload)}


def _cache_ttl_seconds(now: datetime = None) -> int:
    now = now or datetime.now(_KST)
    if now.weekday() >= 5:
        return _TTL_WEEKEND_SECONDS
    hm = now.hour * 100 + now.minute
    return _TTL_MARKET_SECONDS if 830 <= hm < 1600 else _TTL_OFF_HOURS_SECONDS


class MarketSnapshotService:

    def get_market_snapshot(self, extra: list = None) -> list:
        # 캐시가 지난 종목만 야후에 묻는다. (스레드로 동시에 물어도 yfinance 가 빨라지지 않아 차례로 묻는다 — 2026-11-21 실측)
        wanted = set(extra or [])
        items = [m for m in EXTRA_ITEMS if m["key"] in wanted] + SNAPSHOT_ITEMS
        ttl = _cache_ttl_seconds()
        now = time.time()
        for meta in items:
            cached = _cache.get(meta["symbol"])
            if not (cached and now - cached[0] < ttl):
                self._refresh(meta)
        return [self._cached_or_empty(meta) for meta in items]

    # ── 내부 ──────────────────────────────────────────────

    @staticmethod
    def _empty(meta: dict) -> dict:
        return {"key": meta["key"], "label": meta["label"], "code": meta["code"],
                "price": None, "change": None, "rate": None, "ymd": None,
                "rate_5d": None, "rate_20d": None, "spark": []}

    def _cached_or_empty(self, meta: dict) -> dict:
        cached = _cache.get(meta["symbol"])
        return cached[1] if cached else self._empty(meta)

    def _refresh(self, meta: dict) -> None:
        """야후에서 받아 캐시에 넣는다. 실패하면 캐시를 건드리지 않는다 — 직전 값이 있으면 그 값을 계속 보여준다
        (예전엔 실패 시 빈 값을 돌려줘 시황 띠가 잠깐 비었다)."""
        symbol = meta["symbol"]
        now = time.time()
        payload = self._empty(meta)
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
            # 한 항목이 실패해도 나머지는 보여준다. 실패는 캐시하지 않는다(직전 값 유지, 없으면 빈 값).
            logging.warning(f"market snapshot fetch failed: {symbol} {e}")
            return

        _cache[symbol] = (now, payload)

    @staticmethod
    def _rate(last: float, base: float):
        return round((last - base) / base * 100, 2) if base else None
