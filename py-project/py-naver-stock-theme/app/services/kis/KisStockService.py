"""
KisStockService.py — OHLCV DataFrame → 지표 계산

배치(py-stock-batch)의 KisStockService.compute_indicator_df를 그대로 포팅.
계산식 / 보조함수 로직 일체 변경 금지.
"""
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from stock_shared.dto.userOptionMeta import UserOptionMeta


class KisStockService:

    def compute_indicator_df(self, data: pd.DataFrame, user_info: UserOptionMeta) -> pd.DataFrame:

        df_open   = data['open'].astype(float)
        df_close  = data['close'].astype(float)
        df_high   = data['high'].astype(float)
        df_low    = data['low'].astype(float)
        df_volume = data['volume'].astype(float)

        # 1. 이동평균 (컬럼명은 ema이지만 실제 SMA)
        data['ema20']  = df_close.rolling(window=20).mean()
        data['ema60']  = df_close.rolling(window=60).mean()
        data['ema120'] = df_close.rolling(window=120).mean()

        # 2. Bollinger Band (20, 2σ)
        ma  = df_close.rolling(20).mean()
        std = df_close.rolling(20).std(ddof=0)
        data['bb_mid']   = ma
        data['bb_upper'] = ma + 2 * std
        data['bb_lower'] = ma - 2 * std
        data['bb_upper_chk'] = self.__check_than_bb('bb_upper', df_high,  data['bb_upper'], window=user_info.bb_over_recent_day)
        data['bb_lower_chk'] = self.__check_than_bb('bb_lower', df_low,   data['bb_lower'], window=user_info.bb_over_recent_day)
        data['bb_mid_breakout'] = self.__bb_mid_check(df_open, df_close, data['bb_mid'], user_info.delay_date)
        data['bb_width']     = data['bb_upper'] - data['bb_lower']
        data['bb_width_avg'] = data['bb_width'].rolling(window=20).mean()

        # Recent High
        data['recent_high'] = df_high.rolling(window=20).max()

        # 3. MACD (12, 26, 9)
        data['macd']   = df_close.ewm(span=12, adjust=False).mean() - df_close.ewm(span=26, adjust=False).mean()
        data['macd_s'] = data['macd'].ewm(span=9, adjust=False).mean()
        data['macd_lower_mean'] = self.__n_day_avg(data['macd'], 'lower')
        data['macd_upper_mean'] = self.__n_day_avg(data['macd'], 'upper')
        data['macd_recent_min'] = data['macd'].rolling(window=user_info.macd_recent_day, min_periods=user_info.macd_recent_day).min()
        data['macd_recent_max'] = data['macd'].rolling(window=user_info.macd_recent_day, min_periods=user_info.macd_recent_day).max()
        data['macd_g_cross_n']  = self.__n_day_cross_check('G', data['macd'], data['macd_s'], user_info.delay_date)
        data['macd_d_cross_n']  = self.__n_day_cross_check('D', data['macd'], data['macd_s'], user_info.delay_date)

        # 4. OBV
        data['obv']        = (np.sign(df_close.diff()) * df_volume).fillna(0).cumsum()
        data['obv_signal'] = data['obv'].rolling(window=9).mean()
        data['obv_g_cross_n'] = self.__n_day_cross_check('G', data['obv'], data['obv_signal'], user_info.delay_date)
        data['obv_d_cross_n'] = self.__n_day_cross_check('D', data['obv'], data['obv_signal'], user_info.delay_date)

        # 5. Volume
        prev_vol        = df_volume.shift(1)
        is_surge_today  = (df_volume >= prev_vol * float(user_info.vol_surge)) & (prev_vol > 0)
        data['vol_surge_n'] = is_surge_today.rolling(window=user_info.delay_date).max() == 1
        data['vol_avg']     = df_volume.rolling(window=20).mean()

        # 6. RSI (14, Wilder — ewm com=13)
        delta    = df_close.diff()
        gain     = delta.where(delta > 0, 0.0)
        loss     = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, float('nan'))
        data['rsi'] = (100 - (100 / (1 + rs))).fillna(50.0)

        # 7. ATR (14, Wilder)
        prev_close = df_close.shift(1)
        tr = pd.concat([
            (df_high - df_low),
            (df_high - prev_close).abs(),
            (df_low  - prev_close).abs(),
        ], axis=1).max(axis=1)
        data['atr']     = tr.ewm(alpha=1 / 14, adjust=False).mean()
        data['atr_pct'] = (data['atr'] / df_close).replace([np.inf, -np.inf], 0.0)

        # 8. Downtrend Ratio (DB 미저장 — 백테스터가 즉석 계산, 라이브에서만 사용)
        below_e60 = (df_close < data['ema60']).where(data['ema60'].notna())
        data['downtrend_ratio'] = below_e60.rolling(window=90, min_periods=20).mean()

        return data

    # ── 보조 함수 (배치 원본 그대로) ────────────────────────────────────

    def __check_than_bb(self, bb_type: str, target: pd.Series,
                        df_bb: pd.Series, window: int = 7) -> pd.Series:
        is_below = target > df_bb if bb_type == 'bb_upper' else target < df_bb
        return is_below.rolling(window=window, min_periods=1).max()

    def __n_day_avg(self, src: pd.Series, avg_type: str,
                   window: int = 120, order: int = 5) -> pd.Series:
        values     = src.values
        real_index = None

        if avg_type == 'lower':
            extrema_indexes = argrelextrema(values, np.less_equal, order=order)[0]
            real_index = extrema_indexes[values[extrema_indexes] < 0]
        elif avg_type == 'upper':
            extrema_indexes = argrelextrema(values, np.greater_equal, order=order)[0]
            real_index = extrema_indexes[values[extrema_indexes] > 0]
        else:
            return pd.Series(0.0, index=src.index)

        vertex_series = pd.Series(np.nan, index=src.index)
        vertex_series.iloc[real_index] = values[real_index]
        return vertex_series.rolling(window=window, min_periods=1).mean()

    def __n_day_cross_check(self, cross_type: str, data: pd.Series,
                            signal: pd.Series, n: int) -> pd.Series:
        prev_data   = data.shift(1)
        prev_signal = signal.shift(1)

        if cross_type == 'G':
            is_cross = (prev_data <= prev_signal) & (data > signal)
        elif cross_type == 'D':
            is_cross = (prev_data >= prev_signal) & (data < signal)
        else:
            return pd.Series('', index=data.index)

        has_cross_recent = is_cross.rolling(window=n).max() == 1
        result_array = np.where(has_cross_recent, cross_type, '')
        return pd.Series(result_array, index=data.index)

    def __bb_mid_check(self, df_open: pd.Series, df_close: pd.Series,
                       bb_mid: pd.Series, n: int) -> pd.Series:
        is_positive   = df_close > df_open
        mid_point     = (df_open + df_close) / 2

        is_upper_on_mid = (mid_point > bb_mid) & (abs(bb_mid - df_open) < abs(bb_mid - df_close))

        is_lower_cond_1 = (mid_point < bb_mid) & (
            (~is_positive & (abs(bb_mid - df_open) < abs(bb_mid - df_close))) |
            (is_positive  & (abs(bb_mid - df_open) > abs(bb_mid - df_close)))
        )
        is_lower_cond_2 = df_open < bb_mid
        is_lower_base   = is_lower_cond_1 | is_lower_cond_2

        is_breakout_day      = is_lower_base.shift(1) & (is_positive & is_upper_on_mid)
        has_breakout_recent  = is_breakout_day.rolling(window=n).max() == 1
        is_maintaining_today = df_close > bb_mid

        return has_breakout_recent & is_maintaining_today
