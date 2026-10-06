"""ccxt 캔들 조회 공통 로직 — 거래소별 클라이언트(upbit/binance)가 같이 쓴다.

반환 DataFrame 규약(거래소 무관):
  columns = datetime, open, high, low, close, volume
  datetime = 봉 시작 시각, KST tz-naive Timestamp (업비트·바이낸스 모두 일봉 경계가 KST 09:00)
"""
from __future__ import annotations

import time

import pandas as pd

OHLCV_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


def to_ms(ts) -> int:
    """tz-naive 는 KST 로 보고 epoch ms 로 변환."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Seoul")
    return int(t.timestamp() * 1000)


def to_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=OHLCV_COLUMNS)
    df["datetime"] = (pd.to_datetime(df["datetime"], unit="ms", utc=True)
                      .dt.tz_convert("Asia/Seoul").dt.tz_localize(None))
    return (df.drop_duplicates("datetime")
              .sort_values("datetime", ignore_index=True))


def fetch_range(exchange, market: str, timeframe: str, since, until=None, *,
                page_limit: int, page_sleep: float, drop_incomplete: bool = True) -> pd.DataFrame:
    """since ~ until(기본: 현재) 구간을 page_limit 봉씩 페이징해서 받는다.

    since/until 은 tz-naive 면 KST 로 해석한다.
    거래가 없던 시간대에 봉을 만들지 않는 거래소(업비트)는 빈 봉이 행 자체로 없다(채우지 않음).
    drop_incomplete=True 면 아직 마감되지 않은 마지막 봉을 버린다(백테스트 look-ahead 방지).
    """
    step_ms = exchange.parse_timeframe(timeframe) * 1000
    cursor = to_ms(since)
    end_ms = to_ms(until) if until is not None else int(time.time() * 1000)

    rows: list = []
    while cursor < end_ms:
        page = exchange.fetch_ohlcv(market, timeframe=timeframe, since=cursor, limit=page_limit)
        if page:
            rows.extend(r for r in page if r[0] < end_ms)
            cursor = max(page[-1][0] + step_ms, cursor + step_ms)
        else:
            # 상장 전이거나 장기간 거래 공백 — 한 페이지만큼 건너뛴다
            cursor += step_ms * page_limit
        time.sleep(page_sleep)

    df = to_frame(rows) if rows else pd.DataFrame(columns=OHLCV_COLUMNS)
    if drop_incomplete and len(df):
        now_kst = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None)
        df = df[df["datetime"] + pd.Timedelta(milliseconds=step_ms) <= now_kst]
    return df.reset_index(drop=True)
