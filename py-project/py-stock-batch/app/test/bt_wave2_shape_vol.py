"""
bt_wave2_shape_vol.py — 고급(2파) 신호 안에서: 형태 5(하락 뒤 최근 V반등)·변동성 작은 쪽 우선이 지금의 shape 하한보다 나은가.

배경(2026-11-14): 형태 군집(bt_shape_clusters)에서 형태 차이는 작았고(형태 5 만 두 해 +), 같은 형태 안에선
변동성이 작은 쪽이 대체로 나았다 — 지금 고급 단계의 shape 하한(변동성 큰 쪽을 남김)과 반대 방향.

정의 — 실행 전에 고정
    대상   : 2파 하락 추세선 돌파 + 거래량 2배↑ 신호(bt_wave2_trendline events, 2022-10~2026-09, 1,249건)
    모집단 : 그날 2파 백테스트 필터 통과 전 종목(종가 1,000·20일 평균 거래대금 5억·시총 1천억·보통주·관리 제외)
    변동성 : vol20 = 최근 20봉 일간 로그수익 표준편차 → 그날 모집단 안 백분위. 3등분(하 < 1/3, 상 >= 2/3)
    shape  : 배포 v1 확률(캐시 proba)의 그날 모집단 백분위 >= 0.6 = 지금 고급 하한
    형태   : bt_shape_clusters 와 같은 k-means(2025 게이트 모집단으로 다시 학습, 같은 시드) 를 신호의 20봉 경로에 배정
    성과   : D+1 시가 매수 +15%/-8%/10일(ret15), 실전 매도 규칙 근사(live8). 같은 날 모집단 평균(ret15) 대비 초과.
             2파 전체 대비 차이는 종목 단위 부트스트랩 90% 구간. 연도별.
한계: 1,249건(연 300건 안팎), 형태 5 는 10개 중 골라 온 것, 2026 은 shape 모델 학습 기간과 겹침.

사용
    poetry run python -m app.test.bt_wave2_shape_vol --sameday <같은 날 기준선 피클>
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, OUT as W2, MIN_CAP  # noqa: E402

L = 20
_G = {}


def _init(meta):
    _G.update(meta)


def univ(fn):
    code = fn[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return None
    df = pd.read_pickle(os.path.join(CACHE, 'stocks', fn))
    c = df.close.astype(float).to_numpy(); v = df.volume.astype(float).to_numpy()
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    lr = np.diff(np.log(np.where(c > 0, c, np.nan)), prepend=np.nan)
    vol20 = pd.Series(lr).rolling(L).std().to_numpy()
    d = df['datetime'].astype(str).str[:10].to_numpy()
    m = (c >= 1000) & (amt20 >= 5e8) & (c * _G['shares'][code] >= MIN_CAP) & (d >= '2022-10-01') & np.isfinite(vol20)
    return pd.DataFrame({'code': code, 'date': d[m], 'vol20': vol20[m], 'proba': df.proba.to_numpy()[m]})


def signal_paths(ev):
    P, keys = [], []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl'))
        d = df['datetime'].astype(str).str[:10].tolist(); idx = {x: k for k, x in enumerate(d)}
        c = df.close.astype(float).to_numpy()
        for x in g.date:
            i = idx.get(x)
            if i is None or i < L:
                continue
            P.append(np.log(c[i - L:i + 1] / c[i])); keys.append((code, x))
    return pd.DataFrame(keys, columns=['code', 'date']), np.array(P)


def kmeans_2025():
    """bt_shape_clusters 와 같은 군집(같은 데이터·시드) — 형태 번호도 같은 규칙(2025 20봉 수익 중앙값 순)."""
    from sklearn.cluster import KMeans
    from app.test.bt_shape_clusters import paths, K
    r = pd.read_pickle(os.path.join(CACHE, 'private', 'shape_gated_rows.pkl'))[['coin', 'd', 'grade', 'ret_close', 'ret_open', 'wake', 'chg']]
    k, P, _ = paths(r)
    fit = (k.d.str[:4] == '2025').to_numpy()
    Z = (P - P.mean(1, keepdims=True)) / (P.std(1, keepdims=True) + 1e-9)
    km = KMeans(n_clusters=K, random_state=7, n_init=10).fit(Z[fit])
    lab = km.predict(Z[fit])
    ret20 = pd.Series(-P[fit, 0]).groupby(lab).median().sort_values()
    remap = {c: n + 1 for n, c in enumerate(ret20.index)}
    return km, remap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sameday', required=True)
    args = ap.parse_args()
    from sqlalchemy import create_engine
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')
                       | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(x) for k, x in zip(ms.stock_code, ms.listed_shares) if x}, 'bad': bad}
    with Pool(8, initializer=_init, initargs=(meta,)) as p:
        u = pd.concat([x for x in p.map(univ, sorted(os.listdir(os.path.join(CACHE, 'stocks'))), chunksize=16) if x is not None])
    u['vol_pct'] = u.groupby('date').vol20.rank(pct=True)
    u['shape_pct'] = u.groupby('date').proba.rank(pct=True)

    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)].copy()
    ex = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8']]
    ev = ev.merge(ex, on=['code', 'date'], how='left').merge(u[['code', 'date', 'vol20', 'vol_pct', 'shape_pct']], on=['code', 'date'], how='inner')
    sd = pd.read_pickle(args.sameday).set_index('date')['mean']
    ev = ev[ev.date.isin(sd.index)].copy()
    ev['ex'] = ev.ret15 - sd.loc[ev.date].values

    km, remap = kmeans_2025()
    k, P = signal_paths(ev)
    Z = (P - P.mean(1, keepdims=True)) / (P.std(1, keepdims=True) + 1e-9)
    k['shape_cl'] = pd.Series(km.predict(Z)).map(remap).values
    ev = ev.merge(k, on=['code', 'date'], how='left')
    ev['vq'] = np.where(ev.vol_pct < 1 / 3, '하', np.where(ev.vol_pct >= 2 / 3, '상', '중'))
    print(f"2파 신호 {len(ev)}건 ({ev.date.min()}~{ev.date.max()}) · 매매당 {ev.ret15.mean() * 100:+.2f}% · 실전 {ev.live8.mean() * 100:+.2f}%"
          f" · 같은 날 대비 {ev.ex.mean() * 100:+.2f}%p")
    print(f"  신호의 변동성 백분위 중앙 {ev.vol_pct.median():.2f} (2파 신호는 원래 변동성 높은 쪽) · 3등분 비중 하 {(ev.vq == '하').mean() * 100:.0f}% 중 {(ev.vq == '중').mean() * 100:.0f}% 상 {(ev.vq == '상').mean() * 100:.0f}%")

    rng = np.random.default_rng(7)
    by = {c: g for c, g in ev.groupby('code')}
    cs = list(by)
    samples = [pd.concat([by[c] for c in rng.choice(cs, len(cs))]) for _ in range(500)]

    def line(lab, mask_fn):
        m = mask_fn(ev)
        s = ev[m]
        dif = [x[mask_fn(x)].ret15.mean() - x.ret15.mean() for x in samples]
        dif8 = [x[mask_fn(x)].live8.mean() - x.live8.mean() for x in samples]
        yr = '/'.join(f"{s[s.year == y].ret15.mean() * 100:+.1f}" if (s.year == y).any() else '-' for y in ('2023', '2024', '2025', '2026'))
        print(f"  {lab:<30} n={m.sum():>5} ({m.mean() * 100:3.0f}%) 매매당 {s.ret15.mean() * 100:+.2f}% 실전 {s.live8.mean() * 100:+.2f}% │ 2파 전체 대비 "
              f"{(s.ret15.mean() - ev.ret15.mean()) * 100:+.2f}%p [{np.nanpercentile(dif, 5) * 100:+.2f}~{np.nanpercentile(dif, 95) * 100:+.2f}]"
              f" 실전 {(s.live8.mean() - ev.live8.mean()) * 100:+.2f}%p [{np.nanpercentile(dif8, 5) * 100:+.2f}~{np.nanpercentile(dif8, 95) * 100:+.2f}] │ {yr}")

    print("\n[남기는 조건별 — 매매당 / 2파 전체 대비 / 연도별 매매당(23/24/25/26)]")
    line('지금 고급: shape 백분위 >= 0.6', lambda x: x.shape_pct >= 0.6)
    line('변동성 하위 1/3 만', lambda x: x.vol_pct < 1 / 3)
    line('변동성 상위 1/3 제외', lambda x: x.vol_pct < 2 / 3)
    line('형태 5 만', lambda x: x.shape_cl == 5)
    line('shape >= 0.6 & 변동성 상위 1/3 제외', lambda x: (x.shape_pct >= 0.6) & (x.vol_pct < 2 / 3))
    print("  ─ 사후 가설(위 결과를 본 뒤 추가 — 확정 근거 아님): shape 대신 단순 변동성 백분위")
    line('변동성 백분위 >= 0.5', lambda x: x.vol_pct >= 0.5)
    line('변동성 백분위 >= 2/3', lambda x: x.vol_pct >= 2 / 3)
    line('shape >= 0.6 & 변동성 >= 2/3', lambda x: (x.shape_pct >= 0.6) & (x.vol_pct >= 2 / 3))

    print("\n[shape 하한 × 변동성 3등분 — 매매당 / 실전 / 건수]")
    for sh, sm in (('shape >= 0.6', ev.shape_pct >= 0.6), ('shape < 0.6', ev.shape_pct < 0.6)):
        print(f"  {sh:<13} " + ' · '.join(f"변동성 {q} {ev[sm & (ev.vq == q)].ret15.mean() * 100:+.2f}%/{ev[sm & (ev.vq == q)].live8.mean() * 100:+.2f}% ({(sm & (ev.vq == q)).sum()})"
                                              for q in ('하', '중', '상')))
    print("\n[형태별 — 2파 신호 안]")
    for c in range(1, 11):
        s = ev[ev.shape_cl == c]
        if len(s):
            print(f"  형태 {c:>2} n={len(s):>4} 매매당 {s.ret15.mean() * 100:+.2f}% 실전 {s.live8.mean() * 100:+.2f}% 같은날대비 {s.ex.mean() * 100:+.2f}%p")

    # 형태별 차이가 기간을 나눠도 유지되나 / 형태별로 변동성 효과가 달라지나
    ev['half'] = np.where(ev.date < '2025-01-01', '앞(~2024)', '뒤(2025~)')
    ev['vh'] = ev.vol_pct >= 0.5
    print("\n[형태별 — 기간 앞/뒤 매매당 · 변동성 백분위 0.5 이상/미만 매매당 (건수)]")
    rows = []
    for c in range(1, 11):
        s = ev[ev.shape_cl == c]
        a1, a2 = s[s.half == '앞(~2024)'], s[s.half == '뒤(2025~)']
        h, l_ = s[s.vh], s[~s.vh]
        rows.append((c, len(s), a1.ret15.mean(), len(a1), a2.ret15.mean(), len(a2), h.ret15.mean(), len(h), l_.ret15.mean(), len(l_)))
        print(f"  형태 {c:>2} n={len(s):>4} │ 앞 {a1.ret15.mean() * 100:+6.2f}% ({len(a1):>3}) 뒤 {a2.ret15.mean() * 100:+6.2f}% ({len(a2):>3}) │"
              f" 변동성↑ {h.ret15.mean() * 100:+6.2f}% ({len(h):>3}) 변동성↓ {l_.ret15.mean() * 100:+6.2f}% ({len(l_):>3}) 차이 {(h.ret15.mean() - l_.ret15.mean()) * 100:+6.2f}%p")
    t = pd.DataFrame(rows, columns=['c', 'n', 'f', 'nf', 'b', 'nb', 'h', 'nh', 'l', 'nl'])
    ok = t[(t.nf >= 20) & (t.nb >= 20)]
    print(f"  앞/뒤 형태 순위 상관(각 20건 이상 {len(ok)}개 형태): {ok.f.corr(ok.b, method='spearman'):+.2f}")
    print(f"  변동성↑ 가 나은 형태 {(t.h > t.l).sum()}/10")
    # 형태 무작위 섞기: 형태 간 차이가 우연으로도 이만큼 나오나(형태 평균의 표준편차)
    obs = ev.groupby('shape_cl').ret15.mean().std()
    rng2 = np.random.default_rng(11)
    null = [ev.assign(sc=rng2.permutation(ev.shape_cl.values)).groupby('sc').ret15.mean().std() for _ in range(1000)]
    print(f"  형태 평균 간 흩어짐 {obs * 100:.2f}%p vs 형태를 무작위로 섞었을 때 95% {np.percentile(null, 95) * 100:.2f}%p (p≈{(np.array(null) >= obs).mean():.2f})")


if __name__ == '__main__':
    main()
