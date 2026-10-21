"""
bt_wave2_exits.py — 2파 하락 추세선 돌파 + 거래량 2배↑ 매수(bt_wave2_trendline) 에 매도 방식을 바꿔 붙였을 때 수익.

매수: D+1 시가(신호 고정). 매도 기준가는 전부 매수 시점에 알 수 있는 값(L0·H1·2파 최저 L2·진입 ATR)으로 정한다.
    base15     : +15% 익절 / -8% 손절 / 10거래일(프로젝트 기준)
    live8      : 실전 규칙 근사(bt_reco_stop.sim_live, KospiStrategy1 손절 8%: +30% 익절·트레일·타임스탑)
    ew         : 엘리엇 3파 목표 = L2 + 1.618 × (H1 - L0) 익절 / L2 손절 / 40일
    ew_cap8    : 같은 목표 / 손절 = max(L2, 진입 × 0.92) / 40일
    h1_split   : 절반은 H1 에서, 나머지는 3파 목표. 손절 = max(L2, 진입 × 0.92), 절반 판 뒤 나머지 손절은 진입가(본전) / 40일
    s15_trail  : 절반은 +15%, 나머지는 고점 - 3×ATR(진입 ATR) 이탈 시. 손절 -8% / 40일
    trail      : 손절 -8%, 고점 수익 +8% 이후 고점 - 3×ATR 이탈 시 / 40일
봉 안 순서: 손절 먼저(같은 봉에 목표도 닿았으면 손절로). 갭이면 시가 체결. 트레일 라인은 전날까지 고점 기준.
왕복 수수료 0.22%. 수익 극대화 기준: 매매당 수익 + 보유 1일당 수익(한 종목씩 돌릴 때의 자금 효율).

사용
    poetry run python -m app.test.bt_wave2_exits
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import OUT as W2
from app.test.eval_shape_proba import _base_user_info  # noqa: F401  (sim_live 내부 사용)
from app.test.bt_reco_stop import sim_live
from stock_shared.chart_analysis.indicators import atr as atr_fn
from stock_shared.strategy.kospi1 import KospiStrategy1

CACHE = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
FEE = 0.0022
MAX_HOLD = 40
METHODS = ['base15', 'live8', 'ew', 'ew_cap8', 'h1_split', 's15_trail', 'trail']
NAMES = {'base15': '① +15%/-8%/10일(기준)', 'live8': '② 현행 실전 규칙(-8%)', 'ew': '③ 엘리엇 3파 목표/2파 저점',
         'ew_cap8': '④ 엘리엇 목표/손절 상한 -8%', 'h1_split': '⑤ H1 절반 + 3파 목표', 's15_trail': '⑥ +15% 절반 + 추세추종',
         'trail': '⑦ 추세추종만'}


def legs(o, h, l, c, i, e, plan, max_hold):
    """plan: 부분 청산 규칙 리스트를 순서대로 처리하는 단순 엔진.
    plan = dict(stop, stop_after_first, parts=[(비중, 목표가 or None)], trail_atr=None|(atr, k, activate))
    반환: (가중 수익, 보유 봉수)"""
    stop = plan['stop']
    parts = [list(p) for p in plan['parts']]
    trail = plan.get('trail')
    peak = e
    got, held, last = 0.0, 0, min(i + max_hold, len(c) - 1)
    for k in range(i + 1, last + 1):
        first = k == i + 1
        oo, hh, ll = o[k], h[k], l[k]
        # 트레일 라인(전날까지 고점 기준)
        tline = None
        if trail is not None:
            atr, mult, act = trail
            if peak / e - 1 >= act:
                tline = peak - mult * atr
        eff_stop = max(stop, tline) if tline is not None else stop
        if ll <= eff_stop:
            px = eff_stop if first else min(oo, eff_stop)
            got += sum(w for w, _ in parts) * (px / e - 1)
            return got, k - i
        for p in parts:
            w, tgt = p
            if w > 0 and tgt is not None and hh >= tgt:
                px = tgt if first else max(oo, tgt)
                got += w * (px / e - 1)
                p[0] = 0.0
                if plan.get('stop_after_first') is not None:
                    stop = max(stop, plan['stop_after_first'])
        parts = [p for p in parts if p[0] > 0]
        if not parts:
            return got, k - i
        peak = max(peak, hh)
    got += sum(w for w, _ in parts) * (c[last] / e - 1)
    return got, last - i


def evaluate():
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)].copy()
    s8 = KospiStrategy1(); s8.stop_loss_pct = 0.08
    rows = []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
        df['coin'] = code
        df['datetime'] = df['datetime'].astype(str).str[:10]
        o, h, l, c = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close'))
        a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
        idx = {d: k for k, d in enumerate(df['datetime'])}
        recs = None
        for x in g.itertuples():
            i = idx.get(x.date)
            if i is None or i + 1 >= len(c):
                continue
            e = o[i + 1]
            i1 = i - int(x.since_h1)
            p1 = h[i1]
            l2 = l[i1 + 1:i + 1].min()
            p0 = p1 - (p1 - l2) / x.retr
            w1 = p1 - p0
            t3 = l2 + 1.618 * w1
            atr_e = a[i]
            stop8 = e * 0.92
            r = {'code': code, 'date': x.date, 'year': x.year, 't3_pct': t3 / e - 1, 'l2_pct': l2 / e - 1, 'h1_pct': p1 / e - 1}

            def put(name, ret_hold):
                ret, hold = ret_hold
                r[name], r[name + '_d'] = ret - FEE, max(hold, 1)

            put('base15', legs(o, h, l, c, i, e, {'stop': stop8, 'parts': [(1.0, e * 1.15)]}, 10))
            if recs is None:
                recs = df.to_dict('records')
            t = sim_live(s8, recs, i)
            r['live8'], r['live8_d'] = (t['ret_net'], max(t['bars_held'], 1)) if t else (np.nan, np.nan)
            if l2 < e * 0.99 and t3 > e * 1.01:
                put('ew', legs(o, h, l, c, i, e, {'stop': l2, 'parts': [(1.0, t3)]}, MAX_HOLD))
            put('ew_cap8', legs(o, h, l, c, i, e, {'stop': max(l2, stop8), 'parts': [(1.0, max(t3, e * 1.01))]}, MAX_HOLD))
            first = p1 if p1 > e * 1.01 else e * 1.15
            put('h1_split', legs(o, h, l, c, i, e, {'stop': max(l2, stop8), 'stop_after_first': e,
                                                       'parts': [(0.5, first), (0.5, max(t3, first * 1.01))]}, MAX_HOLD))
            put('s15_trail', legs(o, h, l, c, i, e, {'stop': stop8, 'stop_after_first': e,
                                                        'parts': [(0.5, e * 1.15), (0.5, None)], 'trail': (atr_e, 3.0, 0.15)}, MAX_HOLD))
            put('trail', legs(o, h, l, c, i, e, {'stop': stop8, 'parts': [(1.0, None)], 'trail': (atr_e, 3.0, 0.08)}, MAX_HOLD))
            rows.append(r)
    res = pd.DataFrame(rows)
    res.to_pickle(os.path.join(W2, 'exits.pkl'))
    return res


def report(res):
    print(f"2파 하락 추세선 돌파 + 거래량 2배↑ 신호 {len(res)}건 — 매도 방식별 (매수는 모두 D+1 시가)")
    print(f"  3파 목표까지 중앙 {res.t3_pct.median() * 100:+.0f}% · 1파 고점(H1)까지 중앙 {res.h1_pct.median() * 100:+.0f}% · 2파 저점까지 중앙 {res.l2_pct.median() * 100:+.0f}%\n")
    print(f"{'매도 방식':<28}{'n':>6}{'매매당':>8}{'중앙':>8}{'수익>0':>8}{'보유일':>7}{'1일당':>8}{'최악':>8}{'하위10%':>9}   연도별 매매당(2023/24/25/26)")
    for m in METHODS:
        s = res.dropna(subset=[m])
        x, d = s[m] * 100, s[m + '_d']
        yr = ' / '.join(f"{s[s.year == y][m].mean() * 100:+.2f}" for y in ('2023', '2024', '2025', '2026'))
        print(f"{NAMES[m]:<28}{len(s):>6}{x.mean():>+7.2f}%{x.median():>+7.2f}%{(x > 0).mean() * 100:>7.0f}%{d.mean():>7.1f}"
              f"{x.mean() / d.mean():>+7.3f}%{x.min():>+7.1f}%{np.percentile(x, 10):>+8.1f}%   {yr}")
    rng = np.random.default_rng(7)
    codes = res.code.unique()
    for m in METHODS[1:]:
        s = res.dropna(subset=[m])
        dd = (s[m] - s['base15'])
        g = {k: dd[s.code == k].values for k in codes if (s.code == k).any()}
        ks = list(g)
        bs = [np.concatenate([g[k] for k in rng.choice(ks, len(ks))]).mean() for _ in range(1000)]
        print(f"  {NAMES[m]} - 기준: 매매당 {dd.mean() * 100:+.2f}%p [종목 단위 90% {np.percentile(bs, 5) * 100:+.2f}~{np.percentile(bs, 95) * 100:+.2f}]")


if __name__ == '__main__':
    report(evaluate())
