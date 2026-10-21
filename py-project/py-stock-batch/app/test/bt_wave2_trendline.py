"""
bt_wave2_trendline.py — 2파 하락 추세선을 돌파하며 3파가 시작되는 모양 + 거래량 증가, 전 종목 5년 검증.

사용자 의도(초기 매수추천 모델이 원래 노리던 것): 1파 상승 뒤 2파 조정의 하락 추세를 깨고 3파가 시작될 때,
거래량이 붙는 날 산다. (예전엔 20일선 돌파로 근사했었다)

정의 — 실행 전에 고정
    스윙      : 하루씩 진행하는 ZigZag, 장중 고가·저가, 반전폭 = max(ATR14 × 4, 3%)  (그날까지 확정된 스윙만)
    2파 구간  : 확정 스윙 L0 → H1 다음, 아직 종가가 H1 을 넘지 않은 동안 (2파 저점 L2 가 확정됐든 아직이든)
    추세선    : H1 에서 출발해 H1 이후 (돌파 전날까지의) 고가를 전부 위에서 덮는 가장 완만한 직선
                = 기울기 max_j (high[j] - H1) / (j - i1), j ∈ [i1+2, t-1]. 기울기 < 0 일 때만 하락 추세선.
    돌파      : 종가 > 추세선(t) 이고 전날 종가 <= 추세선(t-1) 인 첫 봉(2파 구간당 1회)
                조건: H1 이후 5봉 이상, 지금까지의 2파 최저 > L0, 되돌림 (H1 - 최저)/(H1 - L0) ∈ [0.382, 0.786], 종가 < H1
    거래량    : 돌파일 거래량 / 직전 20일 평균 (1.5·2·3배 구간으로 나눠 본다)
    비교      : ma20  — 같은 2파 구간에서 종가가 20일선을 처음 넘은 봉(예전 방식)
                h1    — 같은 구조에서 종가가 H1 을 처음 넘은 봉(1파 고점 돌파)
                base  — 필터 통과 아무 날(20봉마다 표본)
평가 — 프로젝트 기준(수익 우선)
    D+1 시가 매수, 10거래일 안에 장중 고가 +15% 먼저 = 익절 / 저가 -8% 먼저 = 손절(같은 날이면 손절) / 둘 다 없으면 10일째 종가.
    왕복 수수료 0.22%. 참고: +25% 목표 수익, 20일 안에 H1 돌파(3파로 이어짐) 비율.
필터: 종가 >= 1,000원, 20일 평균 거래대금 >= 5억, 시총(종가 × 현재 상장주식수) >= 1,000억, 보통주, 관리·정지(현재) 제외, 250봉 이상.

사용
    poetry run python -m app.test.bt_wave2_trendline
    poetry run python -m app.test.bt_wave2_trendline --report-only
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from stock_shared.strategy.wave2_breakout import scan  # noqa: E402  (운영 배치와 같은 판정)

CACHE = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
OUT = os.path.join(CACHE, 'wave2')
MULT, MIN_PCT = 4.0, 3.0
H, STOP, FEE = 10, 0.08, 0.0022
WARMUP, MIN_PRICE, MIN_AMOUNT, MIN_CAP = 250, 1000, 5e8, 1000e8
BASE_EVERY = 20
_G = {}


def _init(meta):
    _G.update(meta)


def outcome(o, h, l, c, i, T):
    """D+1 시가 진입 → (규칙 수익, 결과 'W'/'F'/'N', 손절 전 최대 상승)."""
    e = o[i + 1]
    peak = 0.0
    for k in range(i + 1, i + H + 1):
        if l[k] / e - 1 <= -STOP:
            return (-STOP if k == i + 1 else min(o[k] / e - 1, -STOP)) - FEE, 'F', peak
        peak = max(peak, h[k] / e - 1)
        if peak >= T:
            return (T if k == i + 1 else max(o[k] / e - 1, T)) - FEE, 'W', peak
    return c[i + H] / e - 1 - FEE, 'N', peak


def run_stock(path):
    from stock_shared.chart_analysis.indicators import atr as atr_fn
    code = os.path.basename(path)[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return [], []
    df = pd.read_pickle(path).reset_index(drop=True)
    n = len(df)
    if n < WARMUP + 25:
        return [], []
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    cap = c * _G['shares'][code]
    ok = (np.arange(n) >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (cap >= MIN_CAP) & (np.arange(n) < n - 21)
    dates = df['datetime'].astype(str).str[:10].tolist()
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    ev, base = [], []

    def row(kind, i, extra):
        r15, x15, m15 = outcome(o, h, l, c, i, 0.15)
        r25, x25, _ = outcome(o, h, l, c, i, 0.25)
        d = {'kind': kind, 'code': code, 'date': dates[i], 'year': dates[i][:4], 'ret15': r15, 'res15': x15, 'mup15': m15,
             'ret25': r25, 'res25': x25, 'ret10c': c[i + H] / o[i + 1] - 1 - FEE}
        d.update(extra)
        return d

    for kind, i, vr, retr, since_h1, p1 in scan(df, a):
        if not ok[i]:
            continue
        reach_h1 = bool((h[i + 1:i + 21] > p1).any())
        ev.append(row(kind, i, {'vol_ratio': vr, 'retr': retr, 'since_h1': since_h1, 'to_h1': p1 / c[i] - 1,
                                'h1_in20': reach_h1}))
    for i in range(WARMUP, n - 21, BASE_EVERY):
        if ok[i]:
            base.append(row('base', i, {}))
    return ev, base


def run():
    from sqlalchemy import create_engine
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y')
                       | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(v) for k, v in zip(ms.stock_code, ms.listed_shares) if v}, 'bad': bad}
    paths = sorted(os.path.join(CACHE, 'stocks', x) for x in os.listdir(os.path.join(CACHE, 'stocks')))
    t0 = time.time()
    ev, base = [], []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for k, (e, b) in enumerate(pool.imap_unordered(run_stock, paths, chunksize=8), 1):
            ev += e; base += b
            if k % 500 == 0:
                print(f"[scan] {k}/{len(paths)} · 이벤트 {len(ev)} · {time.time() - t0:.0f}s", flush=True)
    os.makedirs(OUT, exist_ok=True)
    ev, base = pd.DataFrame(ev), pd.DataFrame(base)
    ev.to_pickle(os.path.join(OUT, 'events.pkl')); base.to_pickle(os.path.join(OUT, 'base.pkl'))
    return ev, base


def _line(lab, g):
    if not len(g):
        return f"  {lab:<30} n=0"
    return (f"  {lab:<30} n={len(g):<6} 수익 {g.ret15.mean() * 100:+6.2f}%  익절 {(g.res15 == 'W').mean() * 100:5.1f}%  "
            f"손절 {(g.res15 == 'F').mean() * 100:5.1f}%  (+25%목표 수익 {g.ret25.mean() * 100:+6.2f}%)"
            + (f"  20일내 H1 돌파 {g.h1_in20.mean() * 100:4.1f}%" if 'h1_in20' in g and g.h1_in20.notna().any() else ''))


def report(ev, base):
    print(f"\n이벤트 {len(ev)}건 · 아무 날 표본 {len(base)}건  — 수익 = +15% 익절 / -8% 손절 / 10일 매매당 평균(수수료 차감)")
    print(_line('아무 날(기준)', base))
    for k, nm in (('tl', '2파 하락추세선 돌파'), ('ma20', '2파 중 20일선 돌파'), ('h1', '1파 고점 돌파')):
        e = ev[ev.kind == k]
        print(f"\n══ {nm}")
        print(_line('전체', e))
        for lo, hi, lab in ((0, 1.5, '거래량 1.5배 미만'), (1.5, 2, '거래량 1.5~2배'), (2, 3, '거래량 2~3배'), (3, 1e9, '거래량 3배 이상')):
            print(_line(lab, e[(e.vol_ratio >= lo) & (e.vol_ratio < hi)]))
        print(f"  {'연도':<6}" + ''.join(f"{y:>16}" for y in ('2022', '2023', '2024', '2025', '2026')) + "   (수익 · 건수)")
        for lab, sub in (('전체', e), ('거래량 2배↑', e[e.vol_ratio >= 2]), ('아무 날', base)):
            line = f"  {lab:<8}"
            for y in ('2022', '2023', '2024', '2025', '2026'):
                g = sub[sub.year == y]
                line += f"{g.ret15.mean() * 100:>+8.2f}% {len(g):>5}" if len(g) else f"{'-':>16}"
            print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    args = ap.parse_args()
    if args.report_only:
        ev, base = pd.read_pickle(os.path.join(OUT, 'events.pkl')), pd.read_pickle(os.path.join(OUT, 'base.pkl'))
    else:
        ev, base = run()
    report(ev, base)


if __name__ == '__main__':
    main()
