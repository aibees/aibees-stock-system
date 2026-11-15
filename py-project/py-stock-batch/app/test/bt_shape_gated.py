"""
bt_shape_gated.py — shape 정답 재설계 2차: 구조 게이트 + 깨어나는 종목 포함 + 상한가 당일 제외.

배경(2026-11-14): 1차(bt_shape_label_compare)에서 새 정답 모델은 '오늘 상한가 → 내일 갭'을 배웠다(상위10의 40%가
신호일 상한가 마감, 그걸 빼면 우위 없음). 급등 '전날'(예: 서한 10/20)은 사전 필터 밑이라 학습 데이터에 없었고,
그냥 넓히면 폭락주로 쏠린다(다음 날 급등의 52%가 고점 대비 -40%↓). 그래서 게이트를 먼저 건다.

정의 — 실행 전에 고정
    데이터   : 전 종목 일봉(stock_ohlcv_daily, KRX), 피처는 배치와 같은 KisService.compute_indicator_df 로 계산(결측 그대로)
    모집단   : 신호일 D 마다 아래를 모두 만족
               대상    보통주, 관리·정지(현재) 아님, 종가 >= 1,000
               유동성  20일 평균 거래대금 >= 5억 (새 사전 필터)  또는  당일 거래대금 >= 5억 (깨어남)
               구조    250일 고점 대비 -40% 초과, 종가 > 120일 이동평균
               제외    D 종가 상한가(전일 대비 +29% 이상) — 체결이 어렵고 '이미 오른 날'
    정답     : 목표 U = D 고가 × 1.15, 손절 S = D+1 시가 × 0.92, 10거래일
               등급 3 = D+1 종가 >= U / 2 = D+1 고가 >= U / 1 = 10일 안 U 가 S 보다 먼저(같은 날이면 손절) / 0
               OLD = 현행 정의 net_edge(D 종가 기준 5봉 고가-저가 차 >= 15%p, 순서 무관) — 같은 모집단·일봉으로 계산
    모델     : OLD / T1(등급>=1) / A(T1 + 무게 3·2·1) / B(등급 다중분류 기대값), shape_train.MODEL_PARAMS, 피처 14개 완전행
    전진 검증 : 2026-01 ~ 2026-10 각 달 — 그 달 시작 20일(달력) 전까지 행으로 학습(2025-01 부터) → 그 달 채점
평가: 날짜별 점수 상위 10 — 등급 비율, 매매 수익(매수가 기준 +15% 익절 / -8% 손절 / 10일, 수수료 0.22%)
      ① 신호일 종가 매수  ② 다음 날 시가 매수. 날짜 단위 부트스트랩 90% 구간, 월별, 깨어남 종목 비중·성과.
한계: 약 10개월 표본 외, 종가 그대로 체결 가정(상한가 마감은 이미 제외), 슬리피지 없음, 피처는 KRX 일봉(배치는 KIS 통합시세).

사용
    poetry run python -m app.test.bt_shape_gated
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService  # noqa: E402
from app.test.eval_shape_proba import DB_URL, _base_user_info  # noqa: E402
from app.test.bt_wave2_trendline import CACHE, outcome  # noqa: E402
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS as F  # noqa: E402
from stock_shared.ml.shape_train import MODEL_PARAMS  # noqa: E402

OUT = os.path.join(CACHE, 'private')
H, FEE = 10, 0.0022
FROM, TO = '2025-01-02', '2026-10-30'
MONTHS = [f'2026-{m:02d}' for m in range(1, 11)]
WEIGHT = {3: 3.0, 2: 2.0, 1: 1.0, 0: 1.0}


def close_entry(o, h, l, c, i):
    e = c[i]; U, S = e * 1.15, e * 0.92
    for k in range(i + 1, i + H + 1):
        if o[k] <= S or o[k] >= U:
            return o[k] / e - 1 - FEE
        if l[k] <= S:
            return -0.08 - FEE
        if h[k] >= U:
            return 0.15 - FEE
    return c[i + H] / e - 1 - FEE


def one(args):
    code, g = args
    g = g.reset_index(drop=True)
    if len(g) < 300:
        return None
    df = pd.DataFrame({'datetime': g.d + ' 00:00:00', 'open': g.o, 'high': g.h, 'low': g.l, 'close': g.c, 'volume': g.v})
    comp = KisService().compute_indicator_df(df.copy(), user_info=_base_user_info())
    o, h, l, c, v = (g[k].to_numpy(float) for k in ('o', 'h', 'l', 'c', 'v'))
    n = len(c)
    amt = c * v
    amt20 = pd.Series(amt).rolling(20).mean().to_numpy()
    ma120 = pd.Series(c).rolling(120).mean().to_numpy()
    hi250 = pd.Series(h).rolling(250, min_periods=200).max().to_numpy()
    d = g.d.to_numpy()
    rows = []
    for i in range(250, n - H - 1):
        if d[i] < FROM or d[i] > TO or c[i] < 1000 or o[i + 1] <= 0:
            continue
        chg = c[i] / c[i - 1] - 1
        liq_old, liq_wake = amt20[i] >= 5e8, (amt20[i] < 5e8) and (amt[i] >= 5e8)
        if not (liq_old or liq_wake) or chg >= 0.29:
            continue
        if not (c[i] / hi250[i] - 1 > -0.40 and c[i] > ma120[i]):
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
        edge = ((h[i + 1:i + 6].max() - c[i]) - (c[i] - l[i + 1:i + 6].min())) / c[i] * 100
        r = {'coin': code, 'd': d[i], 'grade': grade, 'old_y': int(edge >= 15), 'wake': liq_wake, 'chg': chg,
             'ret_close': close_entry(o, h, l, c, i), 'ret_open': outcome(o, h, l, c, i, 0.15)[0],
             'gap1': o[i + 1] / c[i] - 1}
        for col in F:
            r[col] = comp.at[i, col]
        rows.append(r)
    return pd.DataFrame(rows) if rows else None


def build():
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code FROM master_stock", eng).stock_code
    adm = pd.read_sql("SELECT coin, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')])
    b = pd.read_sql(text("SELECT stock_code, trade_date, open_price o, high_price h, low_price l, close_price c, volume v "
                         "FROM stock_ohlcv_daily WHERE trade_date >= '2024-01-01'"), eng)
    b['d'] = (pd.to_datetime(b.trade_date) + pd.Timedelta(hours=9)).dt.strftime('%Y-%m-%d')
    b = b[b.stock_code.str.endswith('0') & ~b.stock_code.isin(bad) & b.stock_code.isin(set(ms))]
    jobs = [(code, g.sort_values('d')[['d', 'o', 'h', 'l', 'c', 'v']]) for code, g in b.groupby('stock_code')]
    print(f"일봉 {len(b):,}행 · {len(jobs)}종목 → 피처 계산", flush=True)
    with Pool(8) as p:
        parts = [x for x in p.imap_unordered(one, jobs, chunksize=16) if x is not None]
    r = pd.concat(parts, ignore_index=True)
    r = r[np.isfinite(r[F].astype(float)).all(axis=1)].reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    r.to_pickle(os.path.join(OUT, 'shape_gated_rows.pkl'))
    return r


def walk_forward(r):
    from sklearn.ensemble import HistGradientBoostingClassifier as HGB
    X = r[F].to_numpy(float)
    y1 = (r.grade.to_numpy() >= 1).astype(int)
    w = r.grade.map(WEIGHT).to_numpy()
    for k in ('OLD', 'T1', 'A', 'B'):
        r[k] = np.nan
    for m in MONTHS:
        cut = (pd.Timestamp(m + '-01') - pd.Timedelta(days=20)).strftime('%Y-%m-%d')
        tr = (r.d < cut).to_numpy(); te = (r.d.str[:7] == m).to_numpy()
        if not te.any():
            continue
        r.loc[te, 'OLD'] = HGB(**MODEL_PARAMS).fit(X[tr], r.old_y.to_numpy()[tr]).predict_proba(X[te])[:, 1]
        r.loc[te, 'T1'] = HGB(**MODEL_PARAMS).fit(X[tr], y1[tr]).predict_proba(X[te])[:, 1]
        r.loc[te, 'A'] = HGB(**MODEL_PARAMS).fit(X[tr], y1[tr], sample_weight=w[tr]).predict_proba(X[te])[:, 1]
        mb = HGB(**MODEL_PARAMS).fit(X[tr], r.grade.to_numpy()[tr])
        r.loc[te, 'B'] = mb.predict_proba(X[te]) @ mb.classes_.astype(float)
        print(f"  {m}: 학습 {tr.sum():,}행 → 채점 {te.sum():,}행", flush=True)
    return r


def ci_days(top, col):
    rng = np.random.default_rng(7)
    byd = {d: g[col].values for d, g in top.groupby('d')}
    ds = list(byd)
    bs = [np.concatenate([byd[x] for x in rng.choice(ds, len(ds))]).mean() for _ in range(1000)]
    return np.percentile(bs, 5) * 100, np.percentile(bs, 95) * 100


def report(r):
    from sklearn.metrics import roc_auc_score
    o = r.dropna(subset=['B']).copy()
    print(f"\n표본 외 {len(o):,}행 ({o.d.min()}~{o.d.max()}, {o.d.nunique()}일, 하루 {len(o) / o.d.nunique():.0f}종목, 깨어남 {o.wake.mean() * 100:.1f}%)")
    print(f"기준(모집단 전체): 등급1+ {(o.grade >= 1).mean() * 100:.1f}% · 2+ {(o.grade >= 2).mean() * 100:.2f}% · 3 {(o.grade == 3).mean() * 100:.2f}%"
          f" · 종가매수 {o.ret_close.mean() * 100:+.2f}% · 시가매수 {o.ret_open.mean() * 100:+.2f}%")
    print(f"\n{'모델':<5}{'AUC1+':>7}{'AUC2+':>7} │ 상위10:{'등급1+':>7}{'2+':>7}{'3':>6}{'깨어남':>7}{'D+1갭':>7} │{'종가매수':>9} {'90% 구간':<16}{'시가매수':>9} {'90% 구간':<16}")
    for k in ('OLD', 'T1', 'A', 'B'):
        top = o.sort_values(k, ascending=False).groupby('d').head(10)
        a, b_ = ci_days(top, 'ret_close'); c_, d_ = ci_days(top, 'ret_open')
        print(f"{k:<5}{roc_auc_score(o.grade >= 1, o[k]):>7.3f}{roc_auc_score(o.grade >= 2, o[k]):>7.3f} │"
              f"{'':7}{(top.grade >= 1).mean() * 100:>6.1f}%{(top.grade >= 2).mean() * 100:>6.2f}%{(top.grade == 3).mean() * 100:>5.2f}%"
              f"{top.wake.mean() * 100:>6.0f}%{top.gap1.mean() * 100:>+6.1f}% │{top.ret_close.mean() * 100:>+8.2f}% [{a:+.2f}~{b_:+.2f}]   "
              f"{top.ret_open.mean() * 100:>+8.2f}% [{c_:+.2f}~{d_:+.2f}]")
    print("\n월별 상위10 종가매수 / 시가매수 (%)")
    mon = {}
    for k in ('OLD', 'A', 'B'):
        top = o.sort_values(k, ascending=False).groupby('d').head(10)
        mon[k + ' 종가'] = top.groupby(top.d.str[:7]).ret_close.mean() * 100
        mon[k + ' 시가'] = top.groupby(top.d.str[:7]).ret_open.mean() * 100
    mon['기준 종가'] = o.groupby(o.d.str[:7]).ret_close.mean() * 100
    print(pd.DataFrame(mon).round(2).to_string())
    print("\n깨어남 종목만 따로(그날 깨어남 중 점수 상위 3)")
    w = o[o.wake]
    print(f"  깨어남 전체 {len(w):,}행: 등급2+ {(w.grade >= 2).mean() * 100:.2f}% · 종가매수 {w.ret_close.mean() * 100:+.2f}% · 시가매수 {w.ret_open.mean() * 100:+.2f}%")
    for k in ('OLD', 'A', 'B'):
        top = w.sort_values(k, ascending=False).groupby('d').head(3)
        print(f"  [{k}] {len(top)}건 등급2+ {(top.grade >= 2).mean() * 100:.1f}% · 종가매수 {top.ret_close.mean() * 100:+.2f}% · 시가매수 {top.ret_open.mean() * 100:+.2f}%")


if __name__ == '__main__':
    p = os.path.join(OUT, 'shape_gated_rows.pkl')
    r = pd.read_pickle(p) if '--cached' in sys.argv and os.path.exists(p) else build()
    print(f"모집단 {len(r):,}행 ({r.d.min()}~{r.d.max()}) · 등급 " + ' '.join(f"{g}:{(r.grade == g).mean() * 100:.2f}%" for g in (0, 1, 2, 3))
          + f" · OLD 양성 {r.old_y.mean() * 100:.1f}% · 깨어남 {r.wake.mean() * 100:.1f}%")
    r = walk_forward(r)
    r.to_pickle(os.path.join(OUT, 'shape_gated_scored.pkl'))
    report(r)
