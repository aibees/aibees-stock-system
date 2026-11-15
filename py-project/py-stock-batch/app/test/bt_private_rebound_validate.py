"""
bt_private_rebound_validate.py — 반등 진입 규칙 재검증 (2026-11-14 사용자: "반등 재검증 다시해볼꺼").

앞 실험(bt_private_line_rebound, bt_private_line_atr)은 전 기간을 보고 좋은 조건을 찾았다. 그 조건이 우연인지 가린다.
DB 일봉도 2021-10 부터라 '더 이른 안 본 기간'은 없다. 그래서 세 가지로 본다.

정의 — 실행 전에 고정(결과 보고 바꾸지 않는다)
    반등 신호·라인·진입거리·폭락 맥락은 앞 두 실험과 같다(같은 scan).
      라인(원래) = 피보나치 ±0.03 · 전저점 ±3% · 120/240일선 ±2%  /  라인(ATR) = 저점과 라인 거리 ATR × 0.5 이내
      거래량 = 반등일 거래량 / 직전 20일 평균,  진입거리 = (신호일 종가 - 저점) / ATR
    매매 = D+1 시가 매수, +15% 익절 / -8% 손절 / 10일, 수수료 0.22%.  잣대 = 같은 날 필터 통과 전 종목 평균 대비 초과수익.

    ① 고정 후보(앞 실험에서 좋아 보였던 것, 지금 정의 그대로)
        R1 라인(원래) & 거래량 1~2배      R2 라인(원래) & 거래량 2배↑      R3 거래량 1배↑(라인 무관)
        R4 진입거리 2~3 ATR              R5 라인(ATR) & 거래량 1배↑ & 진입거리 2~3 ATR (처음 묶어 보는 조합)
        비교: 반등 신호 전체, 2파(추세선 돌파 + 거래량 2배)
        → 연도별(2023/24/25/26) 같은날대비. 매년 같은 방향인지.
    ② 전진 검증(사람이 고르지 않고 기계적으로): 조건 격자 360개
        라인 {무관, 원래, ATR, 라인 없음} × 거래량 {무관, <1, 1~2, 2↑, 1↑} × 진입거리 {무관, <=1, 1~2, 2~3, >3, 1~3} × 폭락 {무관, 폭락, 아님}
        시험 연도 Y = 2024, 2025, 2026: Y 이전 데이터만으로 1위 조건을 고르고(학습 200건·40일 이상), Y 에 그대로 적용.
        고르는 법 두 가지: S1 = 학습 같은날대비 평균 최대, S2 = 날짜 단위 t값 최대.
    ③ 새 데이터: 캐시 이후 DB 일봉으로 2026-08-20 ~ 2026-10-30 신호(어느 실험에도 안 쓴 기간). 10일 결과가 끝난 것만.
        11/09~11 신호는 결과가 아직 안 끝나 빠진다(10/27 실패 반등은 들어간다) → 방향만 본다.
    통과 기준(미리 정함): ② 에서 고른 조건의 시험 연도 같은날대비가 세 해 모두 > 0 이고 합친 90% 구간 하한 > 0.
한계: 현재 상장 종목만, 슬리피지 없음, ① 후보는 이미 전 기간을 보고 고른 것이라 ① 의 연도별 일관성은 약한 증거,
      ③ 은 2달 남짓(시장 국면 하나).

사용
    poetry run python -m app.test.bt_private_rebound_validate --sameday <같은날 기준 pkl>
"""
import argparse
import itertools
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, OUT as W2, outcome, WARMUP, MIN_PRICE, MIN_AMOUNT, MIN_CAP  # noqa: E402
from app.test import bt_private_line_rebound as LR  # noqa: E402
from app.test import bt_private_line_atr as LA  # noqa: E402

OUT = os.path.join(CACHE, 'private')
FRESH = ('2026-08-20', '2026-10-30')
_G = {}


def features(df):
    df = df.copy()
    df['line_orig'] = (df.sw_hit == True) | (df.mj_hit == True) | df.pl_hit.astype(bool) | df.m120_hit.astype(bool) | df.m240_hit.astype(bool)  # noqa: E712
    df['line_atr'] = (df[['sw_datr', 'mj_datr', 'pl_datr', 'm120_datr', 'm240_datr']] <= 0.5).any(axis=1)
    df['crash'] = df.dd <= LR.CRASH
    return df


LINE = {'무관': lambda d: d.code.notna(), '원래': lambda d: d.line_orig, 'ATR': lambda d: d.line_atr, '라인없음': lambda d: ~d.line_orig}
VOL = {'무관': lambda d: d.code.notna(), '<1': lambda d: d.vr < 1, '1~2': lambda d: (d.vr >= 1) & (d.vr < 2),
       '2↑': lambda d: d.vr >= 2, '1↑': lambda d: d.vr >= 1}
DIST = {'무관': lambda d: d.code.notna(), '<=1': lambda d: d.dist_atr <= 1, '1~2': lambda d: (d.dist_atr > 1) & (d.dist_atr <= 2),
        '2~3': lambda d: (d.dist_atr > 2) & (d.dist_atr <= 3), '>3': lambda d: d.dist_atr > 3,
        '1~3': lambda d: (d.dist_atr > 1) & (d.dist_atr <= 3)}
CR = {'무관': lambda d: d.code.notna(), '폭락': lambda d: d.crash, '아님': lambda d: ~d.crash}
FIXED = [
    ('반등 신호 전체', lambda d: d.code.notna()),
    ('R1 라인(원래)·거래량 1~2배', lambda d: d.line_orig & (d.vr >= 1) & (d.vr < 2)),
    ('R2 라인(원래)·거래량 2배↑', lambda d: d.line_orig & (d.vr >= 2)),
    ('R3 거래량 1배↑', lambda d: d.vr >= 1),
    ('R4 진입거리 2~3 ATR', lambda d: (d.dist_atr > 2) & (d.dist_atr <= 3)),
    ('R5 라인(ATR)·거래량1↑·2~3ATR', lambda d: d.line_atr & (d.vr >= 1) & (d.dist_atr > 2) & (d.dist_atr <= 3)),
]


def ci(x, codes, n=1000):
    if len(x) < 5:
        return np.nan, np.nan
    return LR._ci(pd.Series(np.asarray(x)), pd.Series(np.asarray(codes)), n)


def tstat(g):
    by = g.groupby('date').ex.mean()
    return by.mean() / (by.std() / np.sqrt(len(by))) if len(by) > 2 and by.std() > 0 else -np.inf


# ── ③ 새 데이터: DB 일봉으로 신호·같은 날 기준·2파 ─────────────────────────────
def _init(meta):
    _G.update(meta)


def fresh_stock(args):
    from stock_shared.chart_analysis.indicators import atr as atr_fn
    from stock_shared.strategy.wave2_breakout import scan as w2scan
    code, df = args
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return [], [], []
    df = df.reset_index(drop=True)
    n = len(df)
    if n < WARMUP + 25:
        return [], [], []
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    dates = df['datetime'].tolist()
    idx = np.arange(n)
    inwin = np.array([FRESH[0] <= d <= FRESH[1] for d in dates])
    ok = (idx >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (c * _G['shares'][code] >= MIN_CAP) & inwin & (idx + 10 < n)
    e1, _ = LR.events_from_df(df, code, ok)
    e2 = LA.events_from_df(df, code, ok)
    pos = {d: k for k, d in enumerate(dates)}
    keep = ['code', 'date', 'dist_atr', 'sw_datr', 'mj_datr', 'pl_datr', 'm120_datr', 'm240_datr']
    m2 = {(r['code'], r['date']): {k: r[k] for k in keep} for r in e2}
    ev = []
    for r in e1:
        i = pos[r['date']]
        x = dict(r)
        x.update(m2.get((r['code'], r['date']), {}))
        x['x1'] = outcome(o, h, l, c, i, 0.15)[0]
        ev.append(x)
    base = [(dates[i], outcome(o, h, l, c, i, 0.15)[0]) for i in np.flatnonzero(ok)]
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    w2 = [(code, dates[i], outcome(o, h, l, c, i, 0.15)[0]) for kind, i, vr, *_ in w2scan(df, a)
          if kind == 'tl' and vr == vr and vr >= 2 and ok[i]]
    return ev, base, w2


def fresh():
    from sqlalchemy import create_engine, text
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')
                       | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(x) for k, x in zip(ms.stock_code, ms.listed_shares) if x}, 'bad': bad}
    b = pd.read_sql(text("SELECT stock_code, trade_date, open_price open, high_price high, low_price low, close_price close, volume "
                         "FROM stock_ohlcv_daily"), eng)
    b['datetime'] = (pd.to_datetime(b.trade_date) + pd.Timedelta(hours=9)).dt.strftime('%Y-%m-%d')
    b = b.drop(columns='trade_date').sort_values(['stock_code', 'datetime'])
    jobs = [(code, g.drop(columns='stock_code')) for code, g in b.groupby('stock_code', sort=False)]
    ev, base, w2 = [], [], []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for e, bs, w in pool.imap_unordered(fresh_stock, jobs, chunksize=8):
            ev += e; base += bs; w2 += w
    ev = pd.DataFrame(ev).drop_duplicates(['code', 'date'])
    sd = pd.DataFrame(base, columns=['date', 'ret']).groupby('date').ret.mean()
    w2 = pd.DataFrame(w2, columns=['code', 'date', 'x1'])
    pd.to_pickle({'ev': ev, 'sd': sd, 'w2': w2}, os.path.join(OUT, 'rebound_fresh.pkl'))
    return ev, sd, w2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sameday', required=True)
    ap.add_argument('--fresh-cached', action='store_true')
    args = ap.parse_args()
    sd = pd.read_pickle(args.sameday).set_index('date')['mean']

    a = pd.read_pickle(os.path.join(OUT, 'line_rebound_events.pkl'))
    b = pd.read_pickle(os.path.join(OUT, 'line_atr_events.pkl'))
    b = b[['code', 'date', 'jd', 'dist_atr', 'sw_datr', 'mj_datr', 'pl_datr', 'm120_datr', 'm240_datr']]
    # 같은 저가가 두 번 나온 날(동률 20봉 최저)은 신호가 겹친다 → (종목, 신호일) 하나만
    ev = features(a.merge(b, on=['code', 'date', 'jd'], how='inner').drop_duplicates(['code', 'date']))
    ev = ev[ev.date.isin(sd.index) & ev.x1.notna()].copy()
    ev['ex'] = ev.x1 - sd.loc[ev.date].values
    w2 = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    w2 = w2[(w2.kind == 'tl') & (w2.vol_ratio >= 2) & w2.date.isin(sd.index) & (w2.date <= ev.date.max())].copy()
    w2['ex'] = w2.ret15 - sd.loc[w2.date].values

    if args.fresh_cached:
        fz = pd.read_pickle(os.path.join(OUT, 'rebound_fresh.pkl'))
        fev, fsd, fw2 = fz['ev'].drop_duplicates(['code', 'date']), fz['sd'], fz['w2']
    else:
        fev, fsd, fw2 = fresh()
    fev = features(fev)
    fev['ex'] = fev.x1 - fsd.loc[fev.date].values
    fw2['ex'] = fw2.x1 - fsd.loc[fw2.date].values
    fev['year'] = 'NEW'

    print(f"반등 신호 {len(ev):,}건 ({ev.date.min()}~{ev.date.max()}) · 새 데이터 {len(fev):,}건 ({fev.date.min()}~{fev.date.max()}, "
          f"{fsd.size}일, 그날 전 종목 평균 {fsd.mean() * 100:+.2f}%)")

    years = ('2023', '2024', '2025', '2026')
    print("\n[①] 고정 후보 — 같은날대비 %p (건수). 마지막 칸 = 새 데이터(2026-08-20~10-30)")
    print(f"  {'규칙':<30}{'전 기간':>22}  " + ''.join(f"{y:>16}" for y in years) + f"{'새 데이터':>22}")
    rows = FIXED + [('비교: 2파', None)]
    for lab, fn in rows:
        if fn is None:
            g, f = w2, fw2
        else:
            g, f = ev[fn(ev)], fev[fn(fev)]
        lo, hi = ci(g.ex, g.code)
        cells = ''.join(f"{g[g.year == y].ex.mean() * 100:>+8.2f} ({(g.year == y).sum():>5})" for y in years)
        flo, fhi = ci(f.ex, f.code, 500)
        print(f"  {lab:<30}{g.ex.mean() * 100:>+7.2f} [{lo:+.2f}~{hi:+.2f}]  {cells}  {f.ex.mean() * 100:>+7.2f} ({len(f):>4}) [{flo:+.2f}~{fhi:+.2f}]")

    print("\n[②] 전진 검증 — Y 이전으로 1위 조건 고르고 Y 에 적용 (조건 360개, 학습 200건·40일 이상)")
    grid = list(itertools.product(LINE, VOL, DIST, CR))
    masks = {k: LINE[k[0]](ev) & VOL[k[1]](ev) & DIST[k[2]](ev) & CR[k[3]](ev) for k in grid}
    fmasks = {k: LINE[k[0]](fev) & VOL[k[1]](fev) & DIST[k[2]](fev) & CR[k[3]](fev) for k in grid}
    for sname, score in (('S1 평균 최대', lambda g: g.ex.mean()), ('S2 t값 최대', tstat)):
        picked = []
        print(f"  ── {sname}")
        for Y in ('2024', '2025', '2026'):
            tr = (ev.year < Y).to_numpy()
            best, bk = -np.inf, None
            for k in grid:
                g = ev[masks[k] & tr]
                if len(g) < 200 or g.date.nunique() < 40:
                    continue
                s = score(g)
                if s > best:
                    best, bk = s, k
            g_tr = ev[masks[bk] & tr]
            g_te = ev[masks[bk] & (ev.year == Y)]
            allte = ev[ev.year == Y]
            lo, hi = ci(g_te.ex, g_te.code, 500)
            picked.append(g_te)
            print(f"   시험 {Y}: 고른 조건 라인={bk[0]} 거래량={bk[1]} 진입거리={bk[2]} 폭락={bk[3]} │ 학습 {g_tr.ex.mean() * 100:+.2f}%p ({len(g_tr)})"
                  f" → 시험 {g_te.ex.mean() * 100:+.2f}%p ({len(g_te)}) [{lo:+.2f}~{hi:+.2f}] │ 그해 반등 전체 {allte.ex.mean() * 100:+.2f}%p · 2파 {w2[w2.year == Y].ex.mean() * 100:+.2f}%p")
        pool_ = pd.concat(picked)
        lo, hi = ci(pool_.ex, pool_.code)
        ok = all(p.ex.mean() > 0 for p in picked) and lo > 0
        print(f"   시험 합침 {pool_.ex.mean() * 100:+.2f}%p ({len(pool_)}) [{lo:+.2f}~{hi:+.2f}] → 통과 기준 {'충족' if ok else '미충족'}")
        # 전 기간(2026 포함 이전 전체)으로 고른 조건을 새 데이터에
        best, bk = -np.inf, None
        for k in grid:
            g = ev[masks[k]]
            if len(g) < 200 or g.date.nunique() < 40:
                continue
            s = score(g)
            if s > best:
                best, bk = s, k
        f = fev[fmasks[bk]]
        flo, fhi = ci(f.ex, f.code, 500)
        print(f"   전 기간 1위 라인={bk[0]} 거래량={bk[1]} 진입거리={bk[2]} 폭락={bk[3]} ({ev[masks[bk]].ex.mean() * 100:+.2f}%p) → 새 데이터 "
              f"{f.ex.mean() * 100:+.2f}%p ({len(f)}) [{flo:+.2f}~{fhi:+.2f}]")

    # 상위 10개 조건이 해마다 얼마나 바뀌나
    print("\n[참고] 학습 기간별 S1 상위 5개 조건")
    for Y in ('2024', '2025', '2026'):
        tr = (ev.year < Y).to_numpy()
        sc = []
        for k in grid:
            g = ev[masks[k] & tr]
            if len(g) >= 200 and g.date.nunique() >= 40:
                sc.append((g.ex.mean(), len(g), k))
        sc.sort(reverse=True)
        print(f"  ~{int(Y) - 1}: " + ' │ '.join(f"{k[0]}/{k[1]}/{k[2]}/{k[3]} {m * 100:+.2f}({n})" for m, n, k in sc[:5]))


if __name__ == '__main__':
    main()
