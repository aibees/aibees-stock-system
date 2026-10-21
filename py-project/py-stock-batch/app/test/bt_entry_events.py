"""
bt_entry_events.py — 유명한 매수 진입 두 가지를 전 종목 5년 일봉에서 따로 떼어 검증한다.

    ① 쌍바닥 넥라인 돌파
    ② 엘리엇 3파 시작 — (a) 2파 저점이 확정된 날(이른 진입)  (b) 종가가 1파 고점을 처음 넘은 날(돌파 확인)

정의는 실행 전에 고정한다(결과를 보고 바꾸지 않는다). 숫자는 stock_shared.chart_analysis 와 같게 맞췄다.
    스윙      : ZigZag, 장중 고가·저가 기준, 반전 폭 = max(ATR14 × 배수, 3%) — 배수 2.5(촘촘)·4.0(느슨) 두 단위
    쌍바닥    : 확정 스윙 L1-H-L2, |L1-L2| <= max(3%, 0.75 ATR), 골 깊이(H - min L) >= max(5%, 1.5 ATR),
                L1~L2 간격 >= 5봉 → L2 이후 종가가 H(넥라인)를 **처음** 넘은 날
                계획: 손절 = 넥라인 - 높이/2, 목표 = 넥라인 + 높이   (patterns.py 와 동일)
    3파 시작  : 확정 스윙 L0-H1-L2, L2 > L0(2파가 1파 시작점 유지), 2파 되돌림 (H1-L2)/(H1-L0) ∈ [0.382, 0.786]
                (a) L2 가 확정된 날  (b) 그 뒤 L2 아래로 안 내려가고 종가가 H1 을 처음 넘은 날
                계획: 손절 = L2(무너지면 3파 해석이 깨짐), 목표 = L2 + 1파 × 1.618
미래 참조 차단
    ZigZag 를 하루씩 앞으로 진행시키며(online) 그날까지 **확정된** 스윙만 쓴다. 차트 화면처럼 최근 200봉을
    다시 잘라 계산하면 창이 밀릴 때 앞 스윙이 바뀌므로 여기서는 전체 이력 기준 online 계산을 쓴다.
진입·평가
    다음 날 시가 진입. 매도 세 가지:
      plan : 위 계획 손절·목표(장중 체결, 같은 봉이면 손절 먼저, 갭이면 시가), 최대 40봉
      live5: 실전 매도 근사(bt_reco_stop.sim_live) 손절 -5%   live8: 같은 규칙 손절 -8%
비교 기준
    plan  → 우연 기준 적중률 = (진입-손절)/(목표-손절)  (방향성 없는 가격이 목표에 먼저 닿을 확률)
    live* → 같은 종목·같은 필터의 "아무 날 진입"(20봉마다 표본) 결과
필터: 종가 >= 1,000원, 최근 20일 평균 거래대금(종가×거래량) >= 5억, 신호일까지 250봉 이상.

사용
    poetry run python -m app.test.bt_entry_events                 # bt_reco_cache/stocks 캐시 사용
    poetry run python -m app.test.bt_entry_events --report-only
"""
import argparse
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.eval_shape_proba import FEE_RATE
from app.test.bt_reco_stop import sim_live
from stock_shared.chart_analysis.indicators import atr as atr_fn
from stock_shared.strategy.kospi1 import KospiStrategy1

CACHE = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
DEGREES = (2.5, 4.0)
MIN_PCT = 3.0
MAX_HOLD = 40
MIN_PRICE = 1000
MIN_AMOUNT = 5e8
WARMUP = 250
BASE_EVERY = 20
EVENTS = {'dbl_bottom': '쌍바닥 넥라인 돌파', 'w3_early': '3파 시작 · 2파 저점 확정', 'w3_break': '3파 시작 · 1파 고점 돌파'}


# ══════════════════════════════════════════════════════════════════
# 하루씩 진행하는 ZigZag — 그날까지 확정된 스윙만 쓴다
# ══════════════════════════════════════════════════════════════════
def scan_events(df: pd.DataFrame, a: np.ndarray, mult: float) -> list:
    """반환: [(event, i, plan_stop, plan_target, extra)] — i 는 신호 봉(그 봉 종가로 판정, 다음 봉 시가 진입)."""
    high, low, close = df['high'].to_numpy(float), df['low'].to_numpy(float), df['close'].to_numpy(float)
    n = len(df)
    piv = []                    # 확정 스윙 [(kind, i, price)]
    direction, ext_i = 0, 0
    hi_i = lo_i = 0
    out = []
    armed_db = None             # 쌍바닥 돌파 대기: (neck, stop, target, l2_i)
    armed_w3 = None             # 3파 돌파 대기: (h1, l2, target)

    def thr(i, ref):
        return max(a[i] * mult, ref * MIN_PCT / 100)

    for i in range(1, n):
        new_low_confirmed = False
        if direction == 0:
            if high[i] > high[hi_i]:
                hi_i = i
            if low[i] < low[lo_i]:
                lo_i = i
            if lo_i < hi_i and high[hi_i] - low[lo_i] >= thr(i, low[lo_i]):
                piv.append(('L', lo_i, low[lo_i])); direction, ext_i = 1, hi_i
                new_low_confirmed = True
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
                new_low_confirmed = True

        if new_low_confirmed and len(piv) >= 3:
            (k0, i0, p0), (k1, i1, p1), (k2, i2, p2) = piv[-3], piv[-2], piv[-1]
            if (k0, k1, k2) == ('L', 'H', 'L'):
                # ── 쌍바닥 후보: 넥라인 돌파를 기다린다 ──
                ref = min(p0, p2)
                tol = max(0.03 * ref, a[i] * 0.75)
                depth = p1 - ref
                if abs(p0 - p2) <= tol and depth >= max(0.05 * ref, a[i] * 1.5) and i2 - i0 >= 5:
                    armed_db = (p1, p1 - depth * 0.5, p1 + depth, i2)
                else:
                    armed_db = None
                # ── 3파 시작 후보 ──
                w1 = p1 - p0
                r2 = (p1 - p2) / w1 if w1 > 0 else -1
                if p2 > p0 and 0.382 <= r2 <= 0.786:
                    tgt = p2 + 1.618 * w1
                    out.append(('w3_early', i, p2, tgt, r2))
                    armed_w3 = (p1, p2, tgt)
                else:
                    armed_w3 = None

        # 돌파 판정(종가 기준, 처음 넘은 날만)
        if armed_db is not None:
            neck, stop, tgt, _ = armed_db
            if low[i] < stop - (neck - stop):        # 바닥(=neck-높이)을 깨면 무효
                armed_db = None
            elif close[i] > neck:
                out.append(('dbl_bottom', i, stop, tgt, None))
                armed_db = None
        if armed_w3 is not None:
            h1, l2, tgt = armed_w3
            if low[i] < l2:
                armed_w3 = None
            elif close[i] > h1:
                out.append(('w3_break', i, l2, tgt, None))
                armed_w3 = None
    return out


def sim_plan(recs: list, i_sig: int, stop: float, target: float):
    if i_sig + 1 >= len(recs):
        return None
    entry = float(recs[i_sig + 1]['open'] or 0)
    if entry <= 0 or not (stop < entry * 0.995 and target > entry * 1.005):
        return None
    last = min(i_sig + MAX_HOLD, len(recs) - 1)
    for k in range(i_sig + 1, last + 1):
        r = recs[k]
        o, h, l = float(r['open']), float(r['high']), float(r['low'])
        first = k == i_sig + 1
        if l <= stop:
            px, why = (stop if first else min(o, stop)), 'STOP'
            break
        if h >= target:
            px, why = (target if first else max(o, target)), 'TARGET'
            break
    else:
        px, why, k = float(recs[last]['close']), ('TIME' if last == i_sig + MAX_HOLD else 'OPEN'), last
    return {'ret': (px - entry) / entry - 2 * FEE_RATE, 'why': why, 'bars': k - i_sig,
            'null': (entry - stop) / (target - stop), 'tgt_pct': (target / entry - 1) * 100,
            'stop_pct': (stop / entry - 1) * 100}


def run(paths: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    s5, s8 = KospiStrategy1(), KospiStrategy1()
    s8.stop_loss_pct = 0.08
    ev_rows, base_rows = [], []
    t0 = time.time()
    for n, path in enumerate(paths, 1):
        code = os.path.basename(path)[:-4]
        df = pd.read_pickle(path).reset_index(drop=True)
        if len(df) < WARMUP + 20:
            continue
        df['coin'] = code
        a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
        amt = (df['close'].astype(float) * df['volume'].astype(float)).rolling(20).mean().to_numpy()
        close = df['close'].to_numpy(float)
        ok = (np.arange(len(df)) >= WARMUP) & (close >= MIN_PRICE) & (amt >= MIN_AMOUNT)
        recs = df.to_dict('records')
        dates = df['datetime'].tolist()

        def trade(i, stop=None, target=None):
            row = {'coin': code, 'date': dates[i], 'year': dates[i][:4]}
            t5, t8 = sim_live(s5, recs, i), sim_live(s8, recs, i)
            if t5 is None or t5['reason'] == 'OPEN_MTM' or t8['reason'] == 'OPEN_MTM':
                return None
            row.update({'live5': t5['ret_net'], 'live5_why': t5['reason'], 'live5_bars': t5['bars_held'],
                        'live8': t8['ret_net'], 'live8_why': t8['reason'], 'live8_bars': t8['bars_held']})
            if stop is not None:
                p = sim_plan(recs, i, stop, target)
                if p is None or p['why'] == 'OPEN':
                    return None
                row.update({'plan': p['ret'], 'plan_why': p['why'], 'plan_bars': p['bars'], 'null': p['null'],
                            'tgt_pct': p['tgt_pct'], 'stop_pct': p['stop_pct']})
            return row

        seen = set()
        for mult in DEGREES:
            for ev, i, stop, tgt, extra in scan_events(df, a, mult):
                if not ok[i] or (ev, i) in seen:       # 두 단위에서 같은 날 같은 신호면 한 번만
                    continue
                seen.add((ev, i))
                r = trade(i, stop, tgt)
                if r:
                    r.update({'event': ev, 'degree': mult, 'r2': extra})
                    ev_rows.append(r)
        for i in range(WARMUP, len(df) - 1, BASE_EVERY):
            if ok[i]:
                r = trade(i)
                if r:
                    base_rows.append(r)
        if n % 200 == 0 or n == len(paths):
            print(f"[scan] {n}/{len(paths)} · 이벤트 {len(ev_rows)} · 기준표본 {len(base_rows)} · {time.time() - t0:.0f}s", flush=True)
    ev, base = pd.DataFrame(ev_rows), pd.DataFrame(base_rows)
    ev.to_pickle(os.path.join(CACHE, 'entry_events.pkl'))
    base.to_pickle(os.path.join(CACHE, 'entry_base.pkl'))
    return ev, base


def _s(x):
    x = x * 100
    return f"승률 {(x > 0).mean() * 100:5.1f}%  평균 {x.mean():+6.2f}%  중앙 {x.median():+6.2f}%"


def report(ev: pd.DataFrame, base: pd.DataFrame):
    print(f"\n이벤트 {len(ev)}건 · 아무 날 진입 표본 {len(base)}건 (2022-10~2026-10, 필터 통과분)")
    print("\n══ 아무 날 진입(기준)")
    for col in ('live5', 'live8'):
        print(f"  {col}: {_s(base[col])}  보유 {base[col + '_bars'].mean():.1f}봉")
    for ev_key, name in EVENTS.items():
        e = ev[ev['event'] == ev_key]
        if e.empty:
            continue
        print(f"\n══ {name} — {len(e)}건 (단위별 {e['degree'].value_counts().to_dict()})")
        res_ = e[e['plan_why'].isin(['TARGET', 'STOP'])]          # 우연 기준은 둘 중 하나엔 닿는다는 가정 → 닿은 것끼리 비교
        tgt_hit = (res_['plan_why'] == 'TARGET').mean() * 100
        print(f"  계획 매도  {_s(e['plan'])}  보유 {e['plan_bars'].mean():.1f}봉 · 목표 먼저 {tgt_hit:.1f}% vs 우연 기준 {res_['null'].mean() * 100:.1f}% "
              f"(목표·손절 닿은 {len(res_)}건, 40봉 내 미도달 {(e['plan_why'] == 'TIME').mean() * 100:.0f}%) "
              f"(목표 중앙 {e['tgt_pct'].median():+.1f}% / 손절 중앙 {e['stop_pct'].median():+.1f}%)")
        for col in ('live5', 'live8'):
            d = (e[col].mean() - base[col].mean()) * 100
            print(f"  실전 {col}  {_s(e[col])}  · 아무 날 대비 평균 {d:+.2f}%p, 승률 {((e[col] > 0).mean() - (base[col] > 0).mean()) * 100:+.1f}%p")
        print(f"  {'연도':<6}{'n':>6}{'목표먼저':>9}{'우연':>7}{'plan 평균':>10}{'live5 평균':>11}{'(기준)':>8}{'live8 평균':>11}{'(기준)':>8}")
        def _hit(g):
            r_ = g[g['plan_why'].isin(['TARGET', 'STOP'])]
            return ((r_['plan_why'] == 'TARGET').mean() * 100 if len(r_) else float('nan')), (r_['null'].mean() * 100 if len(r_) else float('nan'))
        for y, g in e.groupby('year'):
            b = base[base['year'] == y]
            h_, n_ = _hit(g)
            print(f"  {y:<6}{len(g):>6}{h_:>8.1f}%{n_:>6.1f}%"
                  f"{g['plan'].mean() * 100:>+10.2f}{g['live5'].mean() * 100:>+11.2f}{b['live5'].mean() * 100:>+8.2f}"
                  f"{g['live8'].mean() * 100:>+11.2f}{b['live8'].mean() * 100:>+8.2f}")
        for deg, g in e.groupby('degree'):
            h_, n_ = _hit(g)
            print(f"  ATR {deg}배 단위 n={len(g)}: 목표먼저 {h_:.1f}% vs 우연 {n_:.1f}% · "
                  f"plan {g['plan'].mean() * 100:+.2f}% · live8 {g['live8'].mean() * 100:+.2f}%")
        if ev_key.startswith('w3'):
            e2 = e.dropna(subset=['r2']) if ev_key == 'w3_early' else None
            if e2 is not None and len(e2):
                for lo, hi in ((0.382, 0.5), (0.5, 0.618), (0.618, 0.786)):
                    g = e2[(e2['r2'] >= lo) & (e2['r2'] < hi + 1e-9)]
                    h_, n_ = _hit(g)
                    print(f"  2파 되돌림 {lo}~{hi}: n={len(g)} 목표먼저 {h_:.1f}% vs 우연 {n_:.1f}% · "
                          f"live8 {g['live8'].mean() * 100:+.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--limit', type=int, default=0, help='앞 N종목만(점검용)')
    args = ap.parse_args()
    if args.report_only:
        ev, base = pd.read_pickle(os.path.join(CACHE, 'entry_events.pkl')), pd.read_pickle(os.path.join(CACHE, 'entry_base.pkl'))
    else:
        paths = sorted(glob.glob(os.path.join(CACHE, 'stocks', '*.pkl')))
        if args.limit:
            paths = paths[:args.limit]
        ev, base = run(paths)
    report(ev, base)


if __name__ == '__main__':
    main()
