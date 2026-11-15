"""
bt_private_rebound.py — 실전(PRIVATE) 후보 연구 ①: 폭락 뒤 '깊은 2차 바닥'과 'V자 반등' 진입 기준.

배경(2026-11-14): 이번 주 급등 196종목 중 188종목이 고점 대비 -40%↓ 폭락주였고, 2파 모델(되돌림 0.382~0.786)은
되돌림 0.786 초과 2차 바닥과 새 저점 직후 V반등을 구조상 못 잡았다. 두 모양을 고정 정의로 5년 전 종목에서 센다.

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다). 스윙·추세선·거래량은 wave2_breakout 과 같다.
    폭락 맥락  : 기준 저점이 직전 250봉 최고가 대비 -40% 이하
    A 2차 바닥 : 확정 스윙 L0 → H1 뒤, 2파 최저가 L0 위(저점 높임), 되돌림 (H1-최저)/(H1-L0) 를 1.0 미만까지 허용,
                 H1 에서 내려오는 하락 추세선을 종가가 처음 넘고 거래량 >= 직전 20일 평균 × 2.
                 되돌림 구간으로 나눈다: 기존(0.382~0.786) / 깊음(0.786~1.0).  L0 의 폭락 여부로도 나눈다.
    B V자 반등 : 120봉 최저가가 최근 10봉 안(오늘 제외)에서 나왔고, 오늘 종가 > 직전 5봉 최고가, 양봉,
                 거래량 >= 직전 20일 평균 × 2. 같은 저점에서는 첫 신호만. 그 저점의 폭락 여부로 나눈다.
    시장 폭    : 그날 필터 통과 종목 중 종가 > 20일선 비율. 30% 미만(투매 국면) / 이상으로 나눠 본다.
평가 — bt_wave2_trendline 과 같음
    D+1 시가 매수, +15% 먼저 익절 / -8% 먼저 손절 / 10거래일(ret15), 실전 매도 규칙 근사(live8, 손절 -8%).
    같은 날 필터 통과 전 종목 평균(ret15) 대비 초과수익, 종목 단위 부트스트랩 90% 구간, 연도별.
필터: 종가 >= 1,000원, 20일 평균 거래대금 >= 5억, 시총 >= 1,000억, 보통주, 관리·정지(현재) 제외, 250봉 이상.
한계: 캐시는 현재 상장 종목뿐(상폐 종목 없음 → 폭락주 성과가 좋게 나올 수 있다), 슬리피지 없음.

사용
    poetry run python -m app.test.bt_private_rebound
    poetry run python -m app.test.bt_private_rebound --report-only
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, OUT as W2, outcome, WARMUP, MIN_PRICE, MIN_AMOUNT, MIN_CAP  # noqa: E402
from stock_shared.strategy.wave2_breakout import MULT, MIN_PCT  # noqa: E402

OUT = os.path.join(CACHE, 'private')
CRASH = -0.40
VOL_MIN = 2.0
_G = {}


def _init(meta):
    _G.update(meta)


def scan_deep(high, low, close, vol, a):
    """2파 구조에서 되돌림 상한만 1.0 미만으로 넓힌 추세선 돌파. [(i, vr, retr, since_h1, i0)]"""
    v20 = pd.Series(vol).rolling(20).mean().shift(1).to_numpy()
    n = len(close)
    piv, direction, ext_i, hi_i, lo_i = [], 0, 0, 0, 0
    ctx, out = None, []
    thr = lambda i, ref: max(a[i] * MULT, ref * MIN_PCT / 100)  # noqa: E731
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
        if new_pivot == 'H' and len(piv) >= 2 and piv[-2][0] == 'L':
            ctx = {'i0': piv[-2][1], 'p0': piv[-2][2], 'i1': piv[-1][1], 'p1': piv[-1][2], 'tl': False}
        if ctx is None:
            continue
        i0, p0, i1, p1 = ctx['i0'], ctx['p0'], ctx['i1'], ctx['p1']
        lo_since = low[i1 + 1:i + 1].min() if i > i1 else p1
        if lo_since <= p0:
            ctx = None
            continue
        if close[i] > p1:
            ctx = None
            continue
        retr = (p1 - lo_since) / (p1 - p0) if p1 > p0 else 0
        if not (0.382 <= retr < 1.0 and i - i1 >= 5) or ctx['tl']:
            continue
        js = np.arange(i1 + 2, i)
        if len(js) < 2:
            continue
        slope = np.max((high[js] - p1) / (js - i1))
        if slope >= 0:
            continue
        line_t, line_y = p1 + slope * (i - i1), p1 + slope * (i - 1 - i1)
        if close[i] > line_t and close[i - 1] <= line_y:
            vr = vol[i] / v20[i] if v20[i] and v20[i] > 0 else np.nan
            out.append((i, vr, retr, i - i1, i0))
            ctx['tl'] = True
    return out


def scan_v(open_, high, low, close, vol):
    """V자 반등. [(i, vr, i_low, rebound)] — 같은 120봉 저점에서는 첫 신호만."""
    v20 = pd.Series(vol).rolling(20).mean().shift(1).to_numpy()
    n = len(close)
    out, used = [], set()
    for i in range(130, n):
        w0 = i - 119
        i_low = w0 + int(np.argmin(low[w0:i + 1]))
        if i_low == i or i - i_low > 9 or i_low in used:
            continue
        if not (close[i] > high[i - 5:i].max() and close[i] > open_[i]):
            continue
        vr = vol[i] / v20[i] if v20[i] and v20[i] > 0 else np.nan
        if not (vr == vr and vr >= VOL_MIN):
            continue
        used.add(i_low)
        out.append((i, vr, i_low, close[i] / low[i_low] - 1))
    return out


def run_stock(path):
    from stock_shared.chart_analysis.indicators import atr as atr_fn
    from stock_shared.strategy.reco import RecoStrategy
    from app.test.bt_reco_stop import sim_live
    code = os.path.basename(path)[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return [], []
    df = pd.read_pickle(path).reset_index(drop=True)
    n = len(df)
    if n < WARMUP + 25:
        return [], []
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    cap = c * _G['shares'][code]
    idx = np.arange(n)
    ok = (idx >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (cap >= MIN_CAP) & (idx < n - 21)
    dates = df['datetime'].astype(str).str[:10].tolist()
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    sma20 = pd.Series(c).rolling(20).mean().to_numpy()
    s8 = RecoStrategy(); s8.stop_loss_pct = 0.08
    recs = None

    def dd_at(k):
        lo = max(0, k - 250)
        return l[k] / h[lo:k + 1].max() - 1

    def row(kind, i, extra):
        nonlocal recs
        r15, x15, m15 = outcome(o, h, l, c, i, 0.15)
        if recs is None:
            df2 = df.copy(); df2['coin'] = code; df2['datetime'] = dates
            recs = df2.to_dict('records')
        t = sim_live(s8, recs, i)
        d = {'kind': kind, 'code': code, 'date': dates[i], 'year': dates[i][:4], 'ret15': r15, 'res15': x15,
             'mup15': m15, 'live8': t['ret_net'] if t else np.nan}
        d.update(extra)
        return d

    ev = []
    for i, vr, retr, since_h1, i0 in scan_deep(h, l, c, v, a):
        if ok[i] and vr == vr and vr >= VOL_MIN:
            ev.append(row('A', i, {'vr': vr, 'retr': retr, 'since_h1': since_h1, 'dd': dd_at(i0)}))
    for i, vr, i_low, reb in scan_v(o, h, l, c, v):
        if ok[i]:
            ev.append(row('B', i, {'vr': vr, 'dd': dd_at(i_low), 'from_low': i - i_low, 'rebound': reb}))
    breadth = [(dates[i], bool(c[i] > sma20[i])) for i in np.flatnonzero(ok)]
    return ev, breadth


def run():
    from sqlalchemy import create_engine
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')
                       | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(x) for k, x in zip(ms.stock_code, ms.listed_shares) if x}, 'bad': bad}
    paths = sorted(os.path.join(CACHE, 'stocks', x) for x in os.listdir(os.path.join(CACHE, 'stocks')))
    ev, br = [], []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for k, (e, b) in enumerate(pool.imap_unordered(run_stock, paths, chunksize=8), 1):
            ev += e; br += b
            if k % 500 == 0:
                print(f"[scan] {k}/{len(paths)} · 이벤트 {len(ev)}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    ev = pd.DataFrame(ev)
    breadth = pd.DataFrame(br, columns=['date', 'above']).groupby('date').above.mean()
    ev['breadth'] = ev.date.map(breadth)
    ev.to_pickle(os.path.join(OUT, 'rebound_events.pkl'))
    breadth.to_pickle(os.path.join(OUT, 'breadth.pkl'))
    return ev


def _ci(g, col, base_col=None):
    rng = np.random.default_rng(7)
    x = g[col] - (g[base_col] if base_col else 0)
    by = {k: x[(g.code == k).values].values for k in g.code.unique()}
    ks = list(by)
    bs = [np.concatenate([by[k] for k in rng.choice(ks, len(ks))]).mean() for _ in range(1000)]
    return np.percentile(bs, 5) * 100, np.percentile(bs, 95) * 100


def report(ev):
    print(f"이벤트 {len(ev)}건 ({ev.date.min()}~{ev.date.max()})")
    w2 = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    w2 = w2[(w2.kind == 'tl') & (w2.vol_ratio >= 2)]
    sdm = SAMEDAY
    ev = ev[ev.date.isin(sdm.index)].copy()
    ev['base'] = sdm.loc[ev.date].values
    groups = [
        ('참고: 기존 2파(전 종목)', None),
        ('A 기존 되돌림 · 폭락 맥락', (ev.kind == 'A') & (ev.retr <= 0.786) & (ev.dd <= CRASH)),
        ('A 깊은 되돌림 · 폭락 맥락', (ev.kind == 'A') & (ev.retr > 0.786) & (ev.dd <= CRASH)),
        ('A 깊은 되돌림 · 폭락 아님', (ev.kind == 'A') & (ev.retr > 0.786) & (ev.dd > CRASH)),
        ('B V반등 · 폭락 맥락', (ev.kind == 'B') & (ev.dd <= CRASH)),
        ('B V반등 · 폭락 아님', (ev.kind == 'B') & (ev.dd > CRASH)),
    ]
    days = len(sdm)
    print(f"\n{'구분':<24}{'n':>6}{'하루':>6}{'매매당':>9}{'익절':>6}{'손절':>6}{'실전규칙':>9}{'같은날대비':>10}  90% 구간      연도별 매매당(23/24/25/26)")
    for lab, m in groups:
        if m is None:
            g = w2[w2.date.isin(sdm.index)].copy(); g['base'] = sdm.loc[g.date].values
            ex = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8']]
            g = g.merge(ex, on=['code', 'date'], how='left')
        else:
            g = ev[m]
        if not len(g):
            continue
        lo, hi = _ci(g, 'ret15', 'base')
        yr = '/'.join(f"{g[g.year == y].ret15.mean() * 100:+.1f}" if (g.year == y).any() else ' - ' for y in ('2023', '2024', '2025', '2026'))
        print(f"{lab:<24}{len(g):>6}{len(g) / days:>6.2f}{g.ret15.mean() * 100:>+8.2f}%{(g.res15 == 'W').mean() * 100:>5.0f}%"
              f"{(g.res15 == 'F').mean() * 100:>5.0f}%{g.live8.mean() * 100:>+8.2f}%{(g.ret15 - g.base).mean() * 100:>+9.2f}%p"
              f"  {lo:+.2f}~{hi:+.2f}   {yr}")
    print("\n[시장 폭으로 나눔 — 그날 20일선 위 종목 비율 30% 미만(투매) vs 이상]")
    for lab, m in groups[1:]:
        g = ev[m]
        for blab, bm in (('투매', g.breadth < 0.30), ('평시', g.breadth >= 0.30)):
            x = g[bm]
            if len(x) >= 20:
                lo, hi = _ci(x, 'ret15', 'base')
                print(f"  {lab:<24}{blab}  n={len(x):>5} 매매당 {x.ret15.mean() * 100:+.2f}% 실전 {x.live8.mean() * 100:+.2f}% "
                      f"같은날대비 {(x.ret15 - x.base).mean() * 100:+.2f}%p [{lo:+.2f}~{hi:+.2f}] 투매일 {x.date.nunique()}일")
    print("\n[V반등 — 거래량 배수·저점 대비 반등폭]")
    b = ev[(ev.kind == 'B') & (ev.dd <= CRASH)]
    for lab, m in (('거래량 2~3배', b.vr < 3), ('거래량 3~5배', (b.vr >= 3) & (b.vr < 5)), ('거래량 5배↑', b.vr >= 5),
                   ('반등 <15%', b.rebound < .15), ('반등 15~30%', (b.rebound >= .15) & (b.rebound < .30)), ('반등 30%↑', b.rebound >= .30)):
        x = b[m]
        if len(x):
            print(f"  {lab:<12} n={len(x):>5} 매매당 {x.ret15.mean() * 100:+.2f}% 실전 {x.live8.mean() * 100:+.2f}% 같은날대비 {(x.ret15 - x.base).mean() * 100:+.2f}%p")


SAMEDAY = None

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--sameday', required=True, help='같은 날 전 종목 평균 피클(date, mean)')
    args = ap.parse_args()
    SAMEDAY = pd.read_pickle(args.sameday).set_index('date')['mean']
    ev = pd.read_pickle(os.path.join(OUT, 'rebound_events.pkl')) if args.report_only else run()
    report(ev)
