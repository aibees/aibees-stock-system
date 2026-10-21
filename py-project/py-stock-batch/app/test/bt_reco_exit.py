"""
bt_reco_exit.py — 같은 매수추천 신호에서 "매도 방식"만 바꾸면 승률·수익이 어떻게 달라지나.

매수는 그대로(D+1 시가). 매도 기준가는 전부 **추천일 D 의 차트 분석으로 미리 정해 두고** 보유 중에 바꾸지 않는다
(보유 중에 다시 분석하면 ZigZag 가 바뀌어 목표가 따라 움직이는 "사후 맞춤"이 된다).

매도 방식
    base      : 현행 KospiStrategy1(손절 -5% / 익절 +30% / 트레일 ATR3 / 타임스탑 12봉) — run_one_trade 그대로
    elliott   : 가장 유력한 '다음 상승' 해석의 다음 목표(bias_target) 익절 / 그 해석 무효선 손절
    el_hybrid : 현행 규칙 그대로 + 엘리엇 목표에 닿으면 그 가격에 익절
    fib       : 피보 매수 쪽 기준 파동 고점 익절 / 0.786 되돌림 손절
    struct    : 직전 고점 익절 / 직전 저점 손절
가격 기준 매도(elliott/fib/struct)
    - 봉 안에서 손절·목표가 둘 다 닿으면 손절이 먼저(보수적). 시가가 이미 넘어 있으면 시가 체결(갭).
    - 최대 MAX_HOLD 봉 보유 후 종가 청산.
    - 목표가 진입가 +1% 이하이거나 손절이 진입가 -1% 이상이면 그 신호에는 이 방식을 "적용 불가"로 둔다.
비교는 **같은 신호끼리**(그 방식이 적용 가능한 신호에서 base 와 나란히) 한다 — 적용 가능한 신호가 방식마다 달라서다.

사용
    poetry run python -m app.test.bt_reco_exit
    poetry run python -m app.test.bt_reco_exit --report-only
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService
from app.test.eval_shape_proba import (DB_URL, FEE_RATE, SELL_ACTIONS, _base_user_info, run_one_trade, _wilson)
from app.test.bt_reco_chart_analysis import load_bars, ANALYSIS_BARS, VIEW_BARS
from app.test.bt_reco_history import load_reco, dedupe
from stock_shared import chart_analysis
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.vo.userCoinInfo import UserCoinInfo

OUT_DIR = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
MAX_HOLD = 40
MIN_GAP = 0.01
METHODS = ['base', 'elliott', 'el_hybrid', 'fib', 'struct']
NAMES = {'base': '현행', 'elliott': '엘리엇 목표/무효', 'el_hybrid': '현행+엘리엇 목표 익절',
         'fib': '피보 고점/0.786', 'struct': '직전 고점/저점'}


def levels_at(a: dict) -> dict:
    """D 시점 분석 → 방식별 (목표, 손절)."""
    lv = {}
    items = (a.get('elliott') or {}).get('items') or []
    up = next((c for c in items if c.get('bias') == 'up'), None)
    if up:
        lv['elliott'] = (up.get('bias_target'), (up.get('invalid') or {}).get('price'))
        lv['el_title'] = up.get('title')
    fib = a.get('fib') or {}
    plan = fib.get('plan') or {}
    if plan.get('side') == 'buy':
        lv['fib'] = (plan.get('target'), plan.get('stop'))
    st = a.get('structure') or {}
    if st:
        lv['struct'] = ((st.get('resistance') or {}).get('price'), (st.get('support') or {}).get('price'))
    return lv


def _ok(entry, target, stop):
    return (target is not None and stop is not None
            and target > entry * (1 + MIN_GAP) and stop < entry * (1 - MIN_GAP))


def sim_levels(recs: list, i_sig: int, target: float, stop: float) -> dict | None:
    """가격 기준 매도. recs[i_sig+1] 시가 진입."""
    if i_sig + 1 >= len(recs):
        return None
    entry = float(recs[i_sig + 1]['open'] or 0)
    if entry <= 0 or not _ok(entry, target, stop):
        return None
    last = min(i_sig + MAX_HOLD, len(recs) - 1)
    for k in range(i_sig + 1, last + 1):
        r = recs[k]
        o, h, l = float(r['open']), float(r['high']), float(r['low'])
        if l <= stop:                       # 손절 먼저(같은 봉에 목표도 닿았어도)
            px, why = (min(o, stop) if k > i_sig + 1 else stop), 'STOP'
            break
        if h >= target:
            px, why = (max(o, target) if k > i_sig + 1 else target), 'TARGET'
            break
    else:
        r = recs[last]
        px, why = float(r['close']), ('TIME' if last == i_sig + MAX_HOLD else 'OPEN_MTM')
        k = last
    gross = (px - entry) / entry
    return {'ret_net': gross - 2 * FEE_RATE, 'reason': why, 'bars_held': k - i_sig}


def sim_hybrid(strategy, recs: list, i_sig: int, target: float) -> dict | None:
    """현행 KospiStrategy1 + 엘리엇 목표 익절(봉 안에서 목표 닿으면 그 가격)."""
    if i_sig + 1 >= len(recs) or target is None:
        return None
    er = recs[i_sig + 1]
    entry = float(er['open'] or 0)
    if entry <= 0 or target <= entry * (1 + MIN_GAP):
        return None
    ui = _base_user_info()
    ui.has_position = True
    ui.avg_price = ui.entry_price = entry
    ui.entry_atr = float(er['atr'] or 0)
    ui.peak_high = float(er['high'] or entry)
    ui.peak_close = float(er['close'] or entry)
    for i in range(i_sig + 1, len(recs)):
        r = recs[i]
        prev_r = recs[i - 1]
        if float(r['high']) >= target:
            px = max(float(r['open']), target) if i > i_sig + 1 else target
            return {'ret_net': (px - entry) / entry - 2 * FEE_RATE, 'reason': 'TARGET', 'bars_held': i - i_sig}
        prev_peak = ui.peak_high
        ui.peak_high = max(ui.peak_high, float(r['high'] or 0))
        ui.peak_close = max(ui.peak_close, float(r['close'] or 0))
        ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
        ui.bars_held += 1
        res = strategy.get_action_in_active(UserCoinInfo.from_dict(prev_r), UserCoinInfo.from_dict(r), ui)
        ra = (res or {}).get('result_action')
        if ra in SELL_ACTIONS:
            nr = recs[i + 1] if i + 1 < len(recs) else r
            px = float(nr['open'] or nr['close']) if i + 1 < len(recs) else float(r['close'])
            return {'ret_net': (px - entry) / entry - 2 * FEE_RATE, 'reason': ra.name, 'bars_held': i - i_sig}
    last = recs[-1]
    return {'ret_net': (float(last['close']) - entry) / entry - 2 * FEE_RATE, 'reason': 'OPEN_MTM',
            'bars_held': len(recs) - 1 - i_sig}


def evaluate(reco: pd.DataFrame, engine) -> pd.DataFrame:
    strategy = KospiStrategy1()
    rows = []
    codes = reco['stock_code'].unique()
    for n, code in enumerate(codes, 1):
        bars = load_bars('db', code, engine)
        if bars is None or len(bars) < 60:
            continue
        computed = KisService().compute_indicator_df(bars.copy(), user_info=_base_user_info())
        computed['coin'] = code
        computed['datetime'] = computed['datetime'].astype(str).str[:10]
        recs = computed.to_dict('records')
        dates_idx = {d: k for k, d in enumerate(computed['datetime'])}
        ohlc = computed[['datetime', 'open', 'high', 'low', 'close']].rename(columns={'datetime': 'ymd'})
        for _, rk in reco[reco['stock_code'] == code].iterrows():
            i = dates_idx.get(rk['datetime'])
            if i is None or i + 1 >= len(recs):
                continue
            ctx = chart_analysis.Context(ohlc.iloc[max(0, i - ANALYSIS_BARS + 1): i + 1], VIEW_BARS)
            a = {m: chart_analysis.MODULES[m](ctx) for m in ('structure', 'fib', 'elliott')}
            lv = levels_at(a)
            row = {'datetime': rk['datetime'], 'stock_code': code, 'path': rk['path'],
                   'entry': float(recs[i + 1]['open']), 'el_title': lv.get('el_title')}
            out = {'base': run_one_trade(strategy, recs, i, None)}
            if 'elliott' in lv:
                out['elliott'] = sim_levels(recs, i, *lv['elliott'])
                out['el_hybrid'] = sim_hybrid(strategy, recs, i, lv['elliott'][0])
            if 'fib' in lv:
                out['fib'] = sim_levels(recs, i, *lv['fib'])
            if 'struct' in lv:
                out['struct'] = sim_levels(recs, i, *lv['struct'])
            for m in METHODS:
                t = out.get(m)
                row[f'{m}_ret'] = t['ret_net'] if t else np.nan
                row[f'{m}_why'] = t['reason'] if t else None
                row[f'{m}_bars'] = t['bars_held'] if t else np.nan
            for m in ('elliott', 'fib', 'struct'):
                tg, sp = lv.get(m, (None, None))
                row[f'{m}_tgt_pct'] = (tg / row['entry'] - 1) * 100 if tg else np.nan
                row[f'{m}_stop_pct'] = (sp / row['entry'] - 1) * 100 if sp else np.nan
            rows.append(row)
        if n % 100 == 0 or n == len(codes):
            print(f"[eval] 종목 {n}/{len(codes)} · 신호 {len(rows)}", flush=True)
    res = pd.DataFrame(rows)
    res.to_pickle(os.path.join(OUT_DIR, 'reco_exit.pkl'))
    return res


def _line(name, s, bars=None, why=None):
    n = len(s)
    if n == 0:
        return f"  {name:<22} n=0"
    k = int((s > 0).sum())
    lo, hi = _wilson(k, n)
    out = (f"  {name:<22} n={n:<4} 승률 {k / n * 100:5.1f}% [{lo:4.1f}~{hi:4.1f}]  평균 {s.mean() * 100:+6.2f}%  "
           f"중앙 {s.median() * 100:+6.2f}%")
    if bars is not None:
        out += f"  보유 {bars.mean():4.1f}봉"
    if why is not None:
        vc = why.value_counts(normalize=True) * 100
        out += '  ' + ' '.join(f"{k_}{v:.0f}%" for k_, v in vc.items())
    return out


def report(res: pd.DataFrame, dedupe_days: int):
    res = dedupe(res.rename(columns={}), dedupe_days) if dedupe_days else res
    # 현행이 아직 안 끝난 신호는 비교에서 뺀다
    res = res[res['base_why'] != 'OPEN_MTM']
    print(f"\n신호 {len(res)}건 (같은 종목 {dedupe_days}일 내 재추천 제외, 현행 청산 확정분)")
    print(_line('현행(전체)', res['base_ret'].dropna(), res['base_bars'], res['base_why']))
    for m in METHODS[1:]:
        sub = res[res[f'{m}_ret'].notna() & (res[f'{m}_why'] != 'OPEN_MTM')]
        print(f"\n── {NAMES[m]} — 적용 가능 {len(sub)}건 (전체의 {len(sub) / len(res) * 100:.0f}%)")
        if m in ('elliott', 'fib', 'struct'):
            print(f"     목표까지 중앙 {sub[f'{m}_tgt_pct'].median():+.1f}% / 손절까지 중앙 {sub[f'{m}_stop_pct'].median():+.1f}%")
        print(_line('같은 신호 · 현행', sub['base_ret'], sub['base_bars'], sub['base_why']))
        print(_line(f'같은 신호 · {NAMES[m]}', sub[f'{m}_ret'], sub[f'{m}_bars'], sub[f'{m}_why']))
        d = (sub[f'{m}_ret'] - sub['base_ret']) * 100
        rng = np.random.default_rng(7)
        bs = [d.iloc[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)] if len(d) else [np.nan]
        print(f"     차이(방식-현행) 평균 {d.mean():+.2f}%p [90% {np.percentile(bs, 5):+.2f}~{np.percentile(bs, 95):+.2f}] · "
              f"방식이 나은 신호 {(d > 0).mean() * 100:.0f}%")
        for half, part in (('7월 전', sub[sub['datetime'] < '2026-07-01']), ('7월 후', sub[sub['datetime'] >= '2026-07-01'])):
            if len(part):
                dd = (part[f'{m}_ret'] - part['base_ret']).mean() * 100
                print(f"     {half}: n={len(part):<4} 승률 현행 {(part['base_ret'] > 0).mean() * 100:5.1f}% → "
                      f"{(part[f'{m}_ret'] > 0).mean() * 100:5.1f}% · 평균 차이 {dd:+.2f}%p")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--dedupe-days', type=int, default=5)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.report_only:
        res = pd.read_pickle(os.path.join(OUT_DIR, 'reco_exit.pkl'))
    else:
        engine = create_engine(DB_URL)
        reco = load_reco(engine)
        print(f"[reco] {len(reco)}건 / {reco['stock_code'].nunique()}종목", flush=True)
        res = evaluate(reco, engine)
    report(res, args.dedupe_days)


if __name__ == '__main__':
    main()
