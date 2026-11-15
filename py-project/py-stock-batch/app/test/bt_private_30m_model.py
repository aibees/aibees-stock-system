"""
bt_private_30m_model.py — 실전(PRIVATE) 후보 연구 ⑤: 30분봉 패턴을 모델로 학습해 고급 후보 1위 고르기.

배경(2026-11-14 사용자): 조건을 같은 무게로 더하면(④ bt_private_30m_basic) 경우의 수·패턴마다 달라야 할 점수를
못 잡는다. 일봉 shape 모델처럼 30분봉 shape 피처·조건 조합을 학습시키면 어떤가.

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다)
    학습 행  : 1분봉 캐시가 있는 모든 (종목, 날) 중 같은 연속 구간에서 앞선 9거래일 이상 분봉이 있는 날(30분봉 130개 이상).
               (캐시는 2파 신호 종목의 신호 전 20일·보유 10일 구간이라 '2파 신호 주변 종목-일' 표본이다)
    피처     : 그날 마지막 30분봉(장 마감 상태)
        M1 shape  : SHAPE_FEATURE_COLUMNS 14개(배치와 같은 compute_indicator_df 를 30분봉에, 결측은 그대로)
        M2 shape+ : M1 + 기본 조건 12개(0/1, bt_private_30m_basic.conds 와 같음) + ATR/종가 + 20봉 고점 대비 눌림
        M0        : 학습 없이 배포 일봉 shape 모델(v1)을 30분봉 피처에 그대로(결측 0 — 라이브와 같음)
    정답     : 다음 날 시가 매수 시 10거래일 안에 +15% 가 -8% 보다 먼저(1/0)
    모델     : shape_train.MODEL_PARAMS 의 HistGradientBoostingClassifier(일봉 shape 모델과 같은 설정)
    전진 검증 : 2026-01 ~ 2026-09 각 달 m — m 시작 20일(달력) 전까지의 행으로 학습 → m 의 행·신호를 채점(표본 외)
평가: 표본 외 2파 신호(고급 = 일봉 shape 백분위 >= 0.6)의 점수 3등분 성과(ret15·live8), 상-하 차이 종목 부트스트랩,
      같은 날 2건↑ 날 점수 1위 vs 지금 1위(일봉 거래량 배수) 날짜 부트스트랩. 전체 표본 외 행 AUC.
한계: 1년치·2파 주변 표본뿐(전 종목 아님), 같은 종목 연속일은 정답 구간이 겹쳐 실제 독립 표본은 더 적다, 슬리피지 없음.

사용
    poetry run python -m app.test.bt_private_30m_model
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService  # noqa: E402
from app.test.bt_wave2_trendline import CACHE, OUT as W2, outcome  # noqa: E402
from app.test.bt_private_30m import MIN_DIR, FROM, shape_pct  # noqa: E402
from app.test.bt_private_intraday import day_bars  # noqa: E402
from app.test.bt_private_30m_basic import conds, FREQ, K  # noqa: E402
from app.test.eval_shape_proba import _base_user_info  # noqa: E402
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS  # noqa: E402

PRE = 9                       # 앞선 거래일 수(포함하면 10일)
COND_COLS = [f'c{k}' for k in range(1, 13)]
M1 = list(SHAPE_FEATURE_COLUMNS)
M2 = M1 + COND_COLS + ['atr30', 'dip30']
MONTHS = [f'2026-{m:02d}' for m in range(1, 10)]


def one(code):
    df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
    dates = df['datetime'].astype(str).str[:10].tolist()
    idx = {d: k for k, d in enumerate(dates)}
    o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
    files = sorted(f[:-4] for f in os.listdir(os.path.join(MIN_DIR, code)) if f.endswith('.pkl') and f[0].isdigit())
    pos = sorted(idx[f'{f[:4]}-{f[4:6]}-{f[6:]}'] for f in files if f'{f[:4]}-{f[4:6]}-{f[6:]}' in idx)
    blocks, cur = [], []
    for p in pos:
        if cur and p != cur[-1] + 1:
            blocks.append(cur); cur = []
        cur.append(p)
    if cur:
        blocks.append(cur)
    from stock_shared.ml import shape_model
    ks, ui, rows = KisService(), _base_user_info(), []
    for blk in blocks:
        if len(blk) <= PRE:
            continue
        parts, days = [], []
        for p in blk:
            b = day_bars(code, dates[p], FREQ)
            if b is None:
                parts = None
                break
            parts.append(b); days.append(dates[p])
        if parts is None:
            continue
        b = pd.concat(parts)
        b['datetime'] = [f"{dd} {9 + (k * FREQ) // 60:02d}:{(k * FREQ) % 60:02d}:00" for dd, k in zip(b.day, b.index)]
        b = b.reset_index(drop=True)[['datetime', 'open', 'high', 'low', 'close', 'volume']]
        raw = ks.compute_indicator_df(b.copy(), user_info=ui)
        filled = raw.fillna(0.0).to_dict('records')
        last_of = raw.groupby(raw['datetime'].str[:10]).apply(lambda g: g.index[-1]).to_dict()
        for n, (p, d) in enumerate(zip(blk, days)):
            if n < PRE or p + 10 >= len(c):
                continue
            k = last_of[d]
            t, y, yy = filled[k], filled[k - 1], filled[k - 2]
            r15, x15, _ = outcome(o, h, l, c, p, 0.15)
            row = {'code': code, 'date': d, 'y': int(x15 == 'W'), 'ret15': r15}
            for col in M1:
                row[col] = raw.at[k, col]
            cs = conds(t, y, yy, detail=True)
            row.update({f'c{j + 1}': int(v) for j, v in enumerate(cs)})
            close, rh = t['close'], t['recent_high']
            row['atr30'] = t['atr'] / close if close else np.nan
            row['dip30'] = (close - rh) / rh if rh else np.nan
            row['m0'] = shape_model.score({col: t[col] for col in M1})
            rows.append(row)
    return rows


def walk_forward(r):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from stock_shared.ml.shape_train import MODEL_PARAMS
    r = r.copy()
    r['m1'] = np.nan; r['m2'] = np.nan
    for m in MONTHS:
        cut = (pd.Timestamp(m + '-01') - pd.Timedelta(days=20)).strftime('%Y-%m-%d')
        tr, te = r[r.date < cut], r[r.date.str[:7] == m]
        if len(te) == 0 or len(tr) < 300 or tr.y.sum() < 30:
            print(f"  {m}: 학습 {len(tr)}행(양성 {int(tr.y.sum())}) — 건너뜀")
            continue
        for name, cols in (('m1', M1), ('m2', M2)):
            mdl = HistGradientBoostingClassifier(**MODEL_PARAMS).fit(tr[cols].to_numpy(float), tr.y.to_numpy())
            r.loc[te.index, name] = mdl.predict_proba(te[cols].to_numpy(float))[:, 1]
        print(f"  {m}: 학습 {len(tr)}행(양성 {tr.y.mean() * 100:.0f}%) → 채점 {len(te)}행")
    oos = r.dropna(subset=['m1'])
    print(f"표본 외 행 {len(oos)} · 양성 {oos.y.mean() * 100:.1f}% · AUC M0 {roc_auc_score(oos.y, oos.m0.fillna(0)):.3f}"
          f" M1 {roc_auc_score(oos.y, oos.m1):.3f} M2 {roc_auc_score(oos.y, oos.m2):.3f}")
    return r


def report(s0all):
    rng = np.random.default_rng(7)
    for scope, s0 in (('고급(shape 백분위 >= 0.6)', s0all[s0all.pct >= 0.6]), ('2파 신호 전체', s0all)):
        print(f"\n━━ 표본 외 {scope}: {len(s0)}건 ({s0.date.min()}~{s0.date.max()}) · 같은 날 2건↑ {(s0.groupby('date').size() >= 2).sum()}일"
              f" · 전체 매매당 {s0.ret15.mean() * 100:+.2f}% 실전 {s0.live8.mean() * 100:+.2f}%")
        for col, lab in (('m0', 'M0 일봉 모델 그대로'), ('m1', 'M1 30분 shape'), ('m2', 'M2 shape+조건')):
            s = s0.dropna(subset=[col]).copy()
            s['_g'] = pd.qcut(s[col].rank(method='first'), 3, labels=['하', '중', '상']).astype(str)
            parts = ' · '.join(f"{g} {s[s._g == g].ret15.mean() * 100:+.2f}%/실전 {s[s._g == g].live8.mean() * 100:+.2f}%" for g in ('하', '중', '상'))
            by = {k: v for k, v in s.groupby('code')}
            ks = list(by)
            dd, dd8 = [], []
            for _ in range(1000):
                x = pd.concat([by[k] for k in rng.choice(ks, len(ks))])
                dd.append(x[x._g == '상'].ret15.mean() - x[x._g == '하'].ret15.mean())
                dd8.append(x[x._g == '상'].live8.mean() - x[x._g == '하'].live8.mean())
            d = s[s._g == '상'].ret15.mean() - s[s._g == '하'].ret15.mean()
            d8 = s[s._g == '상'].live8.mean() - s[s._g == '하'].live8.mean()
            print(f" [{lab}] 3등분 {parts}")
            print(f"   상-하 매매당 {d * 100:+.2f}%p [{np.nanpercentile(dd, 5) * 100:+.2f}~{np.nanpercentile(dd, 95) * 100:+.2f}]"
                  f" · 실전 {d8 * 100:+.2f}%p [{np.nanpercentile(dd8, 5) * 100:+.2f}~{np.nanpercentile(dd8, 95) * 100:+.2f}]")
            m = s.groupby('date').filter(lambda g: len(g) >= 2)
            if len(m):
                now = m.loc[m.groupby('date').vol_ratio.idxmax()].set_index('date')
                new = m.loc[m.groupby('date')[col].idxmax()].set_index('date')
                out = []
                for c2 in ('ret15', 'live8'):
                    diff = (new[c2] - now[c2]).dropna().values
                    bs = [rng.choice(diff, len(diff)).mean() for _ in range(2000)]
                    out.append(f"{c2} {diff.mean() * 100:+.2f}%p [{np.percentile(bs, 5) * 100:+.2f}~{np.percentile(bs, 95) * 100:+.2f}]")
                same = (now.code == new.code).mean()
                print(f"   같은 날 2건↑ {len(now)}일: 점수 1위 - 지금 1위 " + ' · '.join(out) + f" (1위 같은 날 {same * 100:.0f}%)")


if __name__ == '__main__':
    codes = sorted(x for x in os.listdir(MIN_DIR) if os.path.isdir(os.path.join(MIN_DIR, x)))
    with Pool(8) as p:
        rows = [x for part in p.map(one, codes) for x in part]
    r = pd.DataFrame(rows)
    print(f"학습용 종목-일 {len(r)}행 · {r.code.nunique()}종목 · {r.date.min()}~{r.date.max()} · 양성 {r.y.mean() * 100:.1f}%")
    r = walk_forward(r)
    r.to_pickle(os.path.join(CACHE, 'private', 'm30_model_rows.pkl'))
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2) & (ev.date >= FROM)][['code', 'date', 'vol_ratio']]
    ex = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8']]
    s = r.dropna(subset=['m1']).merge(ev, on=['code', 'date']).merge(ex, on=['code', 'date'], how='left')
    s = s.merge(shape_pct(set(s.date)), on=['code', 'date'], how='left')
    report(s)
