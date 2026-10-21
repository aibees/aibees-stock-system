"""2파 하락 추세선 돌파 + 거래량 — 매수추천 종합순위(StockBuyCheckJob)와 백테스트(app/test/bt_wave2_trendline.py)의 단일 출처.

엘리엇 1파(L0→H1) 뒤 2파 조정의 하락 추세를 깨고 3파가 시작되는 날을 찾는다.
    스윙      : 하루씩 진행하는 ZigZag, 장중 고가·저가, 반전폭 = max(ATR14 × 4, 3%)  (그날까지 확정된 스윙만)
    2파 구간  : 확정 스윙 L0 → H1 다음, 종가가 아직 H1 을 넘지 않은 동안
    추세선    : H1 에서 출발해 H1 이후 (어제까지의) 고가를 전부 위에서 덮는 가장 완만한 직선(기울기 < 0 만)
    돌파(tl)  : 종가 > 추세선 이고 전날 종가 <= 추세선 인 첫 봉(2파 구간당 1회)
                조건: H1 이후 5봉 이상, 2파 최저 > L0, 되돌림 (H1 - 최저)/(H1 - L0) ∈ [0.382, 0.786], 종가 < H1
    거래량    : 돌파일 거래량 / 직전 20일 평균. 매수 신호는 VOL_MIN(2배) 이상.
검증(2022-10~2026-10 전 종목, +15%/-8%/10일): 거래량 2배↑ 1,249건 매매당 +0.74%(종목 단위 90% +0.27~+1.23, 2023~26 매년 +),
현행 매도 규칙(손절 -8%)으로는 +1.07%. 거래량이 클수록 좋아져 순위는 거래량 배수 큰 순.
"""
import numpy as np
import pandas as pd

from stock_shared.chart_analysis.indicators import atr as atr_fn

MULT, MIN_PCT = 4.0, 3.0
VOL_MIN = 2.0
# 후보 필터(백테스트와 동일)
MIN_BARS, MIN_PRICE, MIN_AMOUNT, MIN_CAP = 250, 1000, 5e8, 1000e8


def scan(df: pd.DataFrame, a: np.ndarray) -> list:
    """[(kind, i, vol_ratio, retr, since_h1, h1)] — kind: tl(추세선 돌파) / ma20(20일선 돌파) / h1(1파 고점 돌파)."""
    high, low, close = (df[k].to_numpy(float) for k in ('high', 'low', 'close'))
    vol = df['volume'].to_numpy(float)
    ma20 = pd.Series(close).rolling(20).mean().to_numpy()
    v20 = pd.Series(vol).rolling(20).mean().shift(1).to_numpy()
    n = len(df)
    piv, direction, ext_i, hi_i, lo_i = [], 0, 0, 0, 0
    ctx = None          # 2파 구간 상태: dict(i0, p0, i1, p1, done_tl, done_ma, done_h1)
    out = []

    def thr(i, ref):
        return max(a[i] * MULT, ref * MIN_PCT / 100)

    for i in range(1, n):
        new_pivot = None
        if direction == 0:
            if high[i] > high[hi_i]:
                hi_i = i
            if low[i] < low[lo_i]:
                lo_i = i
            if lo_i < hi_i and high[hi_i] - low[lo_i] >= thr(i, low[lo_i]):
                piv.append(('L', lo_i, low[lo_i])); direction, ext_i = 1, hi_i
            elif hi_i < lo_i and high[hi_i] - low[lo_i] >= thr(i, high[hi_i]):
                piv.append(('H', hi_i, high[hi_i])); direction, ext_i = -1, lo_i; new_pivot = 'H'
        elif direction > 0:
            if high[i] > high[ext_i]:
                ext_i = i
            elif high[ext_i] - low[i] >= thr(i, high[ext_i]):
                piv.append(('H', ext_i, high[ext_i])); direction, ext_i = -1, i; new_pivot = 'H'
        else:
            if low[i] < low[ext_i]:
                ext_i = i
            elif high[i] - low[ext_i] >= thr(i, low[ext_i]):
                piv.append(('L', ext_i, low[ext_i])); direction, ext_i = 1, i

        # 새 고점 H1 이 확정되면 2파 구간 시작(그 앞이 L0)
        if new_pivot == 'H' and len(piv) >= 2 and piv[-2][0] == 'L':
            ctx = {'i0': piv[-2][1], 'p0': piv[-2][2], 'i1': piv[-1][1], 'p1': piv[-1][2],
                   'tl': False, 'ma': False, 'h1': False}
        if ctx is None:
            continue
        i0, p0, i1, p1 = ctx['i0'], ctx['p0'], ctx['i1'], ctx['p1']
        lo_since = low[i1 + 1:i + 1].min() if i > i1 else p1
        if lo_since <= p0:                 # 2파가 1파 시작점을 깸 → 해석 무효
            ctx = None
            continue
        retr = (p1 - lo_since) / (p1 - p0) if p1 > p0 else 0
        structure_ok = 0.382 <= retr <= 0.786 and i - i1 >= 5
        vr = vol[i] / v20[i] if v20[i] and v20[i] > 0 else np.nan

        if close[i] > p1:                  # 1파 고점 돌파 — 여기서 2파 구간 종료
            if structure_ok and not ctx['h1']:
                out.append(('h1', i, vr, retr, i - i1, p1))
            ctx = None
            continue
        if not structure_ok:
            continue
        # 하락 추세선: H1 이후 (어제까지) 고가를 위에서 덮는 가장 완만한 선
        js = np.arange(i1 + 2, i)
        if len(js) >= 2 and not ctx['tl']:
            slope = np.max((high[js] - p1) / (js - i1))
            if slope < 0:
                line_t, line_y = p1 + slope * (i - i1), p1 + slope * (i - 1 - i1)
                if close[i] > line_t and close[i - 1] <= line_y:
                    out.append(('tl', i, vr, retr, i - i1, p1))
                    ctx['tl'] = True
        if not ctx['ma'] and ma20[i] == ma20[i] and close[i] > ma20[i] and close[i - 1] <= ma20[i - 1]:
            out.append(('ma20', i, vr, retr, i - i1, p1))
            ctx['ma'] = True
    return out


def today_signal(df: pd.DataFrame, listed_shares, bad: bool, code: str) -> dict | None:
    """df(일봉 오름차순, open/high/low/close/volume)의 **마지막 봉**이 매수 신호면 정보 dict, 아니면 None."""
    n = len(df)
    if n < MIN_BARS or bad or not str(code).endswith('0') or not listed_shares:
        return None
    c = df['close'].to_numpy(float)
    v = df['volume'].to_numpy(float)
    amt20 = float(np.mean(c[-20:] * v[-20:]))
    cap = c[-1] * float(listed_shares)
    if c[-1] < MIN_PRICE or amt20 < MIN_AMOUNT or cap < MIN_CAP:
        return None
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    for kind, i, vr, retr, since_h1, h1 in scan(df.reset_index(drop=True), a):
        if kind == 'tl' and i == n - 1 and vr == vr and vr >= VOL_MIN:
            return {'vol_ratio': float(vr), 'retr': float(retr), 'since_h1': int(since_h1),
                    'h1': float(h1), 'to_h1': float(h1 / c[-1] - 1), 'cap': cap, 'amt20': amt20}
    return None
