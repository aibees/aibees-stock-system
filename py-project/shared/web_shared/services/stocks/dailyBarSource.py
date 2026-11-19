"""
DB 일봉(stock_ohlcv_daily)을 KisEngine 과 같은 모양의 DataFrame 으로 돌려준다.

KIS 를 쓰지 않는 서버(양봉상회, KIS_ENABLED=false)의 차트·추천 기록용. 배치(StockOhlcvDailyJob)가 매일
적재하므로 **전 거래일까지**만 있고 장중 봉은 없다. 가격은 수정주가(KRX 단일 기준)라 KIS 차트와 같다.

반환 열: ymd('YYYY-MM-DD 00:00:00'), open, high, low, close, volume — KisEngine.__produce_data 와 같다.
주봉·월봉은 일봉을 묶어 만든다. 날짜 이름은 KIS 와 맞춘다(주봉 = 그 주 첫 거래일, 월봉 = 그 달 마지막 거래일).
진행 중인 주·달도 지금까지의 봉으로 포함한다(KIS 도 부분봉을 준다).
"""
from datetime import date, timedelta

import pandas as pd

from stock_shared.dao.stockOhlcvDailyDao import StockOhlcvDailyDao
from web_shared.constants.Literal import Literal

_dao = StockOhlcvDailyDao()

# 봉 1개가 덮는 대략의 달력 일수(+여유). 필요한 봉 수만큼만 DB 에서 읽는다.
_CALENDAR_DAYS_PER_BAR = {'day': 1.6, 'week': 7.5, 'month': 31.5, 'year': 366}


def _empty():
    return pd.DataFrame(columns=[Literal.YMD, 'open', 'high', 'low', 'close', 'volume'])


def _to_frame(rows: list) -> pd.DataFrame:
    if not rows:
        return _empty()
    df = pd.DataFrame(rows)
    df = df.rename(columns={'open_price': 'open', 'high_price': 'high',
                            'low_price': 'low', 'close_price': 'close'})
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    for col in ('open', 'high', 'low', 'close', 'volume'):
        df[col] = df[col].astype('int64')
    return df[['trade_date', 'open', 'high', 'low', 'close', 'volume']]


def _resample(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    if unit == 'day' or df.empty:
        out = df.copy()
        out['label'] = out['trade_date']
    else:
        key = {'week': df['trade_date'].dt.to_period('W-SUN'),
               'month': df['trade_date'].dt.to_period('M'),
               'year': df['trade_date'].dt.to_period('Y')}[unit]
        grouped = df.groupby(key, sort=True)
        out = pd.DataFrame({
            'open': grouped['open'].first(),
            'high': grouped['high'].max(),
            'low': grouped['low'].min(),
            'close': grouped['close'].last(),
            'volume': grouped['volume'].sum(),
            # KIS 봉 날짜: 주봉은 첫 거래일, 월·년봉은 마지막 거래일
            'label': grouped['trade_date'].first() if unit == 'week' else grouped['trade_date'].last(),
        }).reset_index(drop=True)
    out[Literal.YMD] = out['label'].dt.strftime('%Y-%m-%d 00:00:00')
    return out[[Literal.YMD, 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)


def recent_bars(session, stock_code: str, count: int = 200, unit: str = 'day') -> pd.DataFrame:
    """최근 count 봉(오름차순). KisEngine.get_ohlcv_period_unit 대신 쓴다."""
    unit = (unit or 'day').lower()
    if unit not in _CALENDAR_DAYS_PER_BAR:
        raise ValueError(f"지원하지 않는 unit='{unit}'. (day|week|month|year 중 하나)")
    from_date = date.today() - timedelta(days=int(count * _CALENDAR_DAYS_PER_BAR[unit]) + 10)
    bars = _resample(_to_frame(_dao.select_bars(session, stock_code, from_date=from_date)), unit)
    return bars.tail(count).reset_index(drop=True)


def bars_between(session, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """start_date~end_date('YYYY-MM-DD') 일봉. KisEngine.getOHLCV 대신 쓴다."""
    rows = _dao.select_bars(session, stock_code, from_date=start_date, to_date=end_date)
    return _resample(_to_frame(rows), 'day')
