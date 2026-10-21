"""스윙 고점·저점(ZigZag) — 장중 고가/저가 기준, 반전 폭은 ATR 배수.

stock_shared.strategy.reco_performance.zigzag 는 고정 % + 종가 기준이다(변동성 큰 종목에서 고저 기준이면
매 봉이 스윙이 되는 문제 때문). 여기서는 패턴·피보나치가 장중 고저를 써야 해서 고저 기준으로 하되,
반전 폭을 종목 변동성(ATR)에 비례시켜 같은 문제를 피한다. 하루 폭이 대략 1 ATR 이라 2.5 ATR 반전이면
한 봉으로는 스윙이 생기지 않는다.
"""
import pandas as pd

ATR_MULT = 2.5     # 반전 인정 폭 = ATR × 이 값
MIN_PCT = 3.0      # 단, 최소 이 %는 되돌려야 한다(변동성 아주 작은 종목 보정)


def find_swings(df: pd.DataFrame, atr: pd.Series, atr_mult: float = ATR_MULT, min_pct: float = MIN_PCT) -> list:
    """df: high/low/ymd 컬럼, 0..n-1 위치 인덱스. atr: 같은 길이.

    반환: [{'i', 'date', 'kind': 'H'|'L', 'price', 'confirmed'}] 시간순.
    마지막 원소는 아직 반전이 확인되지 않은 현재 극값(confirmed=False)이다.
    """
    n = len(df)
    if n < 3:
        return []
    high = df['high'].astype(float).to_numpy()
    low = df['low'].astype(float).to_numpy()
    dates = df['ymd'].astype(str).to_numpy()
    a = atr.bfill().fillna(0).to_numpy()

    def thr(i, ref):
        return max(a[i] * atr_mult, ref * min_pct / 100.0)

    pivots = []

    def push(i, kind, price, confirmed=True):
        pivots.append({'i': int(i), 'date': dates[i], 'kind': kind, 'price': float(price), 'confirmed': confirmed})

    # 방향 미정 구간: 처음 극값 대비 임계를 먼저 넘는 쪽으로 방향을 정한다
    direction = 0
    hi_i, lo_i = 0, 0
    ext_i = 0
    for i in range(1, n):
        if direction == 0:
            if high[i] > high[hi_i]:
                hi_i = i
            if low[i] < low[lo_i]:
                lo_i = i
            up = high[hi_i] - low[lo_i] >= thr(i, low[lo_i]) and lo_i < hi_i
            down = high[hi_i] - low[lo_i] >= thr(i, high[hi_i]) and hi_i < lo_i
            if up:
                push(lo_i, 'L', low[lo_i])
                direction, ext_i = 1, hi_i
            elif down:
                push(hi_i, 'H', high[hi_i])
                direction, ext_i = -1, lo_i
            continue

        if direction > 0:
            if high[i] > high[ext_i]:
                ext_i = i          # 고점 갱신 — 같은 봉에서 반전까지 보지 않는다
            elif high[ext_i] - low[i] >= thr(i, high[ext_i]):
                push(ext_i, 'H', high[ext_i])
                direction, ext_i = -1, i
        else:
            if low[i] < low[ext_i]:
                ext_i = i
            elif high[i] - low[ext_i] >= thr(i, low[ext_i]):
                push(ext_i, 'L', low[ext_i])
                direction, ext_i = 1, i

    if direction > 0:
        push(ext_i, 'H', high[ext_i], confirmed=False)
    elif direction < 0:
        push(ext_i, 'L', low[ext_i], confirmed=False)
    return pivots
