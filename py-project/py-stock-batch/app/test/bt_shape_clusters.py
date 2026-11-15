"""
bt_shape_clusters.py — 가격 경로 '형태'를 명시적으로 군집으로 나눠 형태별 성과 보기.

배경(2026-11-14 사용자): shape 모델은 14개 요약 숫자를 한 점수로 섞어 매겨, 결국 변동성 큰 종목으로 쏠렸다.
형태를 따로 나눠 '어떤 형태가 실제로 이익이 나는지'를 형태 단위로 본다.

정의 — 실행 전에 고정
    모집단  : bt_shape_gated 와 같음(유동성 + 250일 고점 대비 -40% 초과 + 120일선 위, 상한가 마감일 제외, 2025-01~2026-10)
    형태    : 신호일 D 포함 최근 21개 종가(20봉 경로)의 log(종가 / D 종가), 경로마다 평균 0·표준편차 1 로 정규화
              → 크기(변동폭)는 빼고 모양만 남긴다. 크기는 '20봉 일간수익 표준편차'로 따로 기록.
    군집    : k-means K=10, 2025 행으로만 학습(정답·수익은 보지 않음) → 전 기간 배정
    성과    : 정답 등급(목표 = D 고가 × 1.15, 손절 = D+1 시가 -8%, 10일)과 매매 수익(매수가 기준 +15%/-8%/10일, 수수료 0.22%)
              ① 신호일 종가 매수  ② 다음 날 시가 매수. 2025 성과로 형태를 고르고 2026 에서 같은 방향인지 본다.
              같은 날 모집단 평균 대비 초과수익, 종목 단위 부트스트랩 90% 구간.
한계: 20봉 일봉 경로만(분봉·장기 구조 없음), K 는 임의 고정, 같은 종목 연속일은 정답 구간이 겹친다.

사용
    poetry run python -m app.test.bt_shape_clusters
"""
import os
import sys

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from app.test.eval_shape_proba import DB_URL  # noqa: E402
from app.test.bt_wave2_trendline import CACHE  # noqa: E402

OUT = os.path.join(CACHE, 'private')
L, K = 20, 10


def paths(r):
    eng = create_engine(DB_URL)
    b = pd.read_sql(text("SELECT stock_code, trade_date, close_price c, volume v FROM stock_ohlcv_daily "
                         "WHERE trade_date >= '2024-11-01'"), eng)
    b['d'] = (pd.to_datetime(b.trade_date) + pd.Timedelta(hours=9)).dt.strftime('%Y-%m-%d')
    b = b.sort_values(['stock_code', 'd'])
    want = r.groupby('coin').d.apply(list).to_dict()
    P, V, keys = [], [], []
    for code, g in b.groupby('stock_code', sort=False):
        ds = want.get(code)
        if not ds:
            continue
        d = g.d.to_numpy(); c = g.c.to_numpy(float); v = g.v.to_numpy(float)
        idx = {x: k for k, x in enumerate(d)}
        for x in ds:
            i = idx.get(x)
            if i is None or i < L + 20:
                continue
            P.append(np.log(c[i - L:i + 1] / c[i]))
            V.append(v[i - L:i + 1] / (v[i - L - 20:i - L].mean() + 1e-9))
            keys.append((code, x))
    k = pd.DataFrame(keys, columns=['coin', 'd'])
    return k, np.array(P), np.array(V)


def main():
    from sklearn.cluster import KMeans
    r = pd.read_pickle(os.path.join(OUT, 'shape_gated_rows.pkl'))[['coin', 'd', 'grade', 'ret_close', 'ret_open', 'wake', 'chg']]
    k, P, V = paths(r)
    r = k.merge(r, on=['coin', 'd'], how='left').reset_index(drop=True)
    mu, sd = P.mean(axis=1, keepdims=True), P.std(axis=1, keepdims=True) + 1e-9
    Z = (P - mu) / sd
    r['vol20'] = np.diff(P, axis=1).std(axis=1)
    r['ret20'] = -P[:, 0]                       # D 종가 / 20봉 전 종가 - 1 (로그)
    r['y'] = r.d.str[:4]
    fit = (r.y == '2025').to_numpy()
    km = KMeans(n_clusters=K, random_state=7, n_init=10).fit(Z[fit])
    r['cl'] = km.predict(Z)
    # 군집 번호를 20봉 수익 중앙값 순으로 다시 매긴다(읽기 쉽게)
    order = r[fit].groupby('cl').ret20.median().sort_values().index.tolist()
    remap = {c: n + 1 for n, c in enumerate(order)}
    r['cl'] = r.cl.map(remap)
    r.to_pickle(os.path.join(OUT, 'shape_clusters.pkl'))
    np.save(os.path.join(OUT, 'shape_cluster_paths.npy'), P)

    base = r.groupby('d')[['ret_close', 'ret_open']].transform('mean')
    r['ex_close'] = r.ret_close - base.ret_close
    r['ex_open'] = r.ret_open - base.ret_open
    print(f"행 {len(r):,} (2025 {fit.sum():,} · 2026 {(~fit).sum():,}) · 형태 {K}개 · 경로 {L}봉")
    for y in ('2025', '2026'):
        x = r[r.y == y]
        print(f"  {y} 기준: 다음날 +15% {(x.grade >= 2).mean() * 100:.2f}% · 10일 +15% 먼저 {(x.grade >= 1).mean() * 100:.1f}% · "
              f"종가매수 {x.ret_close.mean() * 100:+.2f}% · 시가매수 {x.ret_open.mean() * 100:+.2f}%")
    rng = np.random.default_rng(7)

    def ci(x, col):
        by = {c: v[col].values for c, v in x.groupby('coin')}
        cs = list(by)
        bs = [np.concatenate([by[c] for c in rng.choice(cs, len(cs))]).mean() for _ in range(500)]
        return np.percentile(bs, 5) * 100, np.percentile(bs, 95) * 100

    print(f"\n{'형태':<4}{'비중':>6}{'20봉수익':>9}{'변동성':>7}{'깨어남':>7} │ {'2025 다음날+15%':>14}{'종가 초과':>10}{'시가 초과':>10} │ {'2026 다음날+15%':>14}{'종가 초과':>10}{'(90% 구간)':>18}{'시가 초과':>10}{'(90% 구간)':>18}")
    for c in range(1, K + 1):
        a, b_ = r[(r.cl == c) & (r.y == '2025')], r[(r.cl == c) & (r.y == '2026')]
        lo, hi = ci(b_, 'ex_close'); lo2, hi2 = ci(b_, 'ex_open')
        print(f"{c:<4}{(r.cl == c).mean() * 100:>5.1f}%{np.expm1(r[r.cl == c].ret20.median()) * 100:>+8.1f}%{r[r.cl == c].vol20.median() * 100:>6.1f}%"
              f"{r[r.cl == c].wake.mean() * 100:>6.1f}% │ {(a.grade >= 2).mean() * 100:>13.2f}%{a.ex_close.mean() * 100:>+9.2f}%p{a.ex_open.mean() * 100:>+9.2f}%p │"
              f" {(b_.grade >= 2).mean() * 100:>13.2f}%{b_.ex_close.mean() * 100:>+9.2f}%p [{lo:+.2f}~{hi:+.2f}]{b_.ex_open.mean() * 100:>+9.2f}%p [{lo2:+.2f}~{hi2:+.2f}]")

    # 형태 안에서 크기(변동성) 3등분 — 같은 모양이라도 크게 움직이는 쪽이 다른가
    print("\n[형태 × 변동성 3등분 — 2026 종가매수 초과(%p)]")
    r['vq'] = r.groupby('cl').vol20.transform(lambda s: pd.qcut(s.rank(method='first'), 3, labels=['소', '중', '대']))
    t = r[r.y == '2026'].pivot_table(index='cl', columns='vq', values='ex_close', aggfunc='mean', observed=True) * 100
    t25 = r[r.y == '2025'].pivot_table(index='cl', columns='vq', values='ex_close', aggfunc='mean', observed=True) * 100
    print(pd.concat({'2025': t25.round(2), '2026': t.round(2)}, axis=1).to_string())

    # 그림: 형태별 경로(중앙값, % 기준) + 2025/2026 성과
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'AppleGothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(2, 5, figsize=(17, 7), sharex=True)
    xs = np.arange(-L, 1)
    for c, ax in zip(range(1, K + 1), axes.ravel()):
        m = (r.cl == c).to_numpy()
        pp = np.expm1(P[m]) * 100
        ax.fill_between(xs, np.percentile(pp, 25, axis=0), np.percentile(pp, 75, axis=0), color='#9db4d6', alpha=.5, lw=0)
        ax.plot(xs, np.median(pp, axis=0), color='#1f3b6e', lw=2)
        ax.axhline(0, color='#999', lw=.6)
        a, b_ = r[m & fit], r[m & ~fit]
        ax.set_title(f"형태 {c} ({m.mean() * 100:.0f}%)\n'25 종가 {a.ex_close.mean() * 100:+.2f}%p · '26 {b_.ex_close.mean() * 100:+.2f}%p",
                     fontsize=10)
        ax.tick_params(labelsize=8)
    fig.suptitle('최근 20봉 종가 경로(신호일 종가 = 0%) — 중앙값과 25~75% 범위 / 같은 날 평균 대비 종가매수 초과수익', fontsize=12)
    fig.tight_layout()
    png = os.path.join(OUT, 'shape_clusters.png')
    fig.savefig(png, dpi=110)
    print(f"\n그림: {png}")


if __name__ == '__main__':
    main()
