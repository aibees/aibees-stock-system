"""
bt_private_line_rebound.py — 실전(PRIVATE) 후보 연구 ②: '하락하다가 특정 라인에서 반등'을 라인 자체로 잡기.

배경(2026-11-14 사용자): 2파는 되돌림 구조와 추세선 돌파가 있어야 해서, 최근처럼 하락하다 특정 라인에서
반등하는 자리를 못 잡는다. 앞 실험(bt_private_rebound)은 반등을 '거래량 2배 돌파'로 확인한 뒤 다음 날 사고
손절을 -8% 고정으로 둬서, 라인 근처에서 사는 효과와 라인 아래 손절을 보지 못했다.
여기서는 같은 반등 신호를 놓고 '저점이 라인 위였나 / 아무 데나였나'를 비교해 라인이 의미가 있는지 본다.

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다)
    하락 저점 j : 20봉 최저가이면서, 직전 20봉 최고가 대비 15% 이상 내려온 봉(하락하다가).
    반등 신호 i : j 뒤 5봉 안, 그 사이 j 저가를 깨지 않고, 종가 > j 고가 이고 양봉인 첫 봉. j 하나에 신호 하나.
    라인(저점 j 의 저가가 닿은 라인, 겹칠 수 있음)
      fib_swing : 2파와 같은 ATR14×4 스윙의 최근 상승 구간(L0→H1, i 시점에 확정된 것, H1 < j)의 되돌림
                  0.382/0.5/0.618/0.786/0.886/1.0 중 하나와 ±0.03 이내. 사이에 있으면 '라인 사이'(대조군).
      fib_major : 최근 120봉 최고가 H 와 그 앞 250봉 최저가 L 의 큰 상승 구간(H/L ≥ 1.2, j 가 H 이후 최저)의
                  같은 되돌림 비율 ±0.03. 사이에 있으면 '라인 사이'.
      prior_low : j 기준 60~500봉 전 최저가 ±3% (장기 전저점 지지).
      ma120 / ma240 : 그 이평 ±2%.
      none      : 위 어디에도 안 닿음.
    폭락 맥락 : j 저가가 직전 250봉 최고가 대비 -40% 이하.
매매 — D+1 시가 매수, 수수료 0.22%
    X1 고정 : +15% 익절 / -8% 손절 / 10거래일 (앞 실험들과 같음) → 같은 날 필터 통과 전 종목 평균 대비 초과수익.
    X2 라인 손절 : 손절 = j 저가 × 0.98(라인 깨짐), +15% 익절, 20거래일. 시가가 손절가 아래면 매수 안 함.
필터: 종가 >= 1,000원, 20일 평균 거래대금 >= 5억, 시총 >= 1,000억, 보통주, 관리·정지(현재) 제외, 250봉 이상.
한계: 현재 상장 종목만(상폐 폭락주 빠짐 → 폭락 맥락이 좋게 나올 수 있음), 슬리피지 없음, 같은 봉에서 손절·익절이
      둘 다 닿으면 손절로 본다, 라인 종류·허용폭은 임의 고정.

사용
    poetry run python -m app.test.bt_private_line_rebound --sameday <같은날 기준 pkl>
    poetry run python -m app.test.bt_private_line_rebound --sameday <pkl> --report-only
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, outcome, FEE, WARMUP, MIN_PRICE, MIN_AMOUNT, MIN_CAP  # noqa: E402
from stock_shared.strategy.wave2_breakout import MULT, MIN_PCT  # noqa: E402

OUT = os.path.join(CACHE, 'private')
LEVELS = np.array([0.382, 0.5, 0.618, 0.786, 0.886, 1.0])
TOL = 0.03
CRASH = -0.40
_G = {}


def _init(meta):
    _G.update(meta)


def zigzag(high, low, a):
    """확정 스윙 [(type, idx, price, confirm_i)]. wave2_breakout 과 같은 규칙."""
    n = len(high)
    piv, direction, ext_i, hi_i, lo_i = [], 0, 0, 0, 0
    thr = lambda i, ref: max(a[i] * MULT, ref * MIN_PCT / 100)  # noqa: E731
    for i in range(1, n):
        if direction == 0:
            if high[i] > high[hi_i]:
                hi_i = i
            if low[i] < low[lo_i]:
                lo_i = i
            if lo_i < hi_i and high[hi_i] - low[lo_i] >= thr(i, low[lo_i]):
                piv.append(('L', lo_i, low[lo_i], i)); direction, ext_i = 1, hi_i
            elif hi_i < lo_i and high[hi_i] - low[lo_i] >= thr(i, high[hi_i]):
                piv.append(('H', hi_i, high[hi_i], i)); direction, ext_i = -1, lo_i
        elif direction > 0:
            if high[i] > high[ext_i]:
                ext_i = i
            elif high[ext_i] - low[i] >= thr(i, high[ext_i]):
                piv.append(('H', ext_i, high[ext_i], i)); direction, ext_i = -1, i
        else:
            if low[i] < low[ext_i]:
                ext_i = i
            elif high[i] - low[ext_i] >= thr(i, low[ext_i]):
                piv.append(('L', ext_i, low[ext_i], i)); direction, ext_i = 1, i
    return piv


def swing_leg(piv, j, i):
    """i 시점에 확정된 H 중 j 보다 앞선 최근 것과 그 앞 L. (L0, H1, iH) 또는 None."""
    for k in range(len(piv) - 1, 0, -1):
        t, idx, p, conf = piv[k]
        if t == 'H' and idx < j and conf <= i and piv[k - 1][0] == 'L':
            return piv[k - 1][2], p, idx
    return None


def level_hit(depth):
    """되돌림 깊이 → (가까운 라인, 라인 위 여부). 0.35~1.03 밖이면 (nan, None)."""
    if not (LEVELS[0] - TOL <= depth <= LEVELS[-1] + TOL):
        return np.nan, None
    k = int(np.argmin(np.abs(LEVELS - depth)))
    return LEVELS[k], bool(abs(LEVELS[k] - depth) <= TOL)


def scan(o, h, l, c, v):
    """반등 신호 [(i, j)]."""
    n = len(c)
    lo20 = pd.Series(l).rolling(20).min().to_numpy()
    hi20 = pd.Series(h).rolling(21).max().to_numpy()
    out = []
    for j in range(25, n - 1):
        if l[j] > lo20[j] or hi20[j] / l[j] - 1 < 0.15:
            continue
        for i in range(j + 1, min(j + 6, n)):
            if l[i] < l[j]:
                break
            if c[i] > h[j] and c[i] > o[i]:
                out.append((i, j))
                break
    return out


def x2_line(o, h, l, c, i, stop, T=0.15, H=20):
    """라인 손절 매매. (수익, 결과, 위험폭) 또는 None(시가가 손절가 아래)."""
    e = o[i + 1]
    if e <= stop:
        return None
    risk = 1 - stop / e
    for k in range(i + 1, i + H + 1):
        if l[k] <= stop:
            px = stop if k == i + 1 else min(o[k], stop)
            return px / e - 1 - FEE, 'F', risk
        if h[k] >= e * (1 + T):
            px = e * (1 + T) if k == i + 1 else max(o[k], e * (1 + T))
            return px / e - 1 - FEE, 'W', risk
    return c[i + H] / e - 1 - FEE, 'N', risk


def run_stock(path):
    code = os.path.basename(path)[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return [], []
    df = pd.read_pickle(path).reset_index(drop=True)
    n = len(df)
    if n < WARMUP + 25:
        return [], []
    c, v = df['close'].to_numpy(float), df['volume'].to_numpy(float)
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    cap = c * _G['shares'][code]
    idx = np.arange(n)
    ok = (idx >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (cap >= MIN_CAP) & (idx < n - 21)
    return events_from_df(df, code, ok)


def events_from_df(df, code, ok):
    """일봉 df(datetime/open/high/low/close/volume) → (반등 신호 행들, 유니버스 (날짜, 변동성)). ok = 신호를 받을 봉."""
    from stock_shared.chart_analysis.indicators import atr as atr_fn
    n = len(df)
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    dates = df['datetime'].astype(str).str[:10].tolist()
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    piv = zigzag(h, l, a)
    ma120 = pd.Series(c).rolling(120).mean().to_numpy()
    ma240 = pd.Series(c).rolling(240).mean().to_numpy()
    v20 = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    lr = np.diff(np.log(c), prepend=np.nan)
    vol20 = pd.Series(lr).rolling(20).std().to_numpy()

    ev = []
    for i, j in scan(o, h, l, c, v):
        if not ok[i]:
            continue
        lj = l[j]
        d = {'code': code, 'date': dates[i], 'year': dates[i][:4], 'jd': dates[j], 'wait': i - j,
             'dd': lj / h[max(0, j - 250):j + 1].max() - 1, 'dist': c[i] / lj - 1,
             'vr': v[i] / v20[i] if v20[i] > 0 else np.nan, 'vol20': vol20[i]}
        # fib_swing
        leg = swing_leg(piv, j, i)
        d['sw_depth'], d['sw_lv'], d['sw_hit'] = np.nan, np.nan, None
        if leg is not None and j - leg[2] >= 3 and l[leg[2] + 1:j].min(initial=np.inf) >= lj:
            L0, H1, _ = leg
            if H1 > L0:
                dep = (H1 - lj) / (H1 - L0)
                d['sw_depth'] = dep
                d['sw_lv'], d['sw_hit'] = level_hit(dep)
        # fib_major
        d['mj_depth'], d['mj_lv'], d['mj_hit'] = np.nan, np.nan, None
        w0 = max(0, j - 120)
        iH = w0 + int(np.argmax(h[w0:j + 1]))
        if iH < j and l[iH:j].min(initial=np.inf) >= lj:
            v0 = max(0, iH - 250)
            iL = v0 + int(np.argmin(l[v0:iH + 1]))
            if iL < iH and h[iH] / l[iL] >= 1.2:
                dep = (h[iH] - lj) / (h[iH] - l[iL])
                d['mj_depth'] = dep
                d['mj_lv'], d['mj_hit'] = level_hit(dep)
        # prior_low / MA
        d['pl_hit'] = bool(j >= 560 and abs(lj / l[j - 500:j - 60].min() - 1) <= 0.03)
        d['m120_hit'] = bool(ma120[j] == ma120[j] and abs(lj / ma120[j] - 1) <= 0.02)
        d['m240_hit'] = bool(ma240[j] == ma240[j] and abs(lj / ma240[j] - 1) <= 0.02)
        d['sup'] = lj
        if i + 21 < n:
            r15, x15, _ = outcome(o, h, l, c, i, 0.15)
            d['x1'], d['x1r'] = r15, x15
            t = x2_line(o, h, l, c, i, lj * 0.98)
            d['x2'], d['x2r'], d['risk'] = (t if t else (np.nan, None, np.nan))
        ev.append(d)
    uni = [(dates[k], vol20[k]) for k in np.flatnonzero(ok) if dates[k] >= '2022-10-01']
    return ev, uni


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
    ev, uni = [], []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for k, (e, u) in enumerate(pool.imap_unordered(run_stock, paths, chunksize=8), 1):
            ev += e; uni += u
            if k % 500 == 0:
                print(f"[scan] {k}/{len(paths)} · 신호 {len(ev)}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    ev = pd.DataFrame(ev)
    med = pd.DataFrame(uni, columns=['date', 'vol20']).groupby('date').vol20.median()
    ev['vol_med'] = ev.date.map(med)
    ev.to_pickle(os.path.join(OUT, 'line_rebound_events.pkl'))
    return ev


def _ci(x, codes, n=1000):
    rng = np.random.default_rng(7)
    by = {k: x[(codes == k).values].values for k in codes.unique()}
    ks = list(by)
    bs = [np.concatenate([by[k] for k in rng.choice(ks, len(ks))]).mean() for _ in range(n)]
    return np.percentile(bs, 5) * 100, np.percentile(bs, 95) * 100


def _diff_ci(a, b, n=1000):
    """두 군 평균 차이의 종목 단위 부트스트랩 90% 구간(군마다 따로 재표집)."""
    rng = np.random.default_rng(7)
    out = []
    ga = {k: g.values for k, g in a.groupby(level=0)}
    gb = {k: g.values for k, g in b.groupby(level=0)}
    ka, kb = list(ga), list(gb)
    for _ in range(n):
        ma = np.concatenate([ga[k] for k in rng.choice(ka, len(ka))]).mean()
        mb = np.concatenate([gb[k] for k in rng.choice(kb, len(kb))]).mean()
        out.append(ma - mb)
    return np.percentile(out, 5) * 100, np.percentile(out, 95) * 100


def line(lab, g, days):
    if len(g) < 20:
        print(f"  {lab:<30}{len(g):>6}  (표본 부족)")
        return
    lo, hi = _ci(g.x1 - g.base, g.code)
    yr = '/'.join(f"{g[g.year == y].x1.mean() * 100:+.1f}" if (g.year == y).sum() >= 5 else ' - '
                  for y in ('2023', '2024', '2025', '2026'))
    t = g[g.x2.notna()]
    print(f"  {lab:<30}{len(g):>6}{len(g) / days:>6.2f}{g.x1.mean() * 100:>+8.2f}%{(g.x1 - g.base).mean() * 100:>+8.2f}%p"
          f" [{lo:+.2f}~{hi:+.2f}]  {yr:<22}{t.x2.mean() * 100:>+7.2f}%{(t.x2r == 'W').mean() * 100:>5.0f}%"
          f"{(t.x2r == 'F').mean() * 100:>5.0f}%{t.risk.median() * 100:>6.1f}%")


def report(ev, sameday):
    ev = ev[ev.date.isin(sameday.index)].copy()
    ev['base'] = sameday.loc[ev.date].values
    days = len(sameday)
    ev['crash'] = ev.dd <= CRASH
    ev['sw_on'] = ev.sw_hit == True  # noqa: E712
    ev['sw_off'] = ev.sw_hit == False  # noqa: E712
    ev['mj_on'] = ev.mj_hit == True  # noqa: E712
    ev['mj_off'] = ev.mj_hit == False  # noqa: E712
    ev['any_line'] = ev.sw_on | ev.mj_on | ev.pl_hit | ev.m120_hit | ev.m240_hit
    print(f"반등 신호 {len(ev):,}건 ({ev.date.min()}~{ev.date.max()}, {days}거래일) · 같은 날 기준 = 필터 통과 전 종목 X1 평균")
    head = (f"  {'구분':<30}{'n':>6}{'하루':>6}{'X1매매당':>9}{'같은날대비':>10}  90% 구간        연도별 X1(23/24/25/26)  "
            f"{'X2매매당':>8}{'익절':>5}{'손절':>5}{'위험폭':>6}")
    print("\n[1] 라인 종류별 (겹침 허용)\n" + head)
    for lab, m in (('전체 반등 신호', ev.code.notna()), ('어느 라인이든 닿음', ev.any_line), ('라인 없음', ~ev.any_line),
                   ('fib_swing 라인 위', ev.sw_on), ('fib_swing 라인 사이', ev.sw_off),
                   ('fib_major 라인 위', ev.mj_on), ('fib_major 라인 사이', ev.mj_off),
                   ('장기 전저점', ev.pl_hit), ('120일선', ev.m120_hit), ('240일선', ev.m240_hit)):
        line(lab, ev[m], days)

    print("\n[2] 피보나치 되돌림 비율별 — 같은 구조 안에서 라인 위 vs 사이\n" + head)
    for fam in ('sw', 'mj'):
        print(f"  ── {'fib_swing' if fam == 'sw' else 'fib_major'}")
        for lv in LEVELS:
            line(f"{lv:.3f} 라인 위", ev[(ev[fam + '_lv'] == lv) & ev[fam + '_on']], days)
            line(f"{lv:.3f} 근처 사이", ev[(ev[fam + '_lv'] == lv) & ev[fam + '_off']], days)

    print("\n[3] 라인 위 − 라인 사이 차이 (종목 단위 부트스트랩 90%)")
    for fam, lab in (('sw', 'fib_swing'), ('mj', 'fib_major')):
        for clab, cm in (('전체', ev.code.notna()), ('폭락 맥락', ev.crash), ('폭락 아님', ~ev.crash)):
            on, off = ev[ev[fam + '_on'] & cm], ev[ev[fam + '_off'] & cm]
            for col, base in (('x1', True), ('x2', False)):
                a = (on[col] - (on.base if base else 0)).dropna(); a.index = on.loc[a.index, 'code']
                b = (off[col] - (off.base if base else 0)).dropna(); b.index = off.loc[b.index, 'code']
                lo, hi = _diff_ci(a, b, 500)
                print(f"  {lab:<10}{clab:<8}{col.upper()} 라인 위 n={len(a):>5} {a.mean() * 100:+.2f}% · 사이 n={len(b):>5} "
                      f"{b.mean() * 100:+.2f}% → 차이 {(a.mean() - b.mean()) * 100:+.2f}%p [{lo:+.2f}~{hi:+.2f}]")

    print("\n[4] 폭락 맥락으로 나눔\n" + head)
    for lab, m in (('라인 닿음 · 폭락', ev.any_line & ev.crash), ('라인 닿음 · 폭락 아님', ev.any_line & ~ev.crash),
                   ('라인 없음 · 폭락', ~ev.any_line & ev.crash), ('라인 없음 · 폭락 아님', ~ev.any_line & ~ev.crash)):
        line(lab, ev[m], days)

    print("\n[5] 신호일 종가가 저점에서 얼마나 떠 있나 (= 라인 손절까지 거리)\n" + head)
    for lab, m in (('라인 닿음 · 저점 +5% 이내', ev.any_line & (ev.dist <= .05)),
                   ('라인 닿음 · +5~10%', ev.any_line & (ev.dist > .05) & (ev.dist <= .10)),
                   ('라인 닿음 · +10%↑', ev.any_line & (ev.dist > .10)),
                   ('라인 없음 · 저점 +5% 이내', ~ev.any_line & (ev.dist <= .05)),
                   ('라인 없음 · +5~10%', ~ev.any_line & (ev.dist > .05) & (ev.dist <= .10)),
                   ('라인 없음 · +10%↑', ~ev.any_line & (ev.dist > .10))):
        line(lab, ev[m], days)

    print("\n[6] 라인 닿은 신호 안에서 변동성·거래량\n" + head)
    x = ev[ev.any_line]
    for lab, m in (('변동성 그날 중앙값 이상', x.vol20 >= x.vol_med), ('변동성 중앙값 미만', x.vol20 < x.vol_med),
                   ('거래량 2배↑', x.vr >= 2), ('거래량 1~2배', (x.vr >= 1) & (x.vr < 2)), ('거래량 1배 미만', x.vr < 1)):
        line(lab, x[m], days)
    x = ev[~ev.any_line]
    print("  ── (대조) 라인 없음")
    for lab, m in (('변동성 그날 중앙값 이상', x.vol20 >= x.vol_med), ('변동성 중앙값 미만', x.vol20 < x.vol_med)):
        line(lab, x[m], days)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--sameday', required=True, help='같은 날 전 종목 평균 피클(date, mean)')
    args = ap.parse_args()
    sd = pd.read_pickle(args.sameday).set_index('date')['mean']
    ev = pd.read_pickle(os.path.join(OUT, 'line_rebound_events.pkl')) if args.report_only else run()
    report(ev, sd)
