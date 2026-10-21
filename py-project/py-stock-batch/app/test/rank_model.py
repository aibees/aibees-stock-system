"""
rank_model.py — 일별 종합 1등을 가려낼 순위 모델(연구용). 목표를 실제 매매와 맞춘다.

왜 새로 만드나
    현행 2단계(shape 상위 10 → 모멘텀 재정렬) 1위는 "이미 가장 많이 오른 종목"이 뽑혀
    10일 안에 -8% 먼저 닿는 비율이 58%로 가장 높았다(1~10위 중 최악). 당시 목표가
    "5일 내 장중 고가 기준 큰 출렁임"이라 하락 위험이 빠져 있었기 때문이다.

목표(라벨) — 사용자 기준
    D+1 시가 매수, 10거래일 안에 장중 고가 +T 먼저 = WIN, 장중 저가 -8% 먼저 = FAIL(같은 날 둘 다면 FAIL),
    둘 다 없으면 NONE. T = 15%, 25% 두 모델을 따로 만든다.
    규칙 수익(ret_T): WIN +T, FAIL -8%(이틀째 이후 갭이면 시가), NONE 10일째 종가. 왕복 수수료 차감.
    점수 = 기대손익 = P(WIN)·T + P(NONE)·E[NONE 수익] - P(FAIL)·8%  → 하루 안에서 큰 순으로 1~10위.

후보군 — 필터 통과 전 종목(현행 2단계 필터에 묶이지 않음)
    종가 >= 1,000원, 20일 평균 거래대금 >= 5억, 시가총액(그날 종가 × 현재 상장주식수, 근사) >= 1,000억,
    보통주만(코드 끝자리 0), 관리종목·거래정지(현재 상태) 제외, 250봉 이상.

피처(전부 그날까지의 데이터만)
    가격·과열 : 1/5/20/60일 수익률, 당일 갭·범위·종가 위치, 20/60/120일선 이격, RSI, MACD, 볼린저 위치,
                ATR%, 거래량 비율, 연속 상승일, 250일 고가·저가 대비, 거래대금, 시총
    shape     : SHAPE_FEATURE_COLUMNS + 배포 모델 proba
    스윙      : 하루씩 진행하는 ZigZag(ATR 2.5·4배) — 추세 구조, 마지막 스윙 종류·경과 봉수·거리,
                1파 고점 돌파·3파 이른 진입·쌍바닥 돌파 이후 경과 봉수
    업종·시장 : 업종(대분류) 평균 5·20일 수익률과 종목의 초과분, 시장 평균 5·20일 수익률, 20일선 위 종목 비율
    순위형    : 그날 후보 안에서 5일 수익률·RSI·거래량비·20일선 이격·proba 백분위
    ※ 수급은 2026-08 이후뿐이라 5년 학습에서 뺀다.

검증 — 연도별 전진: 시험 2024 / 2025 / 2026, 학습은 시험 시작 21일(캘린더) 전까지 전부(라벨 10일 겹침 차단)
    매일 1~10위의 성공·실패율·규칙 수익을 현행 composite 순위, shape_proba 순, 후보 평균과 비교.

사용
    poetry run python -m app.test.rank_model --phase data      # 데이터셋 생성(약 수 분, 병렬)
    poetry run python -m app.test.rank_model --phase train     # 학습·평가·리포트
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

CACHE = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
OUT = os.path.join(CACHE, 'rank_model')
H, STOP, FEE = 10, 0.08, 0.0022
TARGETS = (0.15, 0.25)
WARMUP = 250
MIN_PRICE, MIN_AMOUNT, MIN_CAP = 1000, 5e8, 1000e8
TEST_YEARS = ('2024', '2025', '2026')

_G = {}


def _init(meta):
    _G.update(meta)


# ══════════════════════════════════════════════════════════════════
# 하루씩 진행하는 ZigZag 상태(봉마다) — bt_entry_events.scan_events 와 같은 규칙
# ══════════════════════════════════════════════════════════════════
def zigzag_states(high, low, a, mult, min_pct=3.0):
    n = len(high)
    struct = np.zeros(n, np.float32)       # +1 고점·저점 모두 높아짐 / -1 모두 낮아짐 / 0
    last_kind = np.zeros(n, np.float32)    # 마지막 확정 스윙 +1 H / -1 L
    since_piv = np.full(n, np.nan, np.float32)
    piv = []
    direction, ext_i, hi_i, lo_i = 0, 0, 0, 0

    def thr(i, ref):
        return max(a[i] * mult, ref * min_pct / 100)

    for i in range(1, n):
        if direction == 0:
            if high[i] > high[hi_i]:
                hi_i = i
            if low[i] < low[lo_i]:
                lo_i = i
            if lo_i < hi_i and high[hi_i] - low[lo_i] >= thr(i, low[lo_i]):
                piv.append(('L', lo_i, low[lo_i])); direction, ext_i = 1, hi_i
            elif hi_i < lo_i and high[hi_i] - low[lo_i] >= thr(i, high[hi_i]):
                piv.append(('H', hi_i, high[hi_i])); direction, ext_i = -1, lo_i
        elif direction > 0:
            if high[i] > high[ext_i]:
                ext_i = i
            elif high[ext_i] - low[i] >= thr(i, high[ext_i]):
                piv.append(('H', ext_i, high[ext_i])); direction, ext_i = -1, i
        else:
            if low[i] < low[ext_i]:
                ext_i = i
            elif high[i] - low[ext_i] >= thr(i, low[ext_i]):
                piv.append(('L', ext_i, low[ext_i])); direction, ext_i = 1, i
        if piv:
            last_kind[i] = 1 if piv[-1][0] == 'H' else -1
            since_piv[i] = i - piv[-1][1]
            hs = [p[2] for p in piv[-4:] if p[0] == 'H']
            ls = [p[2] for p in piv[-4:] if p[0] == 'L']
            if len(hs) >= 2 and len(ls) >= 2:
                struct[i] = 1 if (hs[-1] > hs[-2] and ls[-1] > ls[-2]) else -1 if (hs[-1] < hs[-2] and ls[-1] < ls[-2]) else 0
    return struct, last_kind, since_piv


def _since(n, idxs, cap=60):
    out = np.full(n, np.nan, np.float32)
    for j in sorted(idxs):
        end = min(n, j + cap + 1)
        out[j:end] = np.arange(end - j, dtype=np.float32)
    return out


def labels(o, h, l, c, T):
    """봉 i 신호 → (결과 0=FAIL/1=NONE/2=WIN, 규칙 수익, 손절 전 최대 상승)."""
    n = len(c)
    res = np.full(n, np.nan, np.float32)
    ret = np.full(n, np.nan, np.float32)
    mup = np.full(n, np.nan, np.float32)
    for i in range(n - H - 1):
        e = o[i + 1]
        if e <= 0:
            continue
        peak, r, rr = 0.0, 1, None
        for k in range(i + 1, i + H + 1):
            if l[k] / e - 1 <= -STOP:
                r, rr = 0, (-STOP if k == i + 1 else min(o[k] / e - 1, -STOP))
                break
            peak = max(peak, h[k] / e - 1)
            if peak >= T:
                r, rr = 2, (T if k == i + 1 else max(o[k] / e - 1, T))
                break
        if rr is None:
            rr = c[i + H] / e - 1
        res[i], ret[i], mup[i] = r, rr - FEE, peak
    return res, ret, mup


def build_stock(path):
    from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
    from stock_shared.chart_analysis.indicators import atr as atr_fn
    from app.test.bt_entry_events import scan_events
    code = os.path.basename(path)[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return None
    df = pd.read_pickle(path).reset_index(drop=True)
    n = len(df)
    if n < WARMUP + H + 5:
        return None
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    cs = pd.Series(c)
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    cap = c * _G['shares'][code]
    ok = (np.arange(n) >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (cap >= MIN_CAP)
    if not _G.get('keep_recent'):          # 학습용은 10일 결과가 확정된 날만. 예시·운영용은 최근 날도 남긴다(라벨 NaN)
        ok &= np.arange(n) < n - H - 1
    if not ok.any():
        return None

    f = pd.DataFrame({'date': df['datetime'].astype(str).str[:10], 'code': code})
    prev = cs.shift(1).to_numpy()
    for k in (1, 5, 20, 60):
        f[f'ret{k}'] = c / cs.shift(k).to_numpy() - 1
    f['gap'] = o / prev - 1
    f['range'] = (h - l) / prev
    f['close_pos'] = np.where(h > l, (c - l) / np.where(h > l, h - l, 1), 0.5)
    for k in ('ema20', 'ema60', 'ema120'):
        f[f'd_{k}'] = c / df[k].to_numpy(float) - 1
    f['rsi'] = df['ind_rsi14'].to_numpy(float)
    f['macd_n'] = df['ind_macd_hist_norm'].to_numpy(float)
    bu, bl = df['bb_upper'].to_numpy(float), df['bb_lower'].to_numpy(float)
    f['bb_pos'] = np.where(bu > bl, (c - bl) / np.where(bu > bl, bu - bl, 1), 0.5)
    f['atr_pct'] = df['atr'].to_numpy(float) / c
    f['vol_ratio'] = df['ind_vol_ratio_today'].to_numpy(float)
    vs = pd.Series(v)
    f['vol5_20'] = (vs.rolling(5).mean() / vs.rolling(20).mean()).to_numpy()
    up = (cs.diff() > 0).astype(int)
    f['up_streak'] = up.groupby((up != up.shift()).cumsum()).cumsum().where(up == 1, 0).to_numpy()
    f['hi250'] = c / pd.Series(h).rolling(250).max().to_numpy() - 1
    f['lo250'] = c / pd.Series(l).rolling(250).min().to_numpy() - 1
    f['log_amt20'] = np.log10(np.maximum(amt20, 1))
    f['log_cap'] = np.log10(np.maximum(cap, 1))
    f['downtrend'] = df['downtrend_ratio'].to_numpy(float) if 'downtrend_ratio' in df else np.nan
    for col in SHAPE_FEATURE_COLUMNS:
        if col not in f:
            f[col] = df[col].to_numpy(float)
    f['proba'] = df['proba'].to_numpy(float)

    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    for mult in (2.5, 4.0):
        tag = str(mult).replace('.', '')
        st, lk, sp = zigzag_states(h, l, a, mult)
        f[f'zz{tag}_struct'], f[f'zz{tag}_lastkind'], f[f'zz{tag}_since'] = st, lk, sp
        ev = scan_events(df, a, mult)
        for name in ('w3_break', 'w3_early', 'dbl_bottom'):
            f[f'zz{tag}_{name}'] = _since(n, [i for k, i, *_ in ev if k == name])

    for T in TARGETS:
        t = int(T * 100)
        r, rr, mu = labels(o, h, l, c, T)
        f[f'res{t}'], f[f'ret{t}r'], f[f'mup{t}'] = r, rr, mu
    # 참고 라벨: D+1 시가 → D+10 종가 (손절·익절 없이)
    f['ret10c'] = np.r_[c[H:n - 1] / o[1:n - H] - 1, [np.nan] * (H + 1)]
    f['sector'] = _G['sector'].get(code, '기타')
    f = f[ok]
    num = f.select_dtypes(include=['float64']).columns
    f[num] = f[num].astype(np.float32)
    return f


def phase_data():
    from sqlalchemy import create_engine
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares, idx_bztp_lcls_name FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')
                       | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(v) for k, v in zip(ms.stock_code, ms.listed_shares) if v},
            'sector': {k: (v or '기타') for k, v in zip(ms.stock_code, ms.idx_bztp_lcls_name)}, 'bad': bad}
    paths = sorted(p for p in (os.path.join(CACHE, 'stocks', x) for x in os.listdir(os.path.join(CACHE, 'stocks'))))
    t0 = time.time()
    parts = []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for n, part in enumerate(pool.imap_unordered(build_stock, paths, chunksize=8), 1):
            if part is not None and len(part):
                parts.append(part)
            if n % 300 == 0:
                print(f"[data] {n}/{len(paths)} · {sum(len(p) for p in parts):,}행 · {time.time() - t0:.0f}s", flush=True)
    d = pd.concat(parts, ignore_index=True)

    # 업종·시장(그날 후보 전체 기준) + 그날 안 백분위
    g = d.groupby('date')
    d['mkt_ret5'], d['mkt_ret20'] = g['ret5'].transform('mean'), g['ret20'].transform('mean')
    d['breadth20'] = g['d_ema20'].transform(lambda s: (s > 0).mean())
    gs = d.groupby(['date', 'sector'])
    d['sec_ret5'], d['sec_ret20'] = gs['ret5'].transform('mean'), gs['ret20'].transform('mean')
    d['rel_sec5'], d['rel_sec20'] = d['ret5'] - d['sec_ret5'], d['ret20'] - d['sec_ret20']
    for col in ('ret5', 'rsi', 'vol_ratio', 'd_ema20', 'proba', 'ret20'):
        d[f'pr_{col}'] = g[col].rank(pct=True).astype(np.float32)
    d['n_cand'] = g['code'].transform('size').astype(np.float32)
    os.makedirs(OUT, exist_ok=True)
    d.to_pickle(os.path.join(OUT, 'dataset.pkl'))
    print(f"[data] 완료 {len(d):,}행 · {d['code'].nunique()}종목 · {d['date'].nunique()}일 ({d['date'].min()}~{d['date'].max()}) · {time.time() - t0:.0f}s")
    for T in TARGETS:
        t = int(T * 100)
        vc = d[f'res{t}'].value_counts(normalize=True).sort_index()
        print(f"  +{t}%: FAIL {vc.get(0.0, 0) * 100:.1f}% · NONE {vc.get(1.0, 0) * 100:.1f}% · WIN {vc.get(2.0, 0) * 100:.1f}% · 규칙수익 평균 {d[f'ret{t}r'].mean() * 100:+.2f}%")


# ══════════════════════════════════════════════════════════════════
# 학습·평가
# ══════════════════════════════════════════════════════════════════
LABEL_COLS = [f'{p}{int(T * 100)}{s}' for T in TARGETS for p, s in (('res', ''), ('ret', 'r'), ('mup', ''))] + ['ret10c']
META_COLS = ['date', 'code', 'sector']
# 하루 안의 모든 후보에 같은 값 — 일별 순위에는 정보가 없고 해마다 분포만 달라 해가 된다(1차 중요도 음수)
DAY_LEVEL = ['n_cand', 'mkt_ret5', 'mkt_ret20', 'breadth20', 'sec_ret5', 'sec_ret20']


def features(d):
    return [c for c in d.columns if c not in LABEL_COLS + META_COLS + DAY_LEVEL and not c.startswith('_')]


def fit_reg(train, test, T, feats, min_leaf=300):
    """그날 후보 평균 대비 초과 규칙수익을 맞히는 회귀 — 시장 전체 등락이 아니라 하루 안의 우열만 배운다."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    t = int(T * 100)
    y = (train[f'ret{t}r'] - train.groupby('date')[f'ret{t}r'].transform('mean')).to_numpy()
    reg = HistGradientBoostingRegressor(loss='absolute_error', max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                        min_samples_leaf=min_leaf, l2_regularization=1.0, early_stopping=False, random_state=7)
    reg.fit(train[feats].to_numpy(np.float32), y)
    return reg.predict(test[feats].to_numpy(np.float32))


def paired_top1(sel_a, sel_b, T):
    """같은 날 1위끼리 규칙수익 차이(a-b) 평균과 90% 부트스트랩 구간."""
    t = int(T * 100)
    a = sel_a[sel_a['rk'] == 1].set_index('date')[f'ret{t}r']
    b = sel_b[sel_b['rk'] == 1].set_index('date')[f'ret{t}r']
    d = (a - b).dropna().to_numpy()
    if not len(d):
        return np.nan, np.nan, np.nan, 0
    rng = np.random.default_rng(7)
    bs = [rng.choice(d, len(d)).mean() for _ in range(2000)]
    return d.mean() * 100, np.percentile(bs, 5) * 100, np.percentile(bs, 95) * 100, len(d)


def fit_score(train, test, T, feats, min_leaf=300):
    from sklearn.ensemble import HistGradientBoostingClassifier
    t = int(T * 100)
    y = train[f'res{t}'].astype(int).to_numpy()
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=min_leaf,
                                         l2_regularization=1.0, early_stopping=False, random_state=7)
    clf.fit(train[feats].to_numpy(np.float32), y)
    p = clf.predict_proba(test[feats].to_numpy(np.float32))
    cls = list(clf.classes_)
    pf, pn, pw = (p[:, cls.index(k)] if k in cls else 0 for k in (0, 1, 2))
    none_mean = float(train.loc[train[f'res{t}'] == 1, f'ret{t}r'].mean())
    return pw * T + pn * none_mean - pf * STOP, pw, pf, clf


def eval_ranked(test, score_col, T, k_max=10):
    """하루마다 score 큰 순 1~k_max 위의 결과."""
    t = int(T * 100)
    s = test.sort_values(['date', score_col], ascending=[True, False])
    s['rk'] = s.groupby('date').cumcount() + 1
    s = s[s['rk'] <= k_max]
    return s[['date', 'code', 'rk', f'res{t}', f'ret{t}r', f'mup{t}']]


def summarize(sel, T, ks=(1, 3, 5, 10)):
    t = int(T * 100)
    out = {}
    for k in ks:
        g = sel[sel['rk'] <= k]
        out[k] = ((g[f'res{t}'] == 2).mean() * 100, (g[f'res{t}'] == 0).mean() * 100, g[f'ret{t}r'].mean() * 100, len(g))
    return out


def phase_train(gate_days=None):
    d_full = pd.read_pickle(os.path.join(OUT, 'dataset.pkl'))
    feats = features(d_full)
    d = d_full
    min_leaf = 300
    if gate_days is not None:
        # 매수 게이트(필수): ATR 4배 스윙 1파 고점 종가 돌파 후 gate_days 거래일 이내 — 이 안에서만 고른다
        d = d_full[d_full['zz40_w3_break'] <= gate_days].copy()
        min_leaf = 60
        print(f"[게이트] 1파 고점 돌파(ATR 4배) {gate_days}일 이내만: {len(d):,}행 · 하루 평균 {len(d) / d['date'].nunique():.1f}종목")
    print(f"데이터 {len(d):,}행 · 피처 {len(feats)}개")
    comp = pd.read_pickle(os.path.join(CACHE, 'eval.pkl'))[['datetime', 'coin', 'composite_rank']]
    comp.columns = ['date', 'code', 'comp_rank']
    results, importances = [], {}
    for T in TARGETS:
        t = int(T * 100)
        print(f"\n════════ 목표 +{t}% / 손절 -8% / 10거래일 ════════")
        hdr = f"{'연도':<6}{'방식':<22}" + ''.join(f"{'상위' + str(k):>24}" for k in (1, 3, 5, 10))
        print(hdr + "\n" + ' ' * 28 + ''.join(f"{'성공/실패/규칙수익':>24}" for _ in range(4)))
        for year in TEST_YEARS:
            start = pd.Timestamp(f'{year}-01-01')
            cut = (start - pd.Timedelta(days=21)).strftime('%Y-%m-%d')
            train = d[d['date'] < cut]
            test = d[(d['date'] >= f'{year}-01-01') & (d['date'] <= f'{year}-12-31')].copy()
            if test.empty:
                continue
            test['score'], test['pw'], test['pf'], clf = fit_score(train, test, T, feats, min_leaf)
            test['reg'] = fit_reg(train, test, T, feats, min_leaf)
            rows = {'모델(기대손익)': eval_ranked(test, 'score', T),
                    '모델(성공확률만)': eval_ranked(test, 'pw', T),
                    '모델(초과수익 회귀)': eval_ranked(test, 'reg', T),
                    'shape_proba 순': eval_ranked(test, 'proba', T)}
            if gate_days is not None:
                test['_recent'] = -test['zz40_w3_break']          # 가장 최근에 돌파한 순
                rows['최근 돌파 순'] = eval_ranked(test, '_recent', T)
            # 현행 composite 순위 — 운영 그대로(게이트 없음), 필터 통과 후보에 든 것만
            full_test = d_full[(d_full['date'] >= f'{year}-01-01') & (d_full['date'] <= f'{year}-12-31')]
            cm = full_test.merge(comp, on=['date', 'code'])
            cm['rk'] = cm['comp_rank']
            rows['현행 composite 순위'] = cm[['date', 'code', 'rk', f'res{t}', f'ret{t}r', f'mup{t}']]
            rnd = test.copy(); rnd['rk'] = 1
            base = {1: ((rnd[f'res{t}'] == 2).mean() * 100, (rnd[f'res{t}'] == 0).mean() * 100, rnd[f'ret{t}r'].mean() * 100, len(rnd))}
            for name, sel in rows.items():
                sm = summarize(sel, T)
                print(f"{year:<6}{name:<22}" + ''.join(f"{v[0]:>7.1f}/{v[1]:>5.1f}/{v[2]:>+6.2f}%".rjust(24) for v in sm.values()))
                results.append({'T': t, 'year': year, 'method': name, **{f'k{k}_win': v[0] for k, v in sm.items()},
                                **{f'k{k}_fail': v[1] for k, v in sm.items()}, **{f'k{k}_ret': v[2] for k, v in sm.items()}})
                if name.startswith('모델'):
                    sel.merge(test[['date', 'code', 'score', 'pw', 'pf', 'reg']], on=['date', 'code']).assign(T=t, year=year, method=name) \
                        .to_pickle(os.path.join(OUT, f'picks{"_g" + str(gate_days) if gate_days is not None else ""}_{t}_{year}_{name}.pkl'))
            for nm in ('모델(성공확률만)', '모델(초과수익 회귀)', '모델(기대손익)'):
                m_, lo_, hi_, nd = paired_top1(rows[nm], rows['현행 composite 순위'], T)
                print(f"{'':<6}  └ {nm} 1위 - 현행 1위 (같은 날 {nd}일): {m_:+.2f}%p [90% {lo_:+.2f}~{hi_:+.2f}]")
            b = base[1]
            print(f"{year:<6}{('게이트 후보 평균' if gate_days is not None else '후보 전체 평균'):<22}{b[0]:>7.1f}/{b[1]:>5.1f}/{b[2]:>+6.2f}%".rjust(0) + f"   (하루 평균 후보 {len(test) / test['date'].nunique():.0f}종목)")
            results.append({'T': t, 'year': year, 'method': '후보 전체 평균', 'k1_win': b[0], 'k1_fail': b[1], 'k1_ret': b[2]})
            if year == TEST_YEARS[-2]:     # 중요도는 한 fold 로(가장 데이터 많은 2025)
                from sklearn.inspection import permutation_importance
                smp = test.sample(min(40000, len(test)), random_state=7)
                y = smp[f'res{t}'].astype(int).to_numpy()
                pi = permutation_importance(clf, smp[feats].to_numpy(np.float32), y, n_repeats=3, random_state=7,
                                            scoring='neg_log_loss', n_jobs=4)
                importances[t] = pd.Series(pi.importances_mean, index=feats).sort_values(ascending=False)
    pd.DataFrame(results).to_csv(os.path.join(OUT, f'results{"_g" + str(gate_days) if gate_days is not None else ""}.csv'), index=False)
    for t, imp in importances.items():
        print(f"\n── +{t}% 모델 피처 중요도(2025 시험, 로그손실 기준 상위 20)")
        print('  ' + ' · '.join(f"{k} {v * 1000:.2f}" for k, v in imp.head(20).items()))
        print('  (하위) ' + ' · '.join(f"{k} {v * 1000:.2f}" for k, v in imp.tail(8).items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['data', 'train', 'all'], default='all')
    ap.add_argument('--gate-days', type=int, default=None, help='매수 게이트: 1파 고점 돌파(ATR 4배) 후 N거래일 이내만')
    args = ap.parse_args()
    if args.phase in ('data', 'all'):
        phase_data()
    if args.phase in ('train', 'all'):
        phase_train(args.gate_days)



if __name__ == '__main__':
    main()
