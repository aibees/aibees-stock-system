from datetime import date, datetime, timedelta

import pandas as pd

from app.common.constants.Literal import Literal
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.config.database import dbConn
from app.domain.dto.userOptionMeta import UserOptionMeta
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.component.KisStockService import KisService
from app.ext_services.upbit.component.UpbitScoreService import UpbitScoreService
from app.ext_services.upbit.component.UpbitService import UpbitService
from app.ext_services.upbit.component.UpbitUserService import UpbitUserService

timeframe = '1h'
session = dbConn.get_session()
daoImpl = TradeCandleDataDao()
serviceImpl = UpbitService()
kisServiceImpl = KisService()
userServiceImpl = UpbitUserService()
scoreServiceImpl = UpbitScoreService()

# KIS 백테스트용
kis = KisEngine()
stockServiceImpl = StockService()
stockUserServiceImpl = UserService()

# UserCoinInfo 속성명 : DataFrame 컬럼상수 (KIS 지표 매핑)
FIELD_MAP_KIS = {
    'open': Literal.OPEN,
    'high': Literal.HIGH,
    'low': Literal.LOW,
    'close': Literal.CLOSE,
    'volume': Literal.VOLUME,
    'vol_surge_n': Literal.VOL_SURGE_N,
    'datetime': Literal.DATETIME,
    # --- 지표 ---
    'ema20': Literal.EMA_20,
    'ema60': Literal.EMA_60,
    'ema120': Literal.EMA_120,
    'bb_mid': Literal.BB_MID,
    'bb_lower': Literal.BB_LOWER,
    'bb_lower_chk': Literal.BB_LOWER_CHK,
    'bb_upper': Literal.BB_UPPER,
    'bb_upper_chk': Literal.BB_UPPER_CHK,
    'bb_width': Literal.BB_WIDTH,
    'bb_width_avg': Literal.BB_WIDTH_AVG,
    'bb_mid_breakout': Literal.BB_MID_BREAKOUT,
    'recent_high': Literal.RECENT_HIGH,
    'macd': Literal.MACD,
    'macd_s': Literal.MACD_S,
    'macd_lower_mean': Literal.MACD_LOWER_MEAN,
    'macd_upper_mean': Literal.MACD_UPPER_MEAN,
    'macd_recent_min': Literal.MACD_RECENT_MIN,
    'macd_recent_max': Literal.MACD_RECENT_MAX,
    'macd_g_cross_n': Literal.MACD_G_CROSS_N,
    'macd_d_cross_n': Literal.MACD_D_CROSS_N,
    'obv': Literal.OBV,
    'obv_signal': Literal.OBV_SIGNAL,
    'obv_g_cross_n': Literal.OBV_G_CROSS_N,
    'obv_d_cross_n': Literal.OBV_D_CROSS_N,
    'rsi': Literal.RSI,
    'atr': Literal.ATR,
}


def _row_to_coin_info(coin_code: str, row) -> UserCoinInfo:
    """compute_indicator_df 결과의 한 행(itertuples)을 UserCoinInfo로 변환"""
    coin_info = UserCoinInfo()
    coin_info.coin_code = coin_code
    for attr_name, col_name in FIELD_MAP_KIS.items():
        coin_info.__setattr__(attr_name, getattr(row, col_name, 0.0))
    return coin_info


def test_backtest_insert(end_date: str, lookback_days: int = 250):
    """
    end_date(YYYY-MM-DD)만 주면 stock master 전체 종목에 대해
    KisEngine -> KisStockService 로 지표를 계산하여 trade_candle_data 에 적재한다. (백테스트용)
    """
    start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    user_info: UserOptionMeta = stockUserServiceImpl.get_user_options(session)
    stock_list = stockServiceImpl.get_stock_master_list(session, 'batches')
    print(f'[backtest] {start_date} ~ {end_date} / 대상 종목 {len(stock_list)}건', flush=True)

    for idx, stock in enumerate(stock_list):
        stock_code = stock.get('stock_code')
        stock_name = stock.get('stock_name')

        try:
            ohlcv = kis.getOHLCV(stock_code, start_date, end_date)
            if ohlcv is None or ohlcv.empty:
                print(f'[{idx}] 조회 불가: {stock_name}({stock_code})', flush=True)
                continue

            computed = kisServiceImpl.compute_indicator_df(ohlcv, user_info)
            computed.fillna(0.0, inplace=True)

            for row in computed.itertuples(index=False):
                coin_info = _row_to_coin_info(stock_code, row)
                daoImpl.upsert_candle_data_kis(session, coin_info)

            session.commit()
            print(f'[{idx}] 적재 완료: {stock_name}({stock_code}) {len(computed)}건', flush=True)

        except Exception as e:
            session.rollback()
            print(f'[{idx}] 실패: {stock_name}({stock_code}) -> {e}', flush=True)
            continue


def test_backtest_insert_one(stock_code: str, end_date: str, lookback_days: int = 250):
    """단일 종목 버전 (디버깅용)"""
    start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    user_info: UserOptionMeta = stockUserServiceImpl.get_user_options(session)

    ohlcv = kis.getOHLCV(stock_code, start_date, end_date)
    if ohlcv is None or ohlcv.empty:
        print(f'조회 불가: {stock_code}', flush=True)
        return

    computed = kisServiceImpl.compute_indicator_df(ohlcv, user_info)
    computed.fillna(0.0, inplace=True)

    for row in computed.itertuples(index=False):
        coin_info = _row_to_coin_info(stock_code, row)
        daoImpl.upsert_candle_data_kis(session, coin_info)

    session.commit()
    print(f'적재 완료: {stock_code} {len(computed)}건', flush=True)

def test(coin: str):
    df = pd.DataFrame(daoImpl.select_candle_data(session, { 'coin_code': coin }))

    user_info = UserOptionMeta()
    user_info.vol_surge = 3.0
    user_info.delay_date = 5

    computed = kisServiceImpl.compute_indicator_df(df, user_info)
    computed.fillna(0.0, inplace=True)

    # 1. 매핑 정의 (UserCoinInfo 속성명 : DataFrame 컬럼상수)
    #    이 딕셔너리는 루프 밖에서 한 번만 정의하면 됩니다.
    field_map1 = {
        'close': Literal.CLOSE,
        'open': Literal.OPEN,
        'high': Literal.HIGH,
        'low': Literal.LOW,
        'volume': Literal.VOLUME,
        'vol_low_th': Literal.VOL_LOW_TH,
        'vol_high_th': Literal.VOL_HIGH_TH,
        'datetime': Literal.DATETIME,
        # --- 지표 ---
        'ema20': Literal.EMA_20,
        'ema60': Literal.EMA_60,
        'ema120': Literal.EMA_120,
        'ema120_slope': Literal.EMA_120_SLOPE,

        'bb_mid': Literal.BB_MID,
        'bb_lower': Literal.BB_LOWER,
        'bb_lower_chk': Literal.BB_LOWER_CHK,
        'bb_upper': Literal.BB_UPPER,
        'bb_upper_chk': Literal.BB_UPPER_CHK,
        'bb_width': Literal.BB_WIDTH,
        'bb_width_avg': Literal.BB_WIDTH_AVG,

        'macd': Literal.MACD,
        'macd_s': Literal.MACD_S,
        'macd_lower_mean': Literal.MACD_LOWER_MEAN,
        'macd_upper_mean': Literal.MACD_UPPER_MEAN,
        'macd_recent_min': Literal.MACD_RECENT_MIN,
        'macd_recent_max': Literal.MACD_RECENT_MAX,

        'fs_k': Literal.FS_K,
        'fs_d': Literal.FS_D,

        'atr': Literal.ATR,
        'atr_pct': Literal.ATR_PCT,
        'roc': Literal.ROC,

        'obv': Literal.OBV,
        'obv_signal': Literal.OBV_SIGNAL,
        'obv_cross': Literal.OBV_CROSS,
        'obv_ema_slow': Literal.OBV_EMA_SLOW,
        'obv_recent_min': Literal.OBV_RECENT_MIN,
        'obv_recent_max': Literal.OBV_RECENT_MAX,

        'rsi': Literal.RSI,
        'rsi_signal': Literal.RSI_SIGNAL,

        'vol_ratio': Literal.VOL_RATIO,
    }

    field_map_kis = {
        'open': Literal.OPEN,
        'high': Literal.HIGH,
        'low': Literal.LOW,
        'close': Literal.CLOSE,
        'volume': Literal.VOLUME,
        'vol_surge_n': Literal.VOL_SURGE_N,
        'datetime': Literal.DATETIME,
        # --- 지표 ---
        'ema20': Literal.EMA_20,
        'ema60': Literal.EMA_60,
        'ema120': Literal.EMA_120,

        'bb_mid': Literal.BB_MID,
        'bb_lower': Literal.BB_LOWER,
        'bb_lower_chk': Literal.BB_LOWER_CHK,
        'bb_upper': Literal.BB_UPPER,
        'bb_upper_chk': Literal.BB_UPPER_CHK,
        'bb_mid_breakout': Literal.BB_MID_BREAKOUT,

        'macd': Literal.MACD,
        'macd_s': Literal.MACD_S,
        'macd_lower_mean': Literal.MACD_LOWER_MEAN,
        'macd_upper_mean': Literal.MACD_UPPER_MEAN,
        'macd_recent_min': Literal.MACD_RECENT_MIN,
        'macd_recent_max': Literal.MACD_RECENT_MAX,
        'macd_g_cross_n': Literal.MACD_G_CROSS_N,
        'macd_d_cross_n': Literal.MACD_D_CROSS_N,

        'obv': Literal.OBV,
        'obv_signal': Literal.OBV_SIGNAL,
        'obv_g_cross_n': Literal.OBV_G_CROSS_N,
        'obv_d_cross_n': Literal.OBV_D_CROSS_N
    }

    # itertuples가 iterrows보다 빠릅니다. index가 필요 없다면 index=False
    for row in computed.itertuples(index=False):
        coin_info = UserCoinInfo()
        coin_info.coin_code = coin  # DF에 없는 고정값 할당

        # 매핑을 이용한 일괄 할당
        for attr_name, col_name in field_map_kis.items():
            # getattr(row, 컬럼명)으로 값 가져오기
            # 주의: DataFrame 컬럼명에 공백/특수문자가 있다면 itertuples가 이름을 변경했을 수 있음
            val = getattr(row, col_name, 0.0)
            setattr(coin_info, attr_name, val)

        # 이제 coin_info_list에 변환된 객체들이 담겨 있습니다.
        # scoreServiceImpl.get_indicator_score_trend(coin_info)
        # scoreServiceImpl.get_indicator_score_momentum(coin_info)
        # scoreServiceImpl.get_indicator_score_volume(coin_info)
        # scoreServiceImpl.get_indicator_score_volatility(coin_info)
        #
        # scoreServiceImpl.get_final_strategy(coin_info)

        daoImpl.update_candle_data_kis(session, coin_info)

    session.commit()
