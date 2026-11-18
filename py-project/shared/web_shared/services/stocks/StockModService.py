
import numpy as np
import pandas as pd

from app.utils.constants.Literal import Literal


class StockModService:

    def __init__(self):
        self.name = 'StockModService'

    def createAddChannel(self, data: pd.DataFrame) -> pd.DataFrame:
        ####################################################################
        # Constants
        ####################################################################
        df_open  = data[Literal.OPEN].astype(float)
        df_close = data[Literal.CLOSE].astype(float)
        df_high  = data[Literal.HIGH].astype(float)
        df_low   = data[Literal.LOW].astype(float)
        df_volume = data[Literal.VOLUME].astype(float)
        df_prev_close = df_close.shift(1)

        data['RATE'] = ((df_close - df_prev_close) / df_prev_close * 100).round(2).astype(str) + "%"

        ####################################################################
        # 1. SMA (단순 이동평균)
        ####################################################################
        data[Literal.SMA_5]   = df_close.rolling(window=5).mean()
        data[Literal.SMA_20]  = df_close.rolling(window=20).mean()
        data[Literal.SMA_60]  = df_close.rolling(window=60).mean()
        data[Literal.SMA_120] = df_close.rolling(window=120).mean()

        ####################################################################
        # 2. Bollinger Band
        ####################################################################
        ma  = df_close.rolling(20).mean()
        std = df_close.rolling(20).std(ddof=0)

        data[Literal.BB_MID]   = ma
        data[Literal.BB_UPPER] = ma + 2 * std
        data[Literal.BB_LOWER] = ma - 2 * std

        ####################################################################
        # 3. MACD (12, 26) / Signal (9)
        ####################################################################
        ema12 = df_close.ewm(span=12, adjust=False).mean()
        ema26 = df_close.ewm(span=26, adjust=False).mean()
        macd  = ema12 - ema26

        data[Literal.MACD]        = macd.round(4)
        data[Literal.MACD_SIGNAL] = macd.ewm(span=9, adjust=False).mean().round(4)

        ####################################################################
        # 4. OBV / OBV Signal (9)
        ####################################################################
        direction = np.sign(df_close.diff().fillna(0))
        obv = (df_volume * direction).cumsum()

        data[Literal.OBV]        = obv
        data[Literal.OBV_SIGNAL] = obv.ewm(span=9, adjust=False).mean()

        ####################################################################
        # 5. RSI (14) / RSI Signal (9)
        ####################################################################
        delta = df_close.diff()
        gain  = delta.clip(lower=0)
        loss  = (-delta).clip(lower=0)

        # Wilder's smoothing (alpha = 1/14)
        avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()

        rs  = avg_gain / avg_loss.replace(0, float('nan'))
        rsi = (100 - (100 / (1 + rs))).round(2)

        data[Literal.RSI]        = rsi
        data[Literal.RSI_SIGNAL] = rsi.ewm(span=6, adjust=False).mean().round(2)

        return data
