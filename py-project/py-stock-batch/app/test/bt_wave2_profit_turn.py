"""
bt_wave2_profit_turn.py — "수익 상태에서 +15% 도달 전에 꺾이면 바로 판다" 검증. 수익 수준을 고정하지 않고 칸별로 본다.

대상·기준은 bt_wave2_fake_rise 와 동일(2파 추세선 돌파+거래량 2배↑, base15, 승패는 장중 고가·저가).
발동: 보유 중 어느 날 종가 수익 ≥ X 이고 그날 꺾임 신호가 켜지면 첫 발동일에 청산. (고가 터치가 아니라 '지금 수익 상태'인지 본다)
체결: ① 다음 날 시가(기본) ② 당일 종가(장 막판 판독 근사). 다음 날 시가는 그 봉의 기준 청산보다 먼저이므로 기준 종료 봉 시가까지 허용한다.
신호: U 무조건(꺾임 판독 없음 — 그 수익 수준에서 '계속 보유'의 가치를 보여 주는 기준), T1~T6(bt_wave2_turn_features), V 거래량 1.5배 음봉.
미도달 = +15% 못 간 신호(손절+만료). 큰 승자 자름이 최우선 지표. 앞(2022~24)·뒤(2025~26) 구간 효과를 따로 본다.

사용
    poetry run python -m app.test.bt_wave2_profit_turn
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_fake_rise import CACHE, FEE, H, base_path, boot
from app.test.bt_wave2_trendline import OUT as W2
from app.test.bt_wave2_turn_features import indicators

LEVELS = [0.0, 0.03, 0.05, 0.08, 0.10, 0.12]
SIGS = {'U': 'U 무조건', 'T1': 'T1 BB 상단 복귀', 'T2': 'T2 MACD 꺾임', 'T3': 'T3 OBV 꺾임', 'T4': 'T4 OBV 데드', 'T5': 'T5 RSI -10',
        'T6': 'T6 동시 꺾임', 'V': 'V 거래량 음봉'}


def evaluate():
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)]
    rows = []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
        df['datetime'] = df['datetime'].astype(str).str[:10]
        o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
        rsi = df['rsi'].to_numpy(float)
        x = indicators(df)
        bb, t2, t3, t4, t6 = x['bb_revert'].to_numpy(), x['t2'].to_numpy(), x['t3'].to_numpy(), x['t4'].to_numpy(), x['t6'].to_numpy()
        idx = {d: k for k, d in enumerate(df['datetime'])}
        for s in g.itertuples():
            i = idx.get(s.date)
            if i is None or i + H + 1 >= len(c):
                continue
            e = o[i + 1]
            ret, res, end_d, _ = base_path(o, h, l, c, i, e)
            r = {'code': code, 'date': s.date, 'year': s.year, 'base': ret, 'res': res, 'end_d': end_d}
            rsi_pk = rsi[i]
            for d in range(1, end_d):
                k = i + d
                rsi_pk = np.nanmax([rsi_pk, rsi[k]])
                gain = c[k] / e - 1
                vavg = v[max(0, k - 20):k].mean()
                on = {'U': True, 'T1': bb[k] == 1, 'T2': t2[k], 'T3': t3[k], 'T4': t4[k], 'T5': rsi_pk - rsi[k] >= 10, 'T6': t6[k],
                      'V': c[k] < o[k] and vavg > 0 and v[k] >= 1.5 * vavg}
                for X in LEVELS:
                    if gain < X:
                        continue
                    for name, val in on.items():
                        key = f'{name}_{X:.2f}'
                        if val and key not in r:
                            r[key] = o[k + 1] / e - 1 - FEE
                            r[key + '_c'] = gain - FEE
                            r[key + '_d'] = d + 1
            rows.append(r)
    res = pd.DataFrame(rows)
    res = res.reindex(columns=list(res.columns) + [f'{n}_{X:.2f}{s}' for n in SIGS for X in LEVELS for s in ('', '_c', '_d')
                                                   if f'{n}_{X:.2f}{s}' not in res.columns])
    res.to_pickle(os.path.join(W2, 'profit_turn.pkl'))
    return res


def report(tr):
    n = len(tr)
    nw = (tr.res == 'W').sum()
    base = tr.base.to_numpy()
    codes = tr.code.to_numpy()
    early = tr.year.isin(['2022', '2023', '2024']).to_numpy()
    rng = np.random.default_rng(7)
    print(f"신호 {n}건 / 기준 매매당 {base.mean() * 100:+.2f}% / 큰 승자 {nw}건 / 앞 {early.sum()}건·뒤 {(~early).sum()}건\n")
    print(f"{'수익≥':>5} {'신호':<16}{'발동':>5}{'큰승자 자름':>12}{'미도달 잡음':>11}{'청산가':>8}{'순효과(시가)':>11}{'90% 구간':>16}{'종가체결':>9}{'앞':>8}{'뒤':>8}")
    for X in LEVELS:
        for nm, lab in SIGS.items():
            key = f'{nm}_{X:.2f}'
            v = tr[key].to_numpy(float)
            fired = ~np.isnan(v)
            diff = np.where(fired, v, base) - base
            dc = np.where(fired, tr[key + '_c'].to_numpy(float), base) - base
            w = fired & (tr.res == 'W').to_numpy()
            lo, hi = boot(diff, codes, rng, n=400)
            print(f"{X * 100:>4.0f}% {lab:<16}{fired.sum():>5}{w.sum():>6}({w.sum() / nw * 100:>3.0f}%){(fired & ~w).sum():>8}"
                  f"{np.nanmean(v) * 100:>+8.1f}%{diff.mean() * 100:>+9.2f}%p{lo * 100:>+8.2f}~{hi * 100:<+6.2f}{dc.mean() * 100:>+8.2f}%p"
                  f"{diff[early].mean() * 100:>+8.2f}{diff[~early].mean() * 100:>+8.2f}")
        print()


if __name__ == '__main__':
    report(evaluate())
