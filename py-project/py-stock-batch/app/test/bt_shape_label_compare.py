"""
bt_shape_label_compare.py — shape_proba 정답(라벨) 재설계 비교: 현행 vs 신호일 고가 기준·순서 반영·다음 날 가중.

배경(2026-11-14 사용자): 현행 정답 net_edge_fwd(종가 기준 5봉 고가-저가 차 >= 15%p, 순서 무관, 학습 테이블 자기 행으로 계산)는
실제 매매와 다르고, 거래량이 식은 종목이 정답 없이 빠져 낙관 편향이 있다. 기준가를 신호일 고가로, 가격 순서를 보고,
'다음 날 +15%' 에 가장 큰 무게를 주는 정답으로 바꾸면 나아지나.

정의 — 실행 전에 고정
    학습 행  : trade_shape_train_daily 의 피처 14개(결측 없는 행만 — 현행 build_dataset 과 같음)
    새 정답  : 전 종목 일봉(stock_ohlcv_daily)으로 계산. 목표가 U = 신호일 고가 × 1.15, 손절 S = D+1 시가 × 0.92
               등급 3 = D+1 종가 >= U / 2 = D+1 고가 >= U / 1 = D+1~D+10 에 U 가 S 보다 먼저(같은 날이면 손절, 시가 갭은 시가 기준) / 0 = 그 외
    모델     : 모두 shape_train.MODEL_PARAMS 의 HistGBM
        OLD : 현행 그대로 — 테이블 정답(net_edge_fwd >= 15) 있는 행만, 이진
        T1  : 새 정답 등급 >= 1 이진, 무게 없음(무게 효과 분리용)
        A   : T1 + 학습 무게 등급3 3배 · 등급2 2배 · 나머지 1배
        B   : 등급 0~3 다중분류, 점수 = 기대 등급(Σ 등급 × 확률)
    전진 검증 : 2026-01 ~ 2026-10 각 달 m — m 시작 20일(달력) 전까지 행으로 학습 → m 채점(표본 외)
평가
    ① 전체 모집단(학습 테이블 행): AUC(등급>=1, 등급>=2), 날짜별 점수 상위 10개의 등급1·2·3 비율과
       실제 매매 수익(ret15 = D+1 시가 매수, +15%/-8%/10일, 매수가 기준)
    ② 2파 신호(bt_wave2_trendline events) 중 학습 테이블에 같은 날 행이 있는 것: 점수의 그날 모집단 백분위로
       3등분 성과, 백분위 0.6 미만 제외 효과(고급 하한과 같은 방식) — ret15·live8
한계: 학습셋은 2025-09~ 약 14개월, 학습 테이블 모집단(사전 필터 통과)만, 피처는 배치(KIS 통합시세) 값·정답은 KRX 일봉.

사용
    poetry run python -m app.test.bt_shape_label_compare
"""
import os
import sys

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from app.test.eval_shape_proba import DB_URL  # noqa: E402
from app.test.bt_wave2_trendline import OUT as W2, outcome  # noqa: E402
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS as F  # noqa: E402
from stock_shared.ml.shape_train import MODEL_PARAMS  # noqa: E402

H = 10
MONTHS = [f'2026-{m:02d}' for m in range(1, 11)]
WEIGHT = {3: 3.0, 2: 2.0, 1: 1.0, 0: 1.0}


def load():
    eng = create_engine(DB_URL)
    cols = ', '.join(F)
    tr = pd.read_sql(text(f"SELECT coin, DATE_FORMAT(DATE_ADD(datetime, INTERVAL 9 HOUR), '%Y-%m-%d') d, net_edge_fwd, {cols} "
                          "FROM trade_shape_train_daily"), eng)
    bars = pd.read_sql(text("SELECT stock_code, trade_date, open_price o, high_price h, low_price l, close_price c "
                            "FROM stock_ohlcv_daily WHERE trade_date >= '2025-08-01'"), eng)
    bars['d'] = (pd.to_datetime(bars.trade_date) + pd.Timedelta(hours=9)).dt.strftime('%Y-%m-%d')
    bars = bars.sort_values(['stock_code', 'd'])
    want = tr.groupby('coin').d.apply(set).to_dict()
    out = []
    for code, g in bars.groupby('stock_code', sort=False):
        ds = want.get(code)
        if not ds:
            continue
        d = g.d.to_numpy()
        o, h, l, c = (g[k].to_numpy(float) for k in ('o', 'h', 'l', 'c'))
        for i in np.flatnonzero(np.isin(d, list(ds))):
            if i + H >= len(d) or o[i + 1] <= 0:
                continue
            U, S = h[i] * 1.15, o[i + 1] * 0.92
            grade = 0
            for k in range(i + 1, i + H + 1):
                if o[k] >= U:
                    grade = 1; break
                if l[k] <= S or o[k] <= S:
                    break
                if h[k] >= U:
                    grade = 1; break
            if h[i + 1] >= U:
                grade = 2
            if c[i + 1] >= U:
                grade = 3
            r15, _, _ = outcome(o, h, l, c, i, 0.15)
            out.append((code, d[i], grade, r15))
    lab = pd.DataFrame(out, columns=['coin', 'd', 'grade', 'ret15'])
    r = tr.merge(lab, on=['coin', 'd'], how='inner')
    r = r[np.isfinite(r[F].astype(float)).all(axis=1)].reset_index(drop=True)
    return r


def walk_forward(r):
    from sklearn.ensemble import HistGradientBoostingClassifier as HGB
    for k in ('OLD', 'T1', 'A', 'B'):
        r[k] = np.nan
    X = r[F].to_numpy(float)
    for m in MONTHS:
        cut = (pd.Timestamp(m + '-01') - pd.Timedelta(days=20)).strftime('%Y-%m-%d')
        tr_m = (r.d < cut).to_numpy()
        te_m = (r.d.str[:7] == m).to_numpy()
        if te_m.sum() == 0:
            continue
        old_m = tr_m & r.net_edge_fwd.notna().to_numpy()
        y_old = (r.net_edge_fwd.to_numpy() >= 15).astype(int)
        y1 = (r.grade.to_numpy() >= 1).astype(int)
        w = r.grade.map(WEIGHT).to_numpy()
        r.loc[te_m, 'OLD'] = HGB(**MODEL_PARAMS).fit(X[old_m], y_old[old_m]).predict_proba(X[te_m])[:, 1]
        r.loc[te_m, 'T1'] = HGB(**MODEL_PARAMS).fit(X[tr_m], y1[tr_m]).predict_proba(X[te_m])[:, 1]
        r.loc[te_m, 'A'] = HGB(**MODEL_PARAMS).fit(X[tr_m], y1[tr_m], sample_weight=w[tr_m]).predict_proba(X[te_m])[:, 1]
        mb = HGB(**MODEL_PARAMS).fit(X[tr_m], r.grade.to_numpy()[tr_m])
        r.loc[te_m, 'B'] = mb.predict_proba(X[te_m]) @ mb.classes_.astype(float)
        print(f"  {m}: 학습 {tr_m.sum():,}행(현행은 정답 있는 {old_m.sum():,}행) → 채점 {te_m.sum():,}행", flush=True)
    return r


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    return roc_auc_score(y, p) if 0 < y.sum() < len(y) else np.nan


def report_population(o):
    print(f"\n━━ ① 전체 모집단 표본 외 {len(o):,}행 ({o.d.min()}~{o.d.max()}, {o.d.nunique()}일)"
          f" · 기준선 등급1+ {(o.grade >= 1).mean() * 100:.1f}% · 2+ {(o.grade >= 2).mean() * 100:.2f}% · 3 {(o.grade == 3).mean() * 100:.2f}% · 매매당 {o.ret15.mean() * 100:+.2f}%")
    print(f"{'모델':<6}{'AUC(1+)':>9}{'AUC(2+)':>9}  날짜별 상위10:{'등급1+':>8}{'등급2+':>8}{'등급3':>7}{'매매당':>9}   상위10 매매당 월별")
    for k in ('OLD', 'T1', 'A', 'B'):
        top = o.sort_values(k, ascending=False).groupby('d').head(10)
        mon = ' '.join(f"{g.ret15.mean() * 100:+.1f}" for _, g in top.groupby(top.d.str[5:7]))
        print(f"{k:<6}{auc((o.grade >= 1).astype(int), o[k]):>9.3f}{auc((o.grade >= 2).astype(int), o[k]):>9.3f}"
              f"{'':16}{(top.grade >= 1).mean() * 100:>7.1f}%{(top.grade >= 2).mean() * 100:>7.2f}%{(top.grade == 3).mean() * 100:>6.2f}%"
              f"{top.ret15.mean() * 100:>+8.2f}%   {mon}")


def report_signals(o):
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)][['code', 'date']].rename(columns={'code': 'coin', 'date': 'd'})
    ex = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8']].rename(columns={'code': 'coin', 'date': 'd'})
    for k in ('OLD', 'T1', 'A', 'B'):
        o[k + '_pct'] = o.groupby('d')[k].rank(pct=True)
    s = o.merge(ev, on=['coin', 'd']).merge(ex, on=['coin', 'd'], how='left')
    print(f"\n━━ ② 2파 신호 중 학습 테이블에 같은 날 행이 있는 표본 외 {len(s)}건 ({s.d.min()}~{s.d.max()})"
          f" · 전체 매매당 {s.ret15.mean() * 100:+.2f}% 실전 {s.live8.mean() * 100:+.2f}%")
    rng = np.random.default_rng(7)
    for k in ('OLD', 'T1', 'A', 'B'):
        p = s[k + '_pct']
        g = pd.qcut(p.rank(method='first'), 3, labels=['하', '중', '상']).astype(str)
        parts = ' · '.join(f"{q} {s[g == q].ret15.mean() * 100:+.2f}%/실전 {s[g == q].live8.mean() * 100:+.2f}%" for q in ('하', '중', '상'))
        keep = p >= 0.6
        by = {c: v for c, v in s.assign(_k=keep).groupby('coin')}
        cs = list(by)
        bs = []
        for _ in range(1000):
            x = pd.concat([by[c] for c in rng.choice(cs, len(cs))])
            bs.append(x[x._k].ret15.mean() - x.ret15.mean())
        print(f" [{k}] 3등분 {parts}")
        print(f"   백분위 0.6 미만 제외({(~keep).mean() * 100:.0f}% 제외): 매매당 {s[keep].ret15.mean() * 100:+.2f}% (전체 대비 "
              f"{(s[keep].ret15.mean() - s.ret15.mean()) * 100:+.2f}%p [{np.percentile(bs, 5) * 100:+.2f}~{np.percentile(bs, 95) * 100:+.2f}])"
              f" · 실전 {s[keep].live8.mean() * 100:+.2f}%")


if __name__ == '__main__':
    r = load()
    print(f"학습 행 {len(r):,} ({r.d.min()}~{r.d.max()}) · 등급 분포 " +
          ' '.join(f"{g}:{(r.grade == g).mean() * 100:.2f}%" for g in (0, 1, 2, 3)) +
          f" · 현행 정답 있는 행 {r.net_edge_fwd.notna().mean() * 100:.1f}%")
    r = walk_forward(r)
    o = r.dropna(subset=['A']).copy()
    os.makedirs(os.path.join(W2, '..', 'private'), exist_ok=True)
    o.to_pickle(os.path.join(W2, '..', 'private', 'shape_label_compare.pkl'))
    report_population(o)
    report_signals(o)
