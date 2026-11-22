"""
차트 퀴즈 지표 계산(numpy). 서버가 전부 계산해 문제에 동결하고, 화면은 그리기만 한다(명세 4-⑦).

모든 함수는 길이가 같은 배열을 돌려주고, 아직 계산할 수 없는 앞부분은 NaN 이다.
가격 지표는 가격 배율에 비례하므로 정규화한 종가(기준일 = 100)로 계산해도 결과가 같다(RSI 는 배율과 무관).
"""
import numpy as np


def sma(x: np.ndarray, p: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < p:
        return out
    c = np.cumsum(np.insert(x.astype(float), 0, 0.0))
    out[p - 1:] = (c[p:] - c[:-p]) / p
    return out


def ema(x: np.ndarray, p: int) -> np.ndarray:
    """첫 값부터 시작하는 지수이동평균(화면 트레이닝 수업의 MACD 와 같은 방식)."""
    out = np.empty(len(x))
    a = 2.0 / (p + 1)
    for i, v in enumerate(x.astype(float)):
        out[i] = v if i == 0 else a * v + (1 - a) * out[i - 1]
    return out


def rsi(close: np.ndarray, p: int = 14) -> np.ndarray:
    """Wilder RSI."""
    n = len(close)
    out = np.full(n, np.nan)
    if n <= p:
        return out
    d = np.diff(close.astype(float))
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    ag = gain[:p].mean()
    al = loss[:p].mean()
    out[p] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(p + 1, n):
        ag = (ag * (p - 1) + gain[i - 1]) / p
        al = (al * (p - 1) + loss[i - 1]) / p
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    m = ema(close, fast) - ema(close, slow)
    s = ema(m, signal)
    # 초기 구간은 EMA 가 덜 쌓여 의미가 없다 — 긴 쪽 기간만큼 비운다
    m[:slow - 1] = np.nan
    s[:slow + signal - 2] = np.nan
    return m, s, m - s


def bollinger(close: np.ndarray, p: int = 20, k: float = 2.0):
    mid = sma(close, p)
    sd = np.full(len(close), np.nan)
    for i in range(p - 1, len(close)):
        sd[i] = close[i + 1 - p:i + 1].std()   # 모표준편차(화면 수업과 같다)
    return mid + k * sd, mid, mid - k * sd


def volume_ratio(vol: np.ndarray, p: int = 20) -> np.ndarray:
    """그날 거래량 ÷ 직전 p일(그날 제외) 평균 거래량."""
    prev = np.full(len(vol), np.nan)
    avg = sma(vol.astype(float), p)
    prev[1:] = avg[:-1]
    with np.errstate(divide='ignore', invalid='ignore'):
        r = vol / prev
    r[~np.isfinite(r)] = np.nan
    return r


def compute_all(close: np.ndarray) -> dict:
    """문제 스냅샷에 넣는 지표 묶음(정규화한 종가 기준)."""
    m, s, h = macd(close)
    up, mid, lo = bollinger(close)
    return {
        "ma": {str(p): sma(close, p) for p in (5, 20, 60, 120)},
        "rsi14": rsi(close, 14),
        "macd": {"macd": m, "signal": s, "hist": h},
        "bollinger": {"upper": up, "mid": mid, "lower": lo},
    }
