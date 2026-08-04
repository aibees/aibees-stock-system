import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
import io, pytz, pprint, matplotlib

from app.common.constants.Literal import Literal
from app.domain.dao.userTestDao import UserTestDao

matplotlib.use('Agg')
from app.domain.dao.userMasterDao import UserMasterDao
from app.domain.dto.userOptionMeta import UserOptionMeta

kst = pytz.timezone("Asia/Seoul")
choices = ['G', 'D']

class KisService:
    ####################################################
    # __init__
    # - UserService init
    ####################################################
    def __init__(self):
        self.__name__ = 'UpbitService'
        self.userMasterDaoImpl = UserMasterDao()
        self.userTestDaoImpl = UserTestDao()

    def compute_indicator_df(self, data: pd.DataFrame, user_info: UserOptionMeta) -> pd.DataFrame:

        ####################################################################
        # Constants
        ####################################################################
        df_open = data[Literal.OPEN].astype(float)
        df_close = data[Literal.CLOSE].astype(float)
        df_high = data[Literal.HIGH].astype(float)
        df_low = data[Literal.LOW].astype(float)
        df_volume = data[Literal.VOLUME].astype(float)

        ####################################################################
        # 1. ma(단순 이동평균)
        ####################################################################
        data[Literal.EMA_20] = df_close.rolling(window=20).mean()
        data[Literal.EMA_60] = df_close.rolling(window=60).mean()
        data[Literal.EMA_120] = df_close.rolling(window=120).mean()

        ####################################################################
        # 1-1. HMA (Hull Moving Average) — KospiStrategy2 추세 코어
        #  HMA(n) = WMA( 2*WMA(n/2) - WMA(n), sqrt(n) )
        #  체결강도(chegyul_strength)는 일봉에 없으므로 여기서 계산하지 않고,
        #  매매 잡이 KIS inquire-ccnl(CTTR/STRN) 값을 별도 주입한다.
        ####################################################################
        hma_p = 20
        _half = self.__wma(df_close, max(1, hma_p // 2))
        _full = self.__wma(df_close, hma_p)
        data[Literal.HMA] = self.__wma(2 * _half - _full, max(1, int(round(hma_p ** 0.5))))
        data[Literal.HMA_SLOPE] = data[Literal.HMA] - data[Literal.HMA].shift(1)


        ####################################################################
        # 2. Bollinger Band
        ####################################################################
        ma = df_close.rolling(20).mean()
        std = df_close.rolling(20).std(ddof=0)

        data[Literal.BB_MID] = ma
        data[Literal.BB_UPPER]  = ma + 2 * std
        data[Literal.BB_LOWER]  = ma - 2 * std
        data[Literal.BB_UPPER_CHK] = self.__check_than_bb(Literal.BB_UPPER, df_high, data[Literal.BB_UPPER], window=user_info.bb_over_recent_day)
        data[Literal.BB_LOWER_CHK] = self.__check_than_bb(Literal.BB_LOWER, df_low, data[Literal.BB_LOWER], window=user_info.bb_over_recent_day)
        data[Literal.BB_MID_BREAKOUT] = self.__bb_mid_check(df_open, df_close, data[Literal.BB_MID], user_info.delay_date)

        ####################################################################
        # 3. MACD (12,26,9)
        ####################################################################
        data[Literal.MACD] = df_close.ewm(span=12, adjust=False).mean() - df_close.ewm(span=26, adjust=False).mean()
        data[Literal.MACD_S] = data[Literal.MACD].ewm(span=9, adjust=False).mean()
        data[Literal.MACD_LOWER_MEAN] = self.__n_day_avg(data[Literal.MACD],'lower')
        data[Literal.MACD_UPPER_MEAN] = self.__n_day_avg(data[Literal.MACD],'upper')

        data[Literal.MACD_RECENT_MIN] = data[Literal.MACD].rolling(window=user_info.macd_recent_day, min_periods=user_info.macd_recent_day).min()
        data[Literal.MACD_RECENT_MAX] = data[Literal.MACD].rolling(window=user_info.macd_recent_day, min_periods=user_info.macd_recent_day).max()

        data[Literal.MACD_G_CROSS_N] = self.__n_day_cross_check('G', data[Literal.MACD], data[Literal.MACD_S], user_info.delay_date)
        data[Literal.MACD_D_CROSS_N] = self.__n_day_cross_check('D', data[Literal.MACD], data[Literal.MACD_S], user_info.delay_date)


        ####################################################################
        # OBV
        ####################################################################
        data[Literal.OBV] = (np.sign(df_close.diff()) * data[Literal.VOLUME]).fillna(0).cumsum()
        data[Literal.OBV_SIGNAL] = data[Literal.OBV].rolling(window=9).mean()

        data[Literal.OBV_G_CROSS_N] = self.__n_day_cross_check('G', data[Literal.OBV], data[Literal.OBV_SIGNAL], user_info.delay_date)
        data[Literal.OBV_D_CROSS_N]=  self.__n_day_cross_check('D', data[Literal.OBV], data[Literal.OBV_SIGNAL], user_info.delay_date)


        ####################################################################
        # VOLUME
        ####################################################################
        prev_vol = df_volume.shift(1)
        is_surge_today = (df_volume >= prev_vol * float(user_info.vol_surge)) & (prev_vol > 0)
        data[Literal.VOL_SURGE_N] = is_surge_today.rolling(window=user_info.delay_date).max() == 1
        # 20일 평균 거래량 (상대 거래량 필터용)
        data[Literal.VOL_AVG] = df_volume.rolling(window=20).mean()

        ####################################################################
        # RSI (14)
        ####################################################################
        delta = df_close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float('nan'))
        data[Literal.RSI] = (100 - (100 / (1 + rs))).fillna(50.0)

        ####################################################################
        # ATR (14, Wilder) — 매도 변동성 기준
        ####################################################################
        prev_close = df_close.shift(1)
        tr = pd.concat([
            (df_high - df_low),
            (df_high - prev_close).abs(),
            (df_low - prev_close).abs(),
        ], axis=1).max(axis=1)
        data[Literal.TR] = tr
        data[Literal.ATR] = tr.ewm(alpha=1 / 14, adjust=False).mean()
        data[Literal.ATR_PCT] = (data[Literal.ATR] / df_close).replace([np.inf, -np.inf], 0.0)

        ####################################################################
        # BB Width
        ####################################################################
        data[Literal.BB_WIDTH] = data[Literal.BB_UPPER] - data[Literal.BB_LOWER]
        data[Literal.BB_WIDTH_AVG] = data[Literal.BB_WIDTH].rolling(window=20).mean()

        ####################################################################
        # Recent High (20일 rolling 최고가 — 눌림목 되돌림 깊이 계산용)
        ####################################################################
        data[Literal.RECENT_HIGH] = df_high.rolling(window=20).max()

        ####################################################################
        # Downtrend Ratio (추세국면 분류기)
        #  최근 90봉 중 close < ema60 비율. KospiStrategy1 의 적응형 게이트가
        #  이 값으로 하락국면(>=0.70) 여부를 판정한다. ema60 미산출 봉은 제외.
        #  (백테스트 경로는 KisBacktester 가 동일 로직으로 즉석 주입)
        ####################################################################
        below_e60 = (df_close < data[Literal.EMA_60]).where(data[Literal.EMA_60].notna())
        data[Literal.DOWNTREND_RATIO] = below_e60.rolling(window=90, min_periods=20).mean()

        return data

    """
    가중이동평균(WMA) — HMA 계산용. 최근값에 큰 가중치.
    """
    def __wma(self, src: pd.Series, period: int) -> pd.Series:
        weights = np.arange(1, period + 1)
        return src.rolling(window=period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    """
    특정 금액이 bb_lower / bb_upper 나갔다가 들어오는지 체크하는 def
    """
    def __check_than_bb(self, bb_type: str, target: pd.Series, df_bb: pd.Series, window: int = 7) -> pd.Series:
        is_below = target > df_bb if bb_type == Literal.BB_UPPER else target < df_bb
        return is_below.rolling(window=window, min_periods=1).max()

    """
    n 일 간의 특정 데이터 평균
    """
    def __n_day_avg(self, src: pd.Series, avg_type: str, window: int = 120, order: int = 5) -> pd.Series:
        # 1. 최근 데이터
        values = src.values
        real_index = None

        if avg_type == 'lower' :
            extrema_indexes = argrelextrema(values, np.less_equal, order=order)[0]
            real_index = extrema_indexes[values[extrema_indexes] < 0]

        elif avg_type == 'upper' :
            extrema_indexes = argrelextrema(values, np.greater_equal, order=order)[0]
            real_index = extrema_indexes[values[extrema_indexes] > 0]
        else :
            return pd.Series(0.0, index=src.index)

        # 3. 값 추출
        # iloc을 사용하여 인덱스 위치로 값 가져오기
        vertex_series = pd.Series(np.nan, index=src.index)
        vertex_series.iloc[real_index] = values[real_index]

        return vertex_series.rolling(window=window, min_periods=1).mean()



    """
    최근 n일 간 Golden cross 있었는지 체크
    """
    def __n_day_cross_check(self, cross_type: str, data: pd.Series, signal: pd.Series, n: int) -> pd.Series:
        prev_obv = data.shift(1)
        prev_signal = signal.shift(1)

        is_cross = None
        if cross_type == 'G':
            is_cross = (prev_obv <= prev_signal) & (data > signal)
        elif cross_type == 'D':
            is_cross = (prev_obv >= prev_signal) & (data < signal)
        else:
            return None

        has_golden_recent = is_cross.rolling(window=n).max() == 1

        # 조건이 참이면 'G', 거짓이면 '' 반환
        result_array = np.where(has_golden_recent, cross_type, '')

        # np.where의 결과는 numpy 배열이므로, 원래의 인덱스를 유지하도록 Series로 묶어줍니다.
        return pd.Series(result_array, index=data.index)

    def __bb_mid_check(self, df_open: pd.Series, df_close: pd.Series, bb_mid: pd.Series, n: int) -> pd.Series:
        # 1. 캔들 기본 지표
        is_positive = df_close > df_open
        mid_point = (df_open + df_close) / 2

        # 2. 상단/하단 조건 (기존 로직 동일하게 유지)
        is_upper_on_mid = (mid_point > bb_mid) & (abs(bb_mid - df_open) < abs(bb_mid - df_close))

        is_lower_cond_1 = (mid_point < bb_mid) & (
                (~is_positive & (abs(bb_mid - df_open) < abs(bb_mid - df_close))) |
                (is_positive & (abs(bb_mid - df_open) > abs(bb_mid - df_close)))
        )
        is_lower_cond_2 = df_open < bb_mid
        is_lower_base = is_lower_cond_1 | is_lower_cond_2

        # 3. [핵심 1] '완벽한 돌파 당일'을 하나의 이벤트로 정의합니다.
        # 조건: 어제는 하단에 있었고 & 오늘은 양봉(is_positive)이면서 상단에 위치함
        is_breakout_day = is_lower_base.shift(1) & (is_positive & is_upper_on_mid)

        # 4. [핵심 2] 최근 n일 이내에 이 '완벽한 돌파 이벤트'가 있었는지 확인합니다.
        has_breakout_recent = is_breakout_day.rolling(window=n).max() == 1

        # 5. [추가] 체크 당일(오늘)의 조건
        # 당일은 음봉이어도 상관없습니다(is_positive 확인 안 함).
        # 단, 종가가 bb_mid선 아래로 다시 깨고 내려가지 않고 '위에 유지'되어야 합니다.
        is_maintaining_today = df_close > bb_mid

        # 6. 최종 시그널 반환
        return has_breakout_recent & is_maintaining_today
