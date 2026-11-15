"""
bt_private_30m_basic.py — 실전(PRIVATE) 후보 연구 ④: 기본(BASIC) 알고리즘의 기계식 점수·조건을 30분봉에 적용해 고급 후보 1위 고르기.

배경(2026-11-14 사용자 제안): 일봉으로 걸러진 2파 후보 안에서, 기본 알고리즘처럼 지표 조건·점수를 30분봉에 매겨
가장 높은 종목을 1위로.

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다)
    데이터  : 신호일 D 포함 직전 20거래일 1분봉 → 30분봉(하루 13개, 15:30 단일가는 마지막 봉에 합침), 15일 미만 제외.
              지표는 배치와 같은 KisService.compute_indicator_df(이평은 20·60·120 '봉'), 이후 fillna(0) — 배치와 같음.
    눈금    : ATR·고점 대비 눌림 기준은 일봉용이라 30분봉에선 1/√13 로 줄인다(가격 변동 ∝ √시간).
              ATR 하한 5% → 1.39%, 점수 ATR 구간 5~12% → 1.39~3.33%, 눌림 구간 3~15% → 0.83~4.16%.
    점수    : 모두 D 의 마지막 30분봉(장 마감 상태) 기준
        S_tech : scoring.tech_score — MACD 기울기 상승 0.30 · BB 중심선 돌파 0.15 · 거래량 하한 0.20(기본 단계와 같이 항상 통과) ·
                 ATR 0.20 · 고점 대비 눌림 0.15. (재무·유동성 점수는 30분봉과 무관해 뺀다)
        S_cnt  : basic_reco 기술 조건 12개 중 만족 개수 — MACD 상승, OBV 상승, 처음 켜짐(직전 봉엔 둘 다 상승 아님),
                 RSI<70, 종가<=BB 상단, 소진 아님, 20봉선 상승, 종가>20봉선, 저가>120봉선, ATR/종가>=1.39%,
                 거래량>=20봉 평균×0.8, 거래량>=직전 봉×2
        S_day  : D 의 30분봉 13개 중 S_cnt 최댓값(그날 가장 좋았던 순간)
    순위    : 점수 큰 순(같으면 일봉 거래량 배수) vs 지금 순위(일봉 거래량 배수 큰 순)
평가: D+1 시가 매수, +15%/-8%/10일(ret15), 실전 매도 규칙(live8). 고급 = shape 백분위 >= 0.6.
한계: 약 1년·200여 건, 같은 날 후보 2개 이상은 40~65일뿐, 마지막 봉은 단일가 거래량이 섞여 거래량 조건이 잘 켜진다
      (모든 종목이 같은 조건이라 순위 비교에는 영향이 작다), 슬리피지 없음.

사용
    poetry run python -m app.test.bt_private_30m_basic
"""
import math
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService  # noqa: E402
from app.test.bt_wave2_trendline import CACHE, OUT as W2  # noqa: E402
from app.test.bt_private_30m import MIN_DIR, FROM, shape_pct  # noqa: E402
from app.test.bt_private_intraday import day_bars, DAYS, MIN_DAYS  # noqa: E402
from app.test.eval_shape_proba import _base_user_info  # noqa: E402
from stock_shared.ml.shape_features import is_exhaustion_risk  # noqa: E402
from stock_shared.strategy import scoring  # noqa: E402

FREQ = 30
K = 1 / math.sqrt(390 / FREQ)                      # 1/√13
ATR_MIN, ATR_LO, ATR_HI = 0.05 * K, 0.05 * K, 0.12 * K
DIP_LO, DIP_HI = 0.03 * K, 0.15 * K


def conds(t, y, yy, detail: bool = False):
    """기본 조건 12개 중 만족 개수. detail=True 면 조건별 참/거짓 목록."""
    f = lambda r, k: float(r.get(k) or 0.0)  # noqa: E731
    up_t = f(t, 'macd') > f(y, 'macd') and f(t, 'obv') > f(y, 'obv')
    up_y = f(y, 'macd') > f(yy, 'macd') and f(y, 'obv') > f(yy, 'obv')
    close, low, vol = f(t, 'close'), f(t, 'low'), f(t, 'volume')
    ma20, ma20p, ma120 = f(t, 'ema20'), f(y, 'ema20'), f(t, 'ema120')
    c = [
        f(t, 'macd') > f(y, 'macd'),
        f(t, 'obv') > f(y, 'obv'),
        up_t and not up_y,
        f(t, 'rsi') < 70,
        0 < close <= f(t, 'bb_upper'),
        not is_exhaustion_risk(t.get('shape_bars_since_min'), t.get('shape_total_ret_14'), t.get('shape_ret_1d_today')),
        ma20 > 0 and ma20p > 0 and ma20 > ma20p,
        ma20 > 0 and close > ma20,
        ma120 > 0 and low > ma120,
        close > 0 and f(t, 'atr') / close >= ATR_MIN,
        f(t, 'vol_avg') > 0 and vol >= f(t, 'vol_avg') * 0.8,
        f(y, 'volume') > 0 and vol >= f(y, 'volume') * 2,
    ]
    return [bool(x) for x in c] if detail else int(sum(bool(x) for x in c))


def tech(t, y) -> float:
    f = lambda r, k: float(r.get(k) or 0.0)  # noqa: E731
    close, rh = f(t, 'close'), f(t, 'recent_high')
    ind = {'macd_slope_up': 'Y' if f(t, 'macd') > f(y, 'macd') else 'N',
           'is_bb_mid_breakout': 'Y' if f(t, 'bb_mid_breakout') > 0 else 'N',
           'is_vol_limit': 'Y',
           'atr_ratio': f(t, 'atr') / close if close else 0.0,
           'dip_from_high': (close - rh) / rh if rh > 0 else 0.0}
    return scoring.tech_score(ind, atr_lo=ATR_LO, atr_hi=ATR_HI, dip_lo=DIP_LO, dip_hi=DIP_HI)


def one(args):
    code, sigs = args
    df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
    dates = df['datetime'].astype(str).str[:10].tolist()
    idx = {d: k for k, d in enumerate(dates)}
    ks, ui, rows = KisService(), _base_user_info(), []
    for d in sigs:
        i = idx.get(d)
        if i is None or i < DAYS:
            continue
        parts = [b for b in (day_bars(code, x, FREQ) for x in dates[i - DAYS + 1:i + 1]) if b is not None]
        if len(parts) < MIN_DAYS or parts[-1].day.iloc[0] != d:
            continue
        b = pd.concat(parts)
        b['datetime'] = [f"{dd} {9 + (k * FREQ) // 60:02d}:{(k * FREQ) % 60:02d}:00" for dd, k in zip(b.day, b.index)]
        b = b.reset_index(drop=True)[['datetime', 'open', 'high', 'low', 'close', 'volume']]
        comp = ks.compute_indicator_df(b.copy(), user_info=ui).fillna(0.0)
        recs = comp.to_dict('records')
        on_d = [k for k, r in enumerate(recs) if r['datetime'].startswith(d) and k >= 2]
        if not on_d:
            continue
        cnts = [conds(recs[k], recs[k - 1], recs[k - 2]) for k in on_d]
        last = len(recs) - 1
        rows.append({'code': code, 'date': d, 's_tech': tech(recs[last], recs[last - 1]),
                     's_cnt': conds(recs[last], recs[last - 1], recs[last - 2]), 's_day': max(cnts),
                     'full_any': max(cnts) == 12})
    return rows


def boot(s, a, b, col):
    rng = np.random.default_rng(7)
    by = {k: v for k, v in s.groupby('code')}
    ks = list(by)
    out = []
    for _ in range(1000):
        x = pd.concat([by[k] for k in rng.choice(ks, len(ks))])
        out.append(x[x._g == a][col].mean() - x[x._g == b][col].mean())
    return np.nanpercentile(out, 5) * 100, np.nanpercentile(out, 95) * 100


def report(r):
    for scope, s0 in (('고급(shape 백분위 >= 0.6)', r[r.pct >= 0.6]), ('2파 신호 전체', r)):
        print(f"\n━━ {scope}: {len(s0)}건 · 같은 날 2건↑ {(s0.groupby('date').size() >= 2).sum()}일 · "
              f"전체 매매당 {s0.ret15.mean() * 100:+.2f}% 실전 {s0.live8.mean() * 100:+.2f}%")
        for col, lab in (('s_tech', '기술 점수(tech_score)'), ('s_cnt', '조건 만족 개수(마감 봉)'), ('s_day', '조건 만족 개수(그날 최고)')):
            s = s0.copy()
            s['_g'] = pd.qcut(s[col].rank(method='first'), 3, labels=['하', '중', '상']).astype(str)
            parts = ' · '.join(f"{g}({s[s._g == g][col].min():.2f}~{s[s._g == g][col].max():.2f}) {s[s._g == g].ret15.mean() * 100:+.2f}%/실전 {s[s._g == g].live8.mean() * 100:+.2f}%"
                               for g in ('하', '중', '상'))
            lo, hi = boot(s, '상', '하', 'ret15')
            lo8, hi8 = boot(s.dropna(subset=['live8']), '상', '하', 'live8')
            d = s[s._g == '상'].ret15.mean() - s[s._g == '하'].ret15.mean()
            d8 = s[s._g == '상'].live8.mean() - s[s._g == '하'].live8.mean()
            print(f" [{lab}] 3등분 {parts}")
            print(f"   상-하: 매매당 {d * 100:+.2f}%p [90% {lo:+.2f}~{hi:+.2f}] · 실전 {d8 * 100:+.2f}%p [90% {lo8:+.2f}~{hi8:+.2f}]")
            m = s.groupby('date').filter(lambda g: len(g) >= 2)
            if len(m):
                now = m.loc[m.groupby('date').vol_ratio.idxmax()]
                m = m.assign(_k=list(zip(m[col], m.vol_ratio)))
                new = m.loc[m.groupby('date')._k.apply(lambda z: z.idxmax())]
                same = (now.set_index('date').code == new.set_index('date').code).mean()
                print(f"   같은 날 2건↑ {m.date.nunique()}일: 지금 1위 {now.ret15.mean() * 100:+.2f}%/실전 {now.live8.mean() * 100:+.2f}% · "
                      f"점수 1위 {new.ret15.mean() * 100:+.2f}%/실전 {new.live8.mean() * 100:+.2f}% (1위 같은 날 {same * 100:.0f}%)")
        y = s0[s0.full_any]
        print(f" [그날 30분봉 중 12개 조건 전부 통과한 봉이 있음] n={len(y)} 매매당 {y.ret15.mean() * 100:+.2f}% 실전 {y.live8.mean() * 100:+.2f}%")


if __name__ == '__main__':
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2) & (ev.date >= FROM)]
    ex = pd.read_pickle(os.path.join(W2, 'exits.pkl'))[['code', 'date', 'live8']]
    have = set(os.listdir(MIN_DIR))
    jobs = [(code, list(g.date)) for code, g in ev.groupby('code') if code in have]
    with Pool(8) as p:
        rows = [x for part in p.map(one, jobs) for x in part]
    r = pd.DataFrame(rows).merge(ev[['code', 'date', 'vol_ratio', 'ret15', 'res15']], on=['code', 'date'])
    r = r.merge(ex, on=['code', 'date'], how='left').merge(shape_pct(set(r.date)), on=['code', 'date'], how='left')
    print(f"2파 신호 {len(ev)}건 중 분봉 {MIN_DAYS}일 이상 {len(r)}건 · 30분봉 눈금 1/√13 = {K:.3f}")
    r.to_pickle(os.path.join(CACHE, 'private', 'basic30_scores.pkl'))
    print(r[['s_tech', 's_cnt', 's_day']].describe().round(2).to_string())
    report(r)
