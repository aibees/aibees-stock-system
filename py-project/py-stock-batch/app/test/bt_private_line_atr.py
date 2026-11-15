"""
bt_private_line_atr.py — 실전(PRIVATE) 후보 연구 ③: 라인 반등을 ATR 폭으로 보고, 청산을 여러 방식으로, 시장 전환과 묶어서.

배경(2026-11-14 사용자):
  - 반등 타점을 라인에 딱 맞추는 게 아니라 ATR 범위 안에서 봐야 한다.
  - 수익이 무조건 +15% 가 정답이 아닐 수 있다.
  - 앞 실험(bt_private_line_rebound)에서 이번 주 사례가 10/27 실패 반등과 11/09 성공 반등을 똑같이 신호로 냈다.
    차이는 시장 전체가 같이 돌았느냐 → 시장 전환 조건을 붙여 본다.

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다)
    반등 신호 : bt_private_line_rebound.scan 과 같음(20봉 최저가 j, 직전 20봉 고점 대비 -15%↓, 5봉 안 저점 안 깨고
                종가 > j 고가 양봉). ATR = ATR14(j).
    라인      : 피보나치 스윙/큰 구간 되돌림(0.382~1.0), 장기 전저점(60~500봉 전 최저가), 120·240일선.
                j 저가와 라인의 거리가 ATR × k 이내면 닿음. k = 0.5(주) / 1.0(참고).
                피보나치 '라인 사이' = 깊이 0.35~1.03 안이지만 어느 라인과도 ATR × k 밖.
    시장 전환 : 그날 필터 통과 종목 중 종가 > 20일선 비율(breadth).
                M1 = 최근 10일 최저 <= 20% 이고 오늘 - 그 최저 >= 15%p (바닥 찍고 급증)
                M2 = 오늘 - 5일 전 >= 10%p 이고 최근 10일 최저 <= 30% (참고)
                시장 약세·전환 없음 = 최근 10일 최저 <= 20% 인데 M1 아님.
매매 — D+1 시가 매수, 수수료 0.22%. 손절 S = j 저가 - ATR (고정 -8% 행만 예외). 시가 <= S 면 매수 안 함.
    고정 +15/-8/10일(앞 실험들과 같음, 같은 날 기준 비교용)
    % 익절  : +8 / +10 / +15 / +20 / +30%, 20일
    ATR 익절: 매수가 + 2 / 3 / 4 / 6 ATR, 20일
    낙폭 회복: j 앞 60봉 고점에서 j 저가까지 낙폭의 0.382 / 0.5 / 0.618 회복 가격, 30일(매수가가 이미 넘었으면 제외)
    추적    : 최고가 - 2 / 3 ATR 추적 손절(처음엔 S), 40일
    기간    : 익절 없이 5 / 10 / 20일 보유(손절 S 는 유지)
    지표: 매매당 평균, 이긴 비율, 평균 보유일, 보유일당 수익(= 매매당 / 보유일). 워커는 한 번에 한 종목이라 보유일당이 중요.
필터: 종가 >= 1,000원, 20일 평균 거래대금 >= 5억, 시총 >= 1,000억, 보통주, 관리·정지(현재) 제외, 250봉 이상.
한계: 현재 상장 종목만, 슬리피지 없음, 같은 봉에 손절·익절 둘 다 닿으면 손절, 청산 방식을 많이 비교하므로
      가장 좋은 하나는 우연히 좋게 나올 수 있음(여러 번 비교한 것). 시장 전환 사건은 4년에 14번뿐.

사용
    poetry run python -m app.test.bt_private_line_atr --sameday <같은날 기준 pkl>
    poetry run python -m app.test.bt_private_line_atr --sameday <pkl> --report-only
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, FEE, WARMUP, MIN_PRICE, MIN_AMOUNT, MIN_CAP  # noqa: E402
from app.test.bt_private_line_rebound import zigzag, swing_leg, scan, LEVELS, CRASH, _ci, _diff_ci  # noqa: E402

OUT = os.path.join(CACHE, 'private')
_G = {}

EXITS = [
    ('fix15', '고정 +15/-8/10일', dict(stop_pct=0.08, tgt_pct=0.15, H=10)),
    ('p8', '+8% 익절', dict(tgt_pct=0.08, H=20)),
    ('p10', '+10% 익절', dict(tgt_pct=0.10, H=20)),
    ('p15', '+15% 익절', dict(tgt_pct=0.15, H=20)),
    ('p20', '+20% 익절', dict(tgt_pct=0.20, H=20)),
    ('p30', '+30% 익절', dict(tgt_pct=0.30, H=20)),
    ('a2', '+2ATR 익절', dict(tgt_atr=2, H=20)),
    ('a3', '+3ATR 익절', dict(tgt_atr=3, H=20)),
    ('a4', '+4ATR 익절', dict(tgt_atr=4, H=20)),
    ('a6', '+6ATR 익절', dict(tgt_atr=6, H=20)),
    ('f382', '낙폭 0.382 회복', dict(tgt_fib=0.382, H=30)),
    ('f500', '낙폭 0.5 회복', dict(tgt_fib=0.5, H=30)),
    ('f618', '낙폭 0.618 회복', dict(tgt_fib=0.618, H=30)),
    ('t2', '추적 2ATR', dict(trail=2, H=40)),
    ('t3', '추적 3ATR', dict(trail=3, H=40)),
    ('h5', '5일 보유', dict(H=5)),
    ('h10', '10일 보유', dict(H=10)),
    ('h20', '20일 보유', dict(H=20)),
]


def _init(meta):
    _G.update(meta)


def sim(o, h, l, c, a, i, S, lj, hd, stop_pct=None, tgt_pct=None, tgt_atr=None, tgt_fib=None, trail=None, H=20):
    """(수익, 보유일) 또는 None. 진입 = o[i+1]."""
    e = o[i + 1]
    st = e * (1 - stop_pct) if stop_pct else S
    if e <= st:
        return None
    tgt = None
    if tgt_pct:
        tgt = e * (1 + tgt_pct)
    elif tgt_atr:
        tgt = e + tgt_atr * a[i]
    elif tgt_fib:
        tgt = lj + tgt_fib * (hd - lj)
        if tgt <= e:
            return None
    hh = e
    for k in range(i + 1, i + H + 1):
        if l[k] <= st:
            px = st if (k == i + 1 or o[k] > st) else o[k]
            return px / e - 1 - FEE, k - i
        if tgt is not None and h[k] >= tgt:
            px = tgt if (k == i + 1 or o[k] < tgt) else o[k]
            return px / e - 1 - FEE, k - i
        if trail:
            hh = max(hh, h[k])
            st = max(st, hh - trail * a[k])
    return c[i + H] / e - 1 - FEE, H


def _datr(price, lines, atr):
    lines = [x for x in lines if x == x and x > 0]
    return min(abs(price - x) for x in lines) / atr if lines and atr > 0 else np.nan


def events_from_df(df, code, ok):
    from stock_shared.chart_analysis.indicators import atr as atr_fn
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    n = len(c)
    dates = df['datetime'].astype(str).str[:10].tolist()
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    piv = zigzag(h, l, a)
    ma120 = pd.Series(c).rolling(120).mean().to_numpy()
    ma240 = pd.Series(c).rolling(240).mean().to_numpy()
    v20 = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    ev = []
    for i, j in scan(o, h, l, c, v):
        if not ok[i] or a[j] <= 0:
            continue
        lj, aj = l[j], a[j]
        hd = h[max(0, j - 60):j + 1].max()
        d = {'code': code, 'date': dates[i], 'year': dates[i][:4], 'jd': dates[j], 'dd': lj / h[max(0, j - 250):j + 1].max() - 1,
             'vr': v[i] / v20[i] if v20[i] > 0 else np.nan, 'dist_atr': (c[i] - lj) / aj, 'atr_pct': aj / c[i]}
        d['sw_depth'] = d['sw_datr'] = np.nan
        leg = swing_leg(piv, j, i)
        if leg is not None and j - leg[2] >= 3 and l[leg[2] + 1:j].min(initial=np.inf) >= lj and leg[1] > leg[0]:
            L0, H1, _ = leg
            d['sw_depth'] = (H1 - lj) / (H1 - L0)
            d['sw_datr'] = _datr(lj, [H1 - r * (H1 - L0) for r in LEVELS], aj)
        d['mj_depth'] = d['mj_datr'] = np.nan
        w0 = max(0, j - 120)
        iH = w0 + int(np.argmax(h[w0:j + 1]))
        if iH < j and l[iH:j].min(initial=np.inf) >= lj:
            v0 = max(0, iH - 250)
            iL = v0 + int(np.argmin(l[v0:iH + 1]))
            if iL < iH and h[iH] / l[iL] >= 1.2:
                d['mj_depth'] = (h[iH] - lj) / (h[iH] - l[iL])
                d['mj_datr'] = _datr(lj, [h[iH] - r * (h[iH] - l[iL]) for r in LEVELS], aj)
        d['pl_datr'] = _datr(lj, [l[j - 500:j - 60].min()], aj) if j >= 560 else np.nan
        d['m120_datr'] = _datr(lj, [ma120[j]], aj)
        d['m240_datr'] = _datr(lj, [ma240[j]], aj)
        if i + 41 < n:
            S = lj - aj
            for key, _, kw in EXITS:
                t = sim(o, h, l, c, a, i, S, lj, hd, **kw)
                d['r_' + key], d['d_' + key] = t if t else (np.nan, np.nan)
        ev.append(d)
    return ev


def run_stock(path):
    code = os.path.basename(path)[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return []
    df = pd.read_pickle(path).reset_index(drop=True)
    n = len(df)
    if n < WARMUP + 45:
        return []
    c, v = df['close'].to_numpy(float), df['volume'].to_numpy(float)
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    idx = np.arange(n)
    ok = (idx >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (c * _G['shares'][code] >= MIN_CAP) & (idx < n - 41)
    return events_from_df(df, code, ok)


def run():
    from sqlalchemy import create_engine
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')
                       | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(x) for k, x in zip(ms.stock_code, ms.listed_shares) if x}, 'bad': bad}
    paths = sorted(os.path.join(CACHE, 'stocks', x) for x in os.listdir(os.path.join(CACHE, 'stocks')))
    ev = []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for k, e in enumerate(pool.imap_unordered(run_stock, paths, chunksize=8), 1):
            ev += e
            if k % 500 == 0:
                print(f"[scan] {k}/{len(paths)} · 신호 {len(ev)}", flush=True)
    ev = pd.DataFrame(ev)
    ev.to_pickle(os.path.join(OUT, 'line_atr_events.pkl'))
    return ev


def market_flags(breadth):
    s = breadth.sort_index()
    m10 = s.rolling(10).min()
    return pd.DataFrame({'b': s, 'm10': m10,
                         'M1': (m10 <= 0.20) & (s - m10 >= 0.15),
                         'M2': (s - s.shift(5) >= 0.10) & (m10 <= 0.30),
                         'weak': (m10 <= 0.20) & ~((m10 <= 0.20) & (s - m10 >= 0.15))})


def add_flags(ev, k):
    for f in ('sw', 'mj', 'pl', 'm120', 'm240'):
        ev[f'{f}_on'] = ev[f'{f}_datr'] <= k
    ev['sw_off'] = ev.sw_depth.between(0.35, 1.03) & ~ev.sw_on
    ev['mj_off'] = ev.mj_depth.between(0.35, 1.03) & ~ev.mj_on
    ev['line'] = ev.sw_on | ev.mj_on | ev.pl_on | ev.m120_on | ev.m240_on
    return ev


def eps(dates):
    d = pd.to_datetime(pd.Series(sorted(set(dates))))
    return int(((d.diff().dt.days.fillna(99)) > 14).sum()) if len(d) else 0


def summary(lab, g, days):
    if len(g) < 15:
        print(f"  {lab:<30}{len(g):>6}  (표본 부족)")
        return
    x = (g.r_fix15 - g.base).dropna()
    lo, hi = _ci(x, g.loc[x.index, 'code'], 500)
    yr = '/'.join(f"{g[g.year == y].r_fix15.mean() * 100:+.1f}" if (g.year == y).sum() >= 5 else ' - ' for y in ('2023', '2024', '2025', '2026'))
    print(f"  {lab:<30}{len(g):>6}{g.date.nunique():>6}{eps(g.date):>5}{x.mean() * 100:>+9.2f}%p [{lo:+.2f}~{hi:+.2f}]  {yr:<22}"
          f"{g.r_p15.mean() * 100:>+7.2f}%{g.r_t3.mean() * 100:>+7.2f}%{g.r_h10.mean() * 100:>+7.2f}%")


def report(ev, sameday, breadth):
    ev = ev[ev.date.isin(sameday.index) & ev.r_fix15.notna()].copy()
    ev['base'] = sameday.loc[ev.date].values
    mf = market_flags(breadth)
    for col in ('b', 'M1', 'M2', 'weak'):
        ev[col] = ev.date.map(mf[col])
    ev['crash'] = ev.dd <= CRASH
    days = len(sameday)
    print(f"반등 신호 {len(ev):,}건 ({ev.date.min()}~{ev.date.max()}) · 같은날대비 = 고정 +15/-8/10일 기준, 필터 통과 전 종목 평균 대비")
    print(f"시장 전환 M1 {int(mf.M1.sum())}일({eps(mf.index[mf.M1])}번) · M2 {int(mf.M2.sum())}일({eps(mf.index[mf.M2])}번)")
    head = (f"  {'구분':<30}{'n':>6}{'날수':>6}{'사건':>5}{'같은날대비':>10}  90% 구간      연도별 고정(23/24/25/26)  "
            f"{'+15%':>7}{'추적3ATR':>7}{'10일':>7}")
    for k in (0.5, 1.0):
        add_flags(ev, k)
        print(f"\n[1] 라인 = ATR × {k} 이내 (라인 닿음 {ev.line.mean() * 100:.0f}%)  — 오른쪽 세 칸은 손절 = 저점 - ATR 의 매매당\n" + head)
        for lab, m in (('전체 반등 신호', ev.code.notna()), ('라인 닿음', ev.line), ('라인 없음', ~ev.line),
                       ('fib_swing 라인 위', ev.sw_on), ('fib_swing 라인 사이', ev.sw_off),
                       ('fib_major 라인 위', ev.mj_on), ('fib_major 라인 사이', ev.mj_off),
                       ('장기 전저점', ev.pl_on), ('120일선', ev.m120_on), ('240일선', ev.m240_on)):
            summary(lab, ev[m], days)
        for fam in ('sw', 'mj'):
            a_, b_ = ev[ev[fam + '_on']], ev[ev[fam + '_off']]
            A = a_.r_fix15 - a_.base; A.index = a_.code
            B = b_.r_fix15 - b_.base; B.index = b_.code
            lo, hi = _diff_ci(A, B, 300)
            print(f"  {fam} 라인 위 − 사이: {(A.mean() - B.mean()) * 100:+.2f}%p [{lo:+.2f}~{hi:+.2f}]")

    add_flags(ev, 0.5)
    print("\n[2] 시장 상태 × 라인(ATR × 0.5) × 반등일 거래량\n" + head)
    groups = [
        ('시장 전환 M1', ev.M1), ('  M1 · 라인 닿음', ev.M1 & ev.line), ('  M1 · 라인 없음', ev.M1 & ~ev.line),
        ('  M1 · 거래량 1배↑', ev.M1 & (ev.vr >= 1)), ('  M1 · 라인 · 거래량 1배↑', ev.M1 & ev.line & (ev.vr >= 1)),
        ('  M1 · 폭락 맥락', ev.M1 & ev.crash),
        ('시장 약세·전환 없음', ev.weak), ('  약세 · 라인 닿음', ev.weak & ev.line), ('  약세 · 거래량 1배↑', ev.weak & (ev.vr >= 1)),
        ('평시(최근 10일 최저 > 20%)', ~ev.M1 & ~ev.weak), ('  평시 · 라인 · 거래량 1배↑', ~ev.M1 & ~ev.weak & ev.line & (ev.vr >= 1)),
        ('참고 M2', ev.M2), ('  M2 · 라인 닿음', ev.M2 & ev.line), ('  M2 · 거래량 1배↑', ev.M2 & (ev.vr >= 1)),
    ]
    for lab, m in groups:
        summary(lab, ev[m], days)
    print("  M1 사건별(14번) 고정 +15/-8 매매당 — 사건 하나에 몰렸는지:")
    x = ev[ev.M1].copy()
    dd = pd.to_datetime(pd.Series(sorted(x.date.unique())))
    epi = dict(zip(dd.dt.strftime('%Y-%m-%d'), ((dd.diff().dt.days.fillna(99)) > 14).cumsum()))
    x['ep'] = x.date.map(epi)
    print('   ' + ' · '.join(f"{g.date.min()[2:7]} n={len(g)} {g.r_fix15.mean() * 100:+.1f}%" for _, g in x.groupby('ep')))

    print("\n[3] 진입 거리 = 신호일 종가가 저점에서 몇 ATR 위인가 (라인 닿음만)\n" + head)
    x = ev[ev.line]
    for lab, m in (('1 ATR 이내', x.dist_atr <= 1), ('1~2 ATR', (x.dist_atr > 1) & (x.dist_atr <= 2)),
                   ('2~3 ATR', (x.dist_atr > 2) & (x.dist_atr <= 3)), ('3 ATR 초과', x.dist_atr > 3)):
        summary(lab, x[m], days)

    print("\n[4] 청산 방식 비교 — 매매당 / 이긴 비율 / 평균 보유일 / 보유일당 (손절 = 저점 - ATR, '고정'만 -8%)")
    cols = [('전체', ev.code.notna()), ('라인 닿음', ev.line), ('라인·거래량1배↑', ev.line & (ev.vr >= 1)),
            ('M1 전환', ev.M1), ('M1·거래량1배↑', ev.M1 & (ev.vr >= 1))]
    print(f"  {'청산':<16}" + ''.join(f"{c:>30}" for c, _ in cols))
    for key, lab, _ in EXITS:
        row = []
        for _, m in cols:
            g = ev[m]
            r, dd_ = g['r_' + key].dropna(), g['d_' + key].dropna()
            row.append(f"{r.mean() * 100:+6.2f}% {(r > 0).mean() * 100:3.0f}% {dd_.mean():4.1f}일 {r.mean() / dd_.mean() * 100:+.3f}%" if len(r) >= 15 else ' ' * 26 + '표본부족')
        print(f"  {lab:<16}" + ''.join(f"{s:>30}" for s in row))
    n_all = ev.code.notna().sum()
    print(f"  (낙폭 회복 익절은 매수가가 이미 목표를 넘은 건 제외: 0.382 {ev.r_f382.notna().sum() / n_all * 100:.0f}% · "
          f"0.5 {ev.r_f500.notna().sum() / n_all * 100:.0f}% · 0.618 {ev.r_f618.notna().sum() / n_all * 100:.0f}% 남음)")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--sameday', required=True)
    args = ap.parse_args()
    sd = pd.read_pickle(args.sameday).set_index('date')['mean']
    br = pd.read_pickle(os.path.join(OUT, 'breadth.pkl'))
    ev = pd.read_pickle(os.path.join(OUT, 'line_atr_events.pkl')) if args.report_only else run()
    report(ev, sd, br)
