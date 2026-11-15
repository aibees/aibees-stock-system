"""
bt_private_intraday.py — 실전(PRIVATE) 후보 연구 ③: 일봉 2파 후보 안에서 분봉(30분·15분) 상승 구조가 뚜렷할수록 1위로.

배경(2026-11-14 사용자 제안): 일봉으로 걸러진 후보 중 1위를 고르기 어렵다. 신호일 D 장 마감까지의 분봉에서
2파 돌파 같은 상승 구조가 뚜렷한 종목을 위로 올리면 어떨까. (D+1 장중 확인 매수는 bt_private_30m 에서 기각 —
여기는 D 마감까지의 정보만 쓰므로 D+1 시가에 그대로 산다.)

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다)
    데이터   : 신호일 포함 직전 20거래일 1분봉(collect_wave2_minutes --warmup 20 --signal-only) → 30분봉(13개/일)·15분봉(26개/일).
               15:30 단일가는 그날 마지막 봉에 합친다. 20일 중 15일 미만이면 제외.
    분봉 2파 : 일봉 2파와 같은 규칙 — ATR14 × 4 스윙(최소 폭 30분봉 1.5%, 15분봉 1.0%), 2파 최저 > L0,
               되돌림 0.382~0.786, H1 뒤 5봉 이상, H1 에서 내려오는 하락 추세선을 종가가 처음 넘음, 거래량 >= 직전 20봉 평균 × 2.
    점수     : S1 D 당일 봉 중 분봉 2파 돌파가 있었나 / S2 그 돌파의 최대 거래량 배수 /
               S3 D 종가 ÷ 최근 5일 분봉 VWAP - 1
    순위     : 분봉 순위 = S1 있음 먼저 → S2 큰 순 (같으면 일봉 거래량 배수) / 지금 순위 = 일봉 거래량 배수 큰 순
평가: D+1 시가 매수, +15%/-8%/10일(ret15), 실전 매도 규칙(live8, bt_wave2_exits). 고급 = shape 백분위 >= 0.6.
한계: 약 1년·200여 건, 같은 날 후보 2개 이상은 40여 일뿐, 분봉 거래량은 시간대 계절성(장 초반 큼)을 보정하지 않음.

사용
    poetry run python -m app.test.bt_private_intraday
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, OUT as W2  # noqa: E402
from app.test.bt_private_30m import MIN_DIR, FROM, shape_pct  # noqa: E402
from stock_shared.chart_analysis.indicators import atr as atr_fn  # noqa: E402

DAYS, MIN_DAYS = 20, 15
FREQ = {30: 1.5, 15: 1.0}          # 봉 길이(분) → 최소 스윙 폭(%)
MULT, VOL_MIN = 4.0, 2.0


def day_bars(code, d, freq):
    p = os.path.join(MIN_DIR, code, d.replace('-', '') + '.pkl')
    if not os.path.exists(p):
        return None
    m = pd.read_pickle(p)
    t = m.index
    last = 390 // freq - 1
    k = np.clip(((t.hour * 60 + t.minute) - 540) // freq, 0, last)
    g = m.groupby(k)
    b = pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(), 'close': g.close.last(),
                      'volume': g.volume.sum(), 'amt': (m.close * m.volume).groupby(k).sum()})
    b['day'] = d
    return b


def scan(high, low, close, vol, a, min_pct):
    """일봉 wave2_breakout.scan 의 tl 규칙을 분봉에 그대로. [(i, vr)]"""
    v20 = pd.Series(vol).rolling(20).mean().shift(1).to_numpy()
    n = len(close)
    piv, direction, ext_i, hi_i, lo_i = [], 0, 0, 0, 0
    ctx, out = None, []
    thr = lambda i, ref: max(a[i] * MULT, ref * min_pct / 100)  # noqa: E731
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
            ctx = {'p0': piv[-2][2], 'i1': piv[-1][1], 'p1': piv[-1][2], 'tl': False}
        if ctx is None:
            continue
        p0, i1, p1 = ctx['p0'], ctx['i1'], ctx['p1']
        lo_since = low[i1 + 1:i + 1].min() if i > i1 else p1
        if lo_since <= p0 or close[i] > p1:
            ctx = None
            continue
        retr = (p1 - lo_since) / (p1 - p0) if p1 > p0 else 0
        if not (0.382 <= retr <= 0.786 and i - i1 >= 5) or ctx['tl']:
            continue
        js = np.arange(i1 + 2, i)
        if len(js) < 2:
            continue
        slope = np.max((high[js] - p1) / (js - i1))
        if slope >= 0:
            continue
        if close[i] > p1 + slope * (i - i1) and close[i - 1] <= p1 + slope * (i - 1 - i1):
            out.append((i, vol[i] / v20[i] if v20[i] and v20[i] > 0 else np.nan))
            ctx['tl'] = True
    return out


def one(args):
    code, sigs = args
    df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
    dates = df['datetime'].astype(str).str[:10].tolist()
    idx = {d: k for k, d in enumerate(dates)}
    rows = []
    for d in sigs:
        i = idx.get(d)
        if i is None or i < DAYS:
            continue
        r = {'code': code, 'date': d}
        for freq, mp in FREQ.items():
            parts = [b for b in (day_bars(code, x, freq) for x in dates[i - DAYS + 1:i + 1]) if b is not None]
            if len(parts) < MIN_DAYS or parts[-1].day.iloc[0] != d:
                r = None
                break
            b = pd.concat(parts, ignore_index=True)
            h, l, c, v = (b[k].to_numpy(float) for k in ('high', 'low', 'close', 'volume'))
            a = atr_fn(b.high.astype(float), b.low.astype(float), b.close.astype(float)).bfill().fillna(0).to_numpy()
            on_d = set(np.flatnonzero(b.day.to_numpy() == d))
            brk = [vr for k, vr in scan(h, l, c, v, a, mp) if k in on_d and vr == vr and vr >= VOL_MIN]
            last5 = b[b.day.isin(sorted(b.day.unique())[-5:])]
            vwap = last5.amt.sum() / last5.volume.sum() if last5.volume.sum() > 0 else np.nan
            r[f's1_{freq}'] = bool(brk)
            r[f's2_{freq}'] = max(brk) if brk else 0.0
            r[f's3_{freq}'] = c[-1] / vwap - 1 if vwap == vwap else np.nan
        if r is not None:
            rows.append(r)
    return rows


def boot_diff(s, _unused, col):
    """s['_m'] 참/거짓 두 군의 평균 차이 — 종목 단위 부트스트랩 90% 구간(%p)."""
    rng = np.random.default_rng(7)
    by = {k: v for k, v in s.groupby('code')}
    ks = list(by)
    out = []
    for _ in range(1000):
        x = pd.concat([by[k] for k in rng.choice(ks, len(ks))])
        mx = x['_m']
        out.append(x[mx][col].mean() - x[~mx][col].mean())
    return np.nanpercentile(out, 5) * 100, np.nanpercentile(out, 95) * 100


def report(r):
    for scope, s0 in (('고급(shape 백분위 >= 0.6)', r[r.pct >= 0.6]), ('2파 신호 전체', r)):
        print(f"\n━━ {scope}: {len(s0)}건 ({s0.date.min()}~{s0.date.max()}) · 같은 날 2건↑ {(s0.groupby('date').size() >= 2).sum()}일"
              f" · 전체 매매당 {s0.ret15.mean() * 100:+.2f}% 실전 {s0.live8.mean() * 100:+.2f}%")
        for freq in FREQ:
            s = s0.copy()
            print(f" [{freq}분봉]")
            s['_m'] = s[f's1_{freq}']
            y, n = s[s._m], s[~s._m]
            lo, hi = boot_diff(s, None, 'ret15')
            lo8, hi8 = boot_diff(s.dropna(subset=['live8']), None, 'live8')
            print(f"   S1 분봉 2파 돌파 있음 n={len(y):>3} 매매당 {y.ret15.mean() * 100:+.2f}% 실전 {y.live8.mean() * 100:+.2f}% │ 없음 n={len(n):>3} "
                  f"{n.ret15.mean() * 100:+.2f}% 실전 {n.live8.mean() * 100:+.2f}% │ 차이 {(y.ret15.mean() - n.ret15.mean()) * 100:+.2f}%p [{lo:+.2f}~{hi:+.2f}]"
                  f" 실전 {(y.live8.mean() - n.live8.mean()) * 100:+.2f}%p [{lo8:+.2f}~{hi8:+.2f}]")
            if len(y) >= 6:
                med = y[f's2_{freq}'].median()
                a, b = y[y[f's2_{freq}'] >= med], y[y[f's2_{freq}'] < med]
                print(f"   S2 돌파 거래량 배수(있음 안에서, 중앙 {med:.1f}배) 큰 쪽 {a.ret15.mean() * 100:+.2f}% 실전 {a.live8.mean() * 100:+.2f}% │ "
                      f"작은 쪽 {b.ret15.mean() * 100:+.2f}% 실전 {b.live8.mean() * 100:+.2f}%")
            q = pd.qcut(s[f's3_{freq}'].rank(method='first'), 3, labels=['하', '중', '상'])
            print("   S3 종가/5일 VWAP 3등분 " + ' · '.join(
                f"{k}({s[q == k][f's3_{freq}'].median() * 100:+.1f}%) {s[q == k].ret15.mean() * 100:+.2f}%/실전 {s[q == k].live8.mean() * 100:+.2f}%"
                for k in ('하', '중', '상')))
            m = s.groupby('date').filter(lambda g: len(g) >= 2)
            if len(m):
                now = m.loc[m.groupby('date').vol_ratio.idxmax()]
                m = m.assign(_k=list(zip(m[f's1_{freq}'], m[f's2_{freq}'], m.vol_ratio)))
                new = m.loc[m.groupby('date')._k.apply(lambda z: z.idxmax())]
                same = (now.set_index('date').code == new.set_index('date').code).mean()
                print(f"   같은 날 2건↑ {m.date.nunique()}일: 지금 1위 {now.ret15.mean() * 100:+.2f}%/실전 {now.live8.mean() * 100:+.2f}% · "
                      f"분봉 순위 1위 {new.ret15.mean() * 100:+.2f}%/실전 {new.live8.mean() * 100:+.2f}% (1위가 같은 날 {same * 100:.0f}%)")


if __name__ == '__main__':
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2) & (ev.date >= FROM)]
    ex = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8']]
    have = set(os.listdir(MIN_DIR))
    jobs = [(code, list(g.date)) for code, g in ev.groupby('code') if code in have]
    with Pool(8) as p:
        rows = [x for part in p.map(one, jobs) for x in part]
    r = pd.DataFrame(rows).merge(ev[['code', 'date', 'vol_ratio', 'ret15', 'res15']], on=['code', 'date'])
    r = r.merge(ex, on=['code', 'date'], how='left').merge(shape_pct(set(r.date)), on=['code', 'date'], how='left')
    print(f"2파 신호 {len(ev)}건 중 분봉 {MIN_DAYS}일 이상 있는 것 {len(r)}건")
    r.to_pickle(os.path.join(CACHE, 'private', 'intraday_scores.pkl'))
    report(r)
