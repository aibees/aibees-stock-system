"""
bt_wave2_trend_regime.py — 추세 타기 매도(bt_wave2_trend_ride 결과)의 경로 착시 제거 + 시장 국면 의존성 점검.

① 1순위 전 신호 개별 평가(건너뛰기 없음) ② 순차 누적에서 상위 3건 뺀 값 ③ 시장 폭(전 종목 중 종가>EMA60 비율, 신호일 기준)별 수익
④ 국면 혼합: 폭이 앞 구간(2022~24) 중앙값 이상이면 추세 타기, 아니면 실전 규칙. 문턱은 앞 구간에서만 구하고 뒤 구간(2025~26)으로 확인.

사용
    poetry run python -m app.test.bt_wave2_trend_regime
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trend_ride import label_of
from app.test.bt_wave2_trendline import CACHE, OUT as W2

CANDS = ['live8', 'ew_ema_C', 'ew_atr_C', 'tline_C', 'sw4_C', 'ema20_C', 'ema20_I', 'macd', 't6', 'obv_ema']


def breadth():
    p = os.path.join(W2, 'breadth.pkl')
    if os.path.exists(p):
        return pd.read_pickle(p)
    up, tot = {}, {}
    d = os.path.join(CACHE, 'stocks')
    for f in os.listdir(d):
        x = pd.read_pickle(os.path.join(d, f))[['datetime', 'close', 'ema60']].dropna()
        x = x[x.ema60 > 0]
        ds = x.datetime.astype(str).str[:10].to_numpy()
        ok = (x.close.astype(float) > x.ema60.astype(float)).to_numpy()
        for k, v in zip(ds, ok):
            up[k] = up.get(k, 0) + int(v)
            tot[k] = tot.get(k, 0) + 1
    s = pd.Series({k: up[k] / tot[k] for k in tot if tot[k] >= 300}).sort_index()
    s.to_pickle(p)
    return s


def seq(res, rule, start):
    day1 = res[(res.date >= start) & res[rule].notna()].groupby('date', sort=True).head(1)
    free, rets = '', []
    for t in day1.itertuples():
        if t.date < free:
            continue
        rets.append(getattr(t, rule))
        free = getattr(t, rule + '_x')
    return np.array(rets)


def main():
    res = pd.read_pickle(os.path.join(W2, 'trend_ride.pkl'))
    res['br'] = res.date.map(breadth())
    done = res[res.date <= '2026-09-16']
    early = done.year.isin(['2022', '2023', '2024'])
    top1 = done.groupby('date', sort=True).head(1)
    e1 = top1.year.isin(['2022', '2023', '2024'])
    print(f"① 1순위 전 신호 {len(top1)}건 개별 평가 (앞 {e1.sum()} / 뒤 {(~e1).sum()})")
    print(f"{'매도':<28}{'매매당':>8}{'중앙':>8}{'앞':>8}{'뒤':>8}{'보유일':>7}{'1일당':>9}")
    for r in CANDS:
        x = top1[r]
        print(f"{label_of(r):<28}{x.mean() * 100:>+7.2f}%{x.median() * 100:>+7.2f}%{x[e1].mean() * 100:>+7.2f}%{x[~e1].mean() * 100:>+7.2f}%{top1[r + '_d'].mean():>7.1f}{x.mean() / top1[r + '_d'].mean() * 100:>+8.3f}%")
    for label, st in (('② 전체 2022-10~', '2022-10-01'), ('② 최근 1년', '2025-11-10')):
        print(f"\n{label} 순차 누적과 상위 3건 제외")
        print(f"{'매도':<28}{'매매수':>6}{'누적':>9}{'상위3 제외':>11}{'상위3 수익':>26}")
        for r in CANDS:
            a = seq(res, r, st)
            t3 = np.sort(a)[-3:]
            rest = np.sort(a)[:-3]
            print(f"{label_of(r):<28}{len(a):>6}{(np.prod(1 + a) - 1) * 100:>+8.0f}%{(np.prod(1 + rest) - 1) * 100:>+10.0f}%    {' '.join(f'{v * 100:+.0f}%' for v in t3[::-1])}")
    th = done.loc[early, 'br'].median()
    hi = done.br >= th
    print(f"\n③ 시장 폭 문턱 {th:.2f}(앞 구간 중앙값). 전 신호 {len(done)}건 — 폭 높음 {hi.sum()} / 낮음 {(~hi).sum()}")
    print(f"{'매도':<28}{'높음 앞':>9}{'높음 뒤':>9}{'낮음 앞':>9}{'낮음 뒤':>9}")
    for r in CANDS:
        x = done[r]
        print(f"{label_of(r):<28}{x[hi & early].mean() * 100:>+8.2f}%{x[hi & ~early].mean() * 100:>+8.2f}%{x[~hi & early].mean() * 100:>+8.2f}%{x[~hi & ~early].mean() * 100:>+8.2f}%")
    print(f"  건수: 높음 앞 {(hi & early).sum()} / 높음 뒤 {(hi & ~early).sum()} / 낮음 앞 {(~hi & early).sum()} / 낮음 뒤 {(~hi & ~early).sum()}")
    print('\n④ 국면 혼합(폭 높음=추세 타기, 낮음=실전 규칙) vs 실전 규칙 — 전 신호 개별, 종목 단위 90%')
    rng = np.random.default_rng(7)
    codes = done.code.to_numpy()
    groups = {k: np.flatnonzero(codes == k) for k in np.unique(codes)}
    keys = list(groups)
    live = done.live8.to_numpy(float)
    print(f"{'혼합 대상':<28}{'매매당':>8}{'앞':>8}{'뒤':>8}{'실전 대비':>10}{'90% 구간':>16}")
    for r in CANDS[1:]:
        mix = np.where(hi, done[r].to_numpy(float), live)
        diff = mix - live
        bs = [np.nanmean(np.concatenate([diff[groups[k]] for k in rng.choice(keys, len(keys))])) for _ in range(500)]
        print(f"{label_of(r):<28}{np.nanmean(mix) * 100:>+7.2f}%{np.nanmean(mix[early]) * 100:>+7.2f}%{np.nanmean(mix[~early]) * 100:>+7.2f}%{np.nanmean(diff) * 100:>+9.2f}%p{np.percentile(bs, 5) * 100:>+8.2f}~{np.percentile(bs, 95) * 100:<+6.2f}")


if __name__ == '__main__':
    main()
