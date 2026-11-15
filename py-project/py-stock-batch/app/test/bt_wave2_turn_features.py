"""
bt_wave2_turn_features.py — 차트가 꺾일 때의 공통점(BB·MACD·OBV·RSI·거래량)이 '큰 승자'와 '가짜 상승'을 가르는가.

대상·판정은 bt_wave2_fake_rise 와 동일(2파 추세선 돌파+거래량 2배↑, base15, 승패는 장중 고가·저가 기준).
지표는 전부 그날 종가까지 아는 값이고, 비교 대상은 아직 보유 중인 봉만이다.

[A] +3% 최초 도달일의 지표 비교 — 이 시점에 이미 운명이 갈려 있는가(종가 기준 판독)
[B] 도달 후 보유 중 매일의 지표 비교 — '도달 후 경과일' 같은 칸끼리 비교
    ※ B 는 손절 직전 봉이 포함돼 가짜 상승 쪽이 구조적으로 약해 보인다. 판단은 C 로 한다.
[C] 사전 고정한 꺾임 신호를 청산 규칙으로 채점(발동 다음 날 시가 체결). 큰 승자 자름이 최우선 지표.
    T1 BB 상단 복귀 : 최근 3봉 안에 고가가 상단 터치 + 오늘 종가 상단 아래
    T2 MACD 꺾임    : 히스토그램 기울기 + → -
    T3 OBV 꺾임     : OBV 3일 기울기 + → -
    T4 OBV 데드크로스: OBV 가 시그널 아래로
    T5 RSI 꺾임     : 진입 후 RSI 고점 대비 -10
    T6 동시 꺾임    : T1 상태 + MACD 기울기 음 + OBV 기울기 음
AUC: 지표가 높을수록 가짜 상승이면 >0.5 (0.5 = 구별 못 함). 구간은 종목 단위 부트스트랩 90%.

사용
    poetry run python -m app.test.bt_wave2_turn_features
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import rankdata

sys.path.insert(0, '../shared')

from app.test.bt_wave2_fake_rise import ARM, CACHE, FEE, H, base_path, boot
from app.test.bt_wave2_trendline import OUT as W2

FEATS = {'pctb': 'BB %B', 'bb_revert': 'BB 상단 터치 후 복귀', 'hist_slope': 'MACD 히스토그램 기울기', 'obv_slope3': 'OBV 3일 기울기',
         'obv_gap': 'OBV-시그널 간격', 'rsi_drop': 'RSI 고점 대비 하락', 'vol3': '거래량/직전 3일 평균'}
FLAGS = {'T1': 'T1 BB 상단 복귀', 'T2': 'T2 MACD 기울기 꺾임', 'T3': 'T3 OBV 기울기 꺾임', 'T4': 'T4 OBV 데드크로스',
         'T5': 'T5 RSI 고점 -10', 'T6': 'T6 동시 꺾임(BB+MACD+OBV)'}


def indicators(df):
    c = df['close'].astype(float)
    hist = df['macd'].astype(float) - df['macd_s'].astype(float)
    obv, sig = df['obv'].astype(float), df['obv_signal'].astype(float)
    vavg = df['volume'].astype(float).rolling(20).mean()
    ub = df['bb_upper'].astype(float)
    lb = df['bb_lower'].astype(float)
    x = pd.DataFrame({
        'pctb': (c - lb) / (ub - lb).replace(0, np.nan),
        'hist_slope': hist.diff() / c,
        'obv_slope3': (obv - obv.shift(3)) / (vavg * 3 + 1e-9),
        'obv_gap': (obv - sig) / (vavg + 1e-9),
        'vol3': df['volume'].astype(float) / df['volume'].astype(float).shift(1).rolling(3).mean().replace(0, np.nan),
    })
    touch = (df['high'].astype(float) >= ub).astype(float).rolling(3).max()
    x['bb_revert'] = ((touch == 1) & (c < ub)).astype(float)
    x['t2'] = (x.hist_slope < 0) & (x.hist_slope.shift(1) >= 0)
    x['t3'] = (x.obv_slope3 < 0) & (x.obv_slope3.shift(1) >= 0)
    x['t4'] = (obv < sig) & (obv.shift(1) >= sig.shift(1))
    x['t6'] = (x.bb_revert == 1) & (x.hist_slope < 0) & (x.obv_slope3 < 0)
    return x


def evaluate():
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)]
    trades, panel = [], []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
        df['datetime'] = df['datetime'].astype(str).str[:10]
        o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
        rsi = df['rsi'].to_numpy(float)
        x = indicators(df)
        idx = {d: k for k, d in enumerate(df['datetime'])}
        for s in g.itertuples():
            i = idx.get(s.date)
            if i is None or i + H + 1 >= len(c):
                continue
            e = o[i + 1]
            ret, res, end_d, peak = base_path(o, h, l, c, i, e)
            t = {'tid': len(trades), 'code': code, 'year': s.year, 'base': ret, 'res': res, 'armed': peak >= ARM}
            arm_d, rsi_pk = None, rsi[i]
            for d in range(1, end_d):           # 종료 봉은 이미 청산이라 제외
                k = i + d
                rsi_pk = np.nanmax([rsi_pk, rsi[k]])
                if arm_d is None and h[k] / e - 1 >= ARM:
                    arm_d = d
                if arm_d is None:
                    continue
                row = {'tid': t['tid'], 'code': code, 'res': res, 'd': d, 'since': d - arm_d, 'rsi_drop': rsi_pk - rsi[k]}
                row.update({f: x[f].iat[k] for f in ('pctb', 'bb_revert', 'hist_slope', 'obv_slope3', 'obv_gap', 'vol3')})
                panel.append(row)
                if d + 1 < end_d:               # 다음 날 시가 청산이 기준 종료보다 빨라야 발동으로 인정
                    nx = o[k + 1] / e - 1 - FEE
                    fired = {'T1': x['bb_revert'].iat[k] == 1, 'T2': x['t2'].iat[k], 'T3': x['t3'].iat[k], 'T4': x['t4'].iat[k],
                             'T5': row['rsi_drop'] >= 10, 'T6': x['t6'].iat[k]}
                    for name, on in fired.items():
                        if on and name not in t:
                            t[name] = nx
            trades.append(t)
    return pd.DataFrame(trades), pd.DataFrame(panel)


def auc(fake, win):
    fake, win = fake[~np.isnan(fake)], win[~np.isnan(win)]
    if len(fake) == 0 or len(win) == 0:
        return np.nan, 0
    r = rankdata(np.concatenate([fake, win]))
    return (r[:len(fake)].sum() - len(fake) * (len(fake) + 1) / 2) / (len(fake) * len(win)), min(len(fake), len(win))


def strat_auc(p, f):
    vals, ws = [], []
    for _, g in p.groupby(p.since.clip(upper=4)):
        a, w = auc(g.loc[g.res == 'F', f].to_numpy(float), g.loc[g.res == 'W', f].to_numpy(float))
        if w:
            vals.append(a); ws.append(w)
    return np.average(vals, weights=ws) if ws else np.nan


def auc_table(p, rng, title, n=300):
    print(title)
    print(f"  (가짜 {p[p.res == 'F'].tid.nunique()}건 / 큰 승자 {p[p.res == 'W'].tid.nunique()}건, 행 {len(p)})")
    print(f"  {'지표':<24}{'가짜 중앙':>10}{'승자 중앙':>10}{'AUC':>7}{'90% 구간':>16}")
    groups = {k: g for k, g in p[p.res.isin(['F', 'W'])].groupby('code')}
    keys = list(groups)
    boots = [pd.concat([groups[k] for k in rng.choice(keys, len(keys))]) for _ in range(n)]
    for f, nm in FEATS.items():
        a = strat_auc(p, f)
        bs = [strat_auc(b, f) for b in boots]
        fm, wm = p.loc[p.res == 'F', f].median(), p.loc[p.res == 'W', f].median()
        print(f"  {nm:<24}{fm:>10.3f}{wm:>10.3f}{a:>7.3f}{np.nanpercentile(bs, 5):>9.3f}~{np.nanpercentile(bs, 95):.3f}")
    print()


def report(tr, panel):
    n = len(tr)
    print(f"신호 {n}건 / 기준 base15 매매당 {tr.base.mean() * 100:+.2f}%")
    print(f"+3% 도달 {tr.armed.sum()}건 — 큰 승자 {((tr.res == 'W') & tr.armed).sum()} / 가짜 상승 {((tr.res == 'F') & tr.armed).sum()} / 만료 {((tr.res == 'N') & tr.armed).sum()}\n")
    rng = np.random.default_rng(7)
    auc_table(panel[panel.since == 0], rng, '[A] +3% 최초 도달일 종가 시점 (이후 보유 중인 건만)')
    auc_table(panel, rng, '[B] 도달 후 보유 중 매일 (경과일 칸별 비교, 손절 직전 봉 포함이라 낙관적)')

    print('[C] 꺾임 신호를 청산 규칙으로 — 전체 신호 기준 매매당 효과')
    print(f"{'규칙':<26}{'발동':>5}{'큰승자 자름':>13}{'가짜 잡음':>10}{'자른손실':>9}{'막은손실':>9}{'정밀도/손익분기':>16}{'순효과':>9}{'90% 구간':>16}   연도별(23/24/25/26)")
    nw, nf = (tr.res == 'W').sum(), ((tr.res == 'F') & tr.armed).sum()
    codes = tr.code.to_numpy()
    base = tr.base.to_numpy()
    for r, nm in FLAGS.items():
        v = tr[r].to_numpy(float)
        fired = ~np.isnan(v)
        diff = np.where(fired, v, base) - base
        w, fk = fired & (tr.res == 'W').to_numpy(), fired & (tr.res == 'F').to_numpy()
        cut, sav = diff[w].sum(), diff[fk].sum()
        prec = fk.sum() / max(fk.sum() + w.sum(), 1)
        be = (-cut / max(w.sum(), 1)) / ((-cut / max(w.sum(), 1)) + sav / max(fk.sum(), 1)) if fk.sum() and w.sum() else np.nan
        lo, hi = boot(diff, codes, rng)
        yr = ' / '.join(f"{diff[(tr.year == y).to_numpy()].mean() * 100:+.2f}" for y in ('2023', '2024', '2025', '2026'))
        print(f"{nm:<26}{fired.sum():>5}{w.sum():>6}/{nw:<3}({w.sum() / nw * 100:>2.0f}%){fk.sum():>6}/{nf:<4}{cut / n * 100:>+8.2f}%{sav / n * 100:>+8.2f}%"
              f"{prec * 100:>8.0f}%/{be * 100:>3.0f}%{diff.mean() * 100:>+8.2f}%{lo * 100:>+8.2f}~{hi * 100:<+7.2f} {yr}")


if __name__ == '__main__':
    tr_, panel_ = evaluate()
    for r_ in FLAGS:
        if r_ not in tr_:
            tr_[r_] = np.nan
    report(tr_, panel_)
    tr_.to_pickle(os.path.join(W2, 'turn_trades.pkl'))
    panel_.to_pickle(os.path.join(W2, 'turn_panel.pkl'))
