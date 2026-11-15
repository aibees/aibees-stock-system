"""
bt_private_30m.py — 실전(PRIVATE) 후보 연구 ②: 고급(2파) 신호에 30분봉 돌파 신호가 순위·진입에 의미가 있나.

대상: 2파 하락 추세선 돌파 + 거래량 2배↑ 신호(bt_wave2_trendline events) 중 1분봉 캐시(collect_wave2_minutes,
2025-11-10~)가 신호일 D 와 다음 날 D+1 모두 있는 것. 고급 = 그중 shape 백분위 >= 0.6(그날 사전 필터 통과 전 종목 기준).
1분봉을 30분봉(09:00~15:00 시작 13개, 15:30 단일가는 마지막 봉에 합침)으로 묶는다.

정의 — 실행 전에 고정
    F1 D 당일 돌파 시각 : D 의 30분봉 종가가 그날 일봉 추세선 값을 처음 넘은 봉. 오전(09:00~11:00 시작 봉) / 오후 / 없음.
    F2 D+1 확인 돌파    : D+1 의 30분봉(14:30 시작 봉까지) 종가가 D 고가를 처음 넘은 봉.
진입·평가 (+15% 먼저 익절 / -8% 먼저 손절, 같은 봉이면 손절, 갭이면 시가, 왕복 수수료 0.22%, D+10 종가에 만기)
    E0 지금 방식  : D+1 시가 매수(전부)
    E1 확인 매수  : F2 가 나온 봉의 종가에 매수, 이후 D+1 남은 30분봉 → D+2~D+10 일봉. F2 가 없으면 매수 안 함.
보는 것
    1) F1 시각별 E0 성과 — D 당일 30분봉 신호가 순위 기준이 되나
    2) F2 있음/없음별 E0 성과 — D+1 장중 확인이 좋은 후보를 가르나(실전 장중 재정렬의 근거)
    3) 같은 신호에서 E1 - E0 — 확인 후 사면 나아지나(놓친 상승·덜 맞은 손절 모두 포함)
한계: 표본 약 1년·200여 건, 슬리피지 없음, 분봉 캐시는 신호 종목만(같은 날 다른 후보 비교 불가).

사용
    poetry run python -m app.test.bt_private_30m
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, OUT as W2, outcome  # noqa: E402

MIN_DIR = os.path.join(CACHE, 'minute')
FROM = '2025-11-10'
FEE, TGT, STOP, H = 0.0022, 0.15, 0.08, 10


def bars30(code, d):
    p = os.path.join(MIN_DIR, code, d.replace('-', '') + '.pkl')
    if not os.path.exists(p):
        return None
    m = pd.read_pickle(p)
    t = m.index
    mins = (t.hour * 60 + t.minute) - 9 * 60
    k = np.clip(mins // 30, 0, 12)                     # 15:00~15:30(단일가 포함) = 12
    g = m.groupby(k)
    b = pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(), 'close': g.close.last(),
                      'volume': g.volume.sum()})
    return b if len(b) >= 10 else None


def path_outcome(entry, segs):
    """segs: [(open, high, low, close)] 진입 뒤 순서대로. 반환 (수익, 결과)."""
    up, dn = entry * (1 + TGT), entry * (1 - STOP)
    for o, h, l, c in segs:
        if o <= dn:
            return o / entry - 1 - FEE, 'F'
        if o >= up:
            return o / entry - 1 - FEE, 'W'
        if l <= dn:
            return -STOP - FEE, 'F'
        if h >= up:
            return TGT - FEE, 'W'
    return segs[-1][3] / entry - 1 - FEE, 'N'


def one(args):
    code, sig_dates = args
    df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
    dates = df['datetime'].astype(str).str[:10].tolist()
    idx = {d: k for k, d in enumerate(dates)}
    o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
    out = []
    for d, since_h1 in sig_dates:
        i = idx.get(d)
        if i is None or i + H >= len(c):
            continue
        b0, b1 = bars30(code, dates[i]), bars30(code, dates[i + 1])
        if b0 is None or b1 is None:
            continue
        i1 = i - int(since_h1)
        js = np.arange(i1 + 2, i)
        if len(js) < 2:
            continue
        slope = np.max((h[js] - h[i1]) / (js - i1))
        line = h[i1] + slope * (i - i1)
        f1 = next((k for k, r in b0.iterrows() if r.close > line), None)
        f2 = next((k for k, r in b1.iterrows() if k <= 11 and r.close > h[i]), None)
        e0, x0, _ = outcome(o, h, l, c, i, TGT)
        r = {'code': code, 'date': d, 'f1': f1, 'f2': f2, 'e0': e0, 'x0': x0,
             'last30_ret': b0.close.iloc[-1] / b0.open.iloc[-1] - 1, 'close_pos': (c[i] - l[i]) / (h[i] - l[i]) if h[i] > l[i] else np.nan}
        if f2 is not None:
            entry = b1.loc[f2, 'close']
            segs = [tuple(b1.loc[k, ['open', 'high', 'low', 'close']]) for k in b1.index if k > f2]
            segs += [(o[k], h[k], l[k], c[k]) for k in range(i + 2, i + H + 1)]
            r['e1'], r['x1'] = path_outcome(entry, segs)
            r['entry_gap'] = entry / o[i + 1] - 1
        out.append(r)
    return out


def shape_pct(dates_needed):
    def univ(fn):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', fn))
        cc, vv = df.close.astype(float), df.volume.astype(float)
        amt20 = (cc * vv).rolling(20).mean()
        d = df['datetime'].astype(str).str[:10]
        m = (cc >= 1000) & (amt20 >= 5e8) & d.isin(dates_needed) & df.proba.notna()
        return pd.DataFrame({'code': fn[:-4], 'date': d[m].values, 'proba': df.proba[m].values})
    u = pd.concat([univ(f) for f in sorted(os.listdir(os.path.join(CACHE, 'stocks')))])
    u['pct'] = u.groupby('date').proba.rank(pct=True)
    return u[['code', 'date', 'pct']]


def boot(g, col):
    rng = np.random.default_rng(7)
    by = {k: v[col].values for k, v in g.groupby('code')}
    ks = list(by)
    bs = [np.concatenate([by[k] for k in rng.choice(ks, len(ks))]).mean() for _ in range(1000)]
    return np.percentile(bs, 5) * 100, np.percentile(bs, 95) * 100


def report(r):
    def line(lab, g, col='e0', xcol='x0'):
        if not len(g):
            return f"  {lab:<26} n=0"
        return (f"  {lab:<26} n={len(g):>3}  매매당 {g[col].mean() * 100:+6.2f}%  익절 {(g[xcol] == 'W').mean() * 100:3.0f}%  "
                f"손절 {(g[xcol] == 'F').mean() * 100:3.0f}%")
    for scope, s in (('고급(shape 백분위 >= 0.6)', r[r.pct >= 0.6]), ('2파 신호 전체', r)):
        print(f"\n━━ {scope}: {len(s)}건 ({s.date.min()}~{s.date.max()}) · 같은 날 2건 이상 {(s.groupby('date').size() >= 2).sum()}일")
        print("[1] D 당일 30분봉이 추세선을 처음 넘은 시각별 — 지금 방식(D+1 시가) 성과")
        print(line('오전(09:00~11:00 봉)', s[s.f1.notna() & (s.f1 <= 4)]))
        print(line('오후(11:30~15:00 봉)', s[s.f1.notna() & (s.f1 > 4)]))
        print(line('30분봉 종가로는 못 넘음', s[s.f1.isna()]))
        print("[2] D+1 장중 30분봉이 D 고가를 넘었나 — 지금 방식 성과")
        y, n = s[s.f2.notna()], s[s.f2.isna()]
        print(line('넘음', y))
        print(line('안 넘음', n))
        if len(y) and len(n):
            rng = np.random.default_rng(7)
            by = {k: v for k, v in s.groupby('code')}
            ks = list(by)
            diffs = []
            for _ in range(1000):
                x = pd.concat([by[k] for k in rng.choice(ks, len(ks))])
                diffs.append(x[x.f2.notna()].e0.mean() - x[x.f2.isna()].e0.mean())
            print(f"    넘음 - 안 넘음: {(y.e0.mean() - n.e0.mean()) * 100:+.2f}%p [종목 90% {np.percentile(diffs, 5) * 100:+.2f}~{np.percentile(diffs, 95) * 100:+.2f}]")
        print("[3] 확인 후 매수(E1) vs 지금 방식(E0)")
        if len(y):
            y = y.copy(); y['d'] = y.e1 - y.e0
            lo, hi = boot(y, 'd')
            print(f"    넘은 {len(y)}건에서: E1 {y.e1.mean() * 100:+.2f}% vs E0 {y.e0.mean() * 100:+.2f}% → 차이 {y.d.mean() * 100:+.2f}%p [90% {lo:+.2f}~{hi:+.2f}]"
                  f" · 진입가는 D+1 시가보다 평균 {y.entry_gap.mean() * 100:+.1f}% 높음")
            tot0, tot1 = s.e0.sum(), y.e1.sum()
            print(f"    전략 합계(건당 같은 금액): E0 전부 매수 {len(s)}건 합 {tot0 * 100:+.1f}% · E1 확인분만 {len(y)}건 합 {tot1 * 100:+.1f}%")
        print("[참고] D 마지막 30분봉 수익(종가 직전 힘)")
        print(line('마지막 30분 상승', s[s.last30_ret > 0]))
        print(line('마지막 30분 하락·보합', s[s.last30_ret <= 0]))


if __name__ == '__main__':
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2) & (ev.date >= FROM)]
    have = set(os.listdir(MIN_DIR))
    jobs = [(code, list(zip(g.date, g.since_h1))) for code, g in ev.groupby('code') if code in have]
    with Pool(8) as p:
        rows = [x for part in p.map(one, jobs) for x in part]
    r = pd.DataFrame(rows)
    r = r.merge(shape_pct(set(r.date)), on=['code', 'date'], how='left')
    print(f"2파 신호 {len(ev)}건 중 분봉 있는 것 {len(r)}건")
    report(r)
