"""차트 분석용 기본 지표 — RSI(14), ATR(14). 둘 다 Wilder 평활(alpha=1/n)."""
import numpy as np
import pandas as pd


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
    gain = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    # pd.NA 로 바꾸면 object 열이 돼서 pandas 버전에 따라 astype(float) 이 터진다 — NaN 을 쓴다
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    # 하락이 한 번도 없던 구간(loss=0)은 100
    return out.where(loss != 0, 100.0)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
