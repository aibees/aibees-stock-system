from app.domain.dao.tradeCandleDataDao import TradeCandleDataDao
from app.domain.dto.userCoinInfo import UserCoinInfo
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.upbit.UpbitCcxt import CcxtUpbit
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config.database import dbConn
from app.ext_services.upbit.component.UpbitService import UpbitService
from app.ext_services.yfinance.yfEngine import yfEngine

timeframe = '1h'
session = dbConn.get_session()
daoImpl = TradeCandleDataDao()
serviceImpl = UpbitService()

def to_ms(dt_str: str, tz: str = "Asia/Seoul") -> int:
    # dt_str 예: "2025-11-06 12:00:00"
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(tz))
    return int(dt.timestamp() * 1000)

"""
UPBIT CCXT에서 실제 OHLCV 데이터 가져와 저장하기
"""

def upbit_ohlcv(code: str, start_dt: str):
    upbit = CcxtUpbit('3EEwAjHTHbyxTq4r0DP4MfGYF2XoAtmdRCWJSvfX', 'QtIf0MFGODp36oxxBZoF9zTn3MqEq06bvzjkycrk')

    since = to_ms(start_dt)
    return upbit.getOHLCVWithSince(code, '1h', since)


def yf_ohlcv(code: str):
    yf = yfEngine()
    start_date = '2025-01-01'
    end_date = '2026-02-14'

    return yf.getOHLCV(code, start_date, end_date)


def kis_ohlcv(code: str):
    kis = KisEngine()
    start_date = '2025-02-13'
    end_date = '2026-02-19'

    return kis.getOHLCV(code, start_date, end_date)

def test(code: str):
    # ohlcv = upbit_ohlcv(code)
    # ohlcv = yf_ohlcv(code)
    ohlcv = kis_ohlcv(code)

    for row in ohlcv.itertuples():
        coin_info = UserCoinInfo()
        coin_info.coin_code = code
        coin_info.datetime = row.datetime
        coin_info.open = float(row.open)
        coin_info.high = float(row.high)
        coin_info.low = float(row.low)
        coin_info.close = float(row.close)
        coin_info.volume = float(row.volume)

        daoImpl.upsert_candle_data(session, coin_info)

    session.commit()