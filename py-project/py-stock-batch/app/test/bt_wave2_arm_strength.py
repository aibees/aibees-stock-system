"""
bt_wave2_arm_strength.py — 수익 구간에 처음 닿은 날의 '힘'으로 가짜 상승을 거르는 규칙 채점.

대상·기준은 bt_wave2_fake_rise 와 동일(2파 추세선 돌파+거래량 2배↑, base15). 전체 신호로 평가한다.
발동: 고가가 처음 +X% 에 닿은 날(도달일) 종가 시점에 단 한 번 판정. 약하면 다음 날 시가 청산, 아니면 끝까지 기준대로. 도달일에 기준 청산되면 판정 없음.
약함의 정의(사전 고정)
    A1 MACD  : 히스토그램 기울기 < 0
    A2 %B    : BB %B 가 앞 구간(2022~24) 도달일 하위 1/3 이하 (문턱은 앞 구간에서만 구한다)
    A3 거래량 : 거래량 < 직전 3일 평균
    A4 복합  : A1·A2·A3 중 2개 이상
수익 상태 조건: 도달일 종가 수익 > 0 인 경우만 발동. (+3% 는 조건 없는 판도 함께 본다)
합격 기준(사전 고정): 큰 승자 자름 ≤ 10%, 순효과 > 0, 앞(2022~24)·뒤(2025~26) 모두 > 0, 실전 규칙 대비도 ≥ 0.
실전 규칙 대비: exits.pkl 의 live8(-8%, +30%, 트레일, 타임스탑)에 같은 청산을 덧씌운 차이. 청산일이 live8 종료 전일 때만 적용.

사용
    poetry run python -m app.test.bt_wave2_arm_strength
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_fake_rise import CACHE, FEE, H, base_path, boot
from app.test.bt_wave2_trendline import OUT as W2
from app.test.bt_wave2_turn_features import indicators

LEVELS = [0.03, 0.05, 0.08]
EARLY = ('2022', '2023', '2024')
RULES = {'A1': 'A1 MACD 기울기 음', 'A2': 'A2 %B 하위 1/3', 'A3': 'A3 거래량 감소', 'A4': 'A4 2개 이상'}


def evaluate():
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)]
    rows = []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
        df['datetime'] = df['datetime'].astype(str).str[:10]
        o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
        x = indicators(df)
        slope, pctb, vol3 = x['hist_slope'].to_numpy(), x['pctb'].to_numpy(), x['vol3'].to_numpy()
        idx = {d: k for k, d in enumerate(df['datetime'])}
        for s in g.itertuples():
            i = idx.get(s.date)
            if i is None or i + H + 1 >= len(c):
                continue
            e = o[i + 1]
            ret, res, end_d, _ = base_path(o, h, l, c, i, e)
            r = {'code': code, 'date': s.date, 'year': s.year, 'base': ret, 'res': res, 'end_d': end_d}
            for X in LEVELS:
                for d in range(1, end_d):
                    k = i + d
                    if h[k] / e - 1 >= X:
                        r.update({f'd_{X}': d, f'gain_{X}': c[k] / e - 1, f'exit_{X}': o[k + 1] / e - 1 - FEE,
                                  f'slope_{X}': slope[k], f'pctb_{X}': pctb[k], f'vol3_{X}': vol3[k]})
                        break
            rows.append(r)
    tr = pd.DataFrame(rows)
    live = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8', 'live8_d']]
    tr = tr.merge(live, on=['code', 'date'], how='left')
    tr.to_pickle(os.path.join(W2, 'arm_strength.pkl'))
    return tr


def line(lab, tr, fired, X, rng):
    n, nw = len(tr), (tr.res == 'W').sum()
    base = tr.base.to_numpy()
    ex = tr[f'exit_{X}'].to_numpy(float)
    diff = np.where(fired, ex, base) - base
    w = fired & (tr.res == 'W').to_numpy()
    f = fired & (tr.res == 'F').to_numpy()
    early = tr.year.isin(EARLY).to_numpy()
    lo, hi = boot(diff, tr.code.to_numpy(), rng, n=500)
    lv = tr.live8.to_numpy(float)
    use = fired & ~np.isnan(lv) & (tr[f'd_{X}'].to_numpy(float) + 1 < tr.live8_d.to_numpy(float))
    dl = np.where(use, ex, lv) - lv
    ok = (w.sum() / nw <= .10) and diff.mean() > 0 and diff[early].mean() > 0 and diff[~early].mean() > 0 and np.nanmean(dl) >= 0
    print(f"{lab:<22}{fired.sum():>5}{w.sum():>5}/{nw:<3}({w.sum() / nw * 100:>3.0f}%){f.sum():>5}/{(tr.res == 'F').sum():<4}"
          f"{np.nanmean(ex[fired]) * 100 if fired.any() else float('nan'):>+7.1f}%{diff.mean() * 100:>+8.2f}%p{lo * 100:>+7.2f}~{hi * 100:<+6.2f}"
          f"{diff[early].mean() * 100:>+7.2f}{diff[~early].mean() * 100:>+7.2f}{np.nanmean(dl) * 100:>+9.2f}%p  {'합격' if ok else '-'}")


def report(tr):
    rng = np.random.default_rng(7)
    early = tr.year.isin(EARLY).to_numpy()
    print(f"신호 {len(tr)}건 / 기준 매매당 {tr.base.mean() * 100:+.2f}% / 실전 규칙(live8) {tr.live8.mean() * 100:+.2f}% / 큰 승자 {(tr.res == 'W').sum()}건 / 앞 {early.sum()}·뒤 {(~early).sum()}\n")
    head = f"{'':<22}{'발동':>5}{'큰승자 자름':>13}{'손절 잡음':>10}{'청산가':>8}{'순효과':>10}{'90% 구간':>15}{'앞':>7}{'뒤':>7}{'실전규칙 대비':>11}"
    for X, gate in [(0.03, False), (0.03, True), (0.05, True), (0.08, True)]:
        has = tr[f'd_{X}'].notna().to_numpy()
        cut = np.nanpercentile(tr.loc[early & has, f'pctb_{X}'], 100 / 3)
        print(f"[도달 +{X * 100:.0f}%{' · 도달일 종가 수익>0' if gate else ' · 수익 조건 없음'}] 도달 후 보유 {has.sum()}건, %B 문턱 {cut:.2f}\n{head}")
        a1 = tr[f'slope_{X}'].to_numpy(float) < 0
        a2 = tr[f'pctb_{X}'].to_numpy(float) <= cut
        a3 = tr[f'vol3_{X}'].to_numpy(float) < 1
        cond = {'A1': a1, 'A2': a2, 'A3': a3, 'A4': a1.astype(int) + a2.astype(int) + a3.astype(int) >= 2}
        g = tr[f'gain_{X}'].to_numpy(float) > 0 if gate else True
        for k, lab in RULES.items():
            line(lab, tr, has & cond[k] & g, X, rng)
        print()


if __name__ == '__main__':
    report(evaluate())
