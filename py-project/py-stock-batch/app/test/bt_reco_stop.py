"""
bt_reco_stop.py — 손절 체결 방식에 따라 실제 손실이 얼마나 달라지나.

배경
    eval_shape_proba.run_one_trade(지금까지 백테스트 표준)는 KospiStrategy1.get_action_in_active 를
    **종가로** 판정하고 **다음 날 시가**에 판다. 그런데 이 판정의 손절 조건은
        종가 <= 진입가 × 0.95  AND  종가가 20일선 아래
    라서 20일선 위면 -5% 를 넘어도 버티고, 손절이 나도 갭하락을 그대로 맞는다.
    반면 실전 워커(M1, modes/mode_1/sell_executor1.hit_line)는 **장중 체결가**가
    stop_price(진입가 × 0.95, 20일선 예외 없음)에 닿는 즉시 판다. 익절(+30%)·트레일도 장중.
    일봉 신호(타임스탑 등)만 개장 루틴에서 처리한다.

비교 (같은 추천 신호, 매수는 모두 D+1 시가)
    bt_close    : 현행 백테스트 — 종가 판정(20일선 예외 포함) → 다음 날 시가 체결
    bt_noema    : 종가 판정이되 20일선 예외 없음 → 다음 날 시가 체결 (예외만의 효과 분리)
    live_intra  : 실전 워커와 같은 방식 — 손절·익절·트레일은 봉 안에서 그 가격에 체결
                  (시가가 이미 넘어 있으면 시가), 나머지 일봉 신호는 다음 날 시가
    봉 안에서 손절과 익절/트레일이 둘 다 닿으면 손절이 먼저(라이브 hit_line 순서와 같음).

사용
    poetry run python -m app.test.bt_reco_stop
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService
from app.test.eval_shape_proba import DB_URL, FEE_RATE, SELL_ACTIONS, _base_user_info, run_one_trade, _wilson
from app.test.bt_reco_chart_analysis import load_bars
from app.test.bt_reco_history import load_reco, dedupe
from stock_shared.strategy.base import Action
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.vo.userCoinInfo import UserCoinInfo

OUT_DIR = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
INTRADAY = {Action.SELL_STOP_LOSS, Action.SELL_PROFIT, Action.SELL_TRAIL}   # 라이브가 장중에 처리하는 것
METHODS = {'bt_close': '현행 백테스트(종가·20일선 예외·익일 시가)',
           'bt_noema': '종가 판정·예외 없음·익일 시가',
           'live_intra': '실전 방식(장중 -5% 즉시)'}


def _ui(entry, er):
    ui = _base_user_info()
    ui.has_position = True
    ui.avg_price = ui.entry_price = entry
    ui.entry_atr = float(er['atr'] or 0)
    ui.peak_high = float(er['high'] or entry)
    ui.peak_close = float(er['close'] or entry)
    return ui


def _done(entry, px, why, held):
    return {'ret_net': (px - entry) / entry - 2 * FEE_RATE, 'reason': why, 'bars_held': held}


def sim_close_noema(strategy, recs, i_sig):
    """종가 -5% 면 20일선과 무관하게 손절(익일 시가). 그 외는 현행 판정 그대로."""
    if i_sig + 1 >= len(recs):
        return None
    er = recs[i_sig + 1]
    entry = float(er['open'] or 0)
    if entry <= 0:
        return None
    ui = _ui(entry, er)
    stop = entry * (1 - strategy.stop_loss_pct)
    for i in range(i_sig + 1, len(recs)):
        r, prev_r = recs[i], recs[i - 1]
        prev_peak = ui.peak_high
        ui.peak_high = max(ui.peak_high, float(r['high'] or 0))
        ui.peak_close = max(ui.peak_close, float(r['close'] or 0))
        ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
        ui.bars_held += 1
        action = Action.SELL_STOP_LOSS if float(r['close']) <= stop else None
        if action is None:
            ra = (strategy.get_action_in_active(UserCoinInfo.from_dict(prev_r), UserCoinInfo.from_dict(r), ui)
                  or {}).get('result_action')
            action = ra if ra in SELL_ACTIONS else None
        if action is not None:
            if i + 1 < len(recs):
                return _done(entry, float(recs[i + 1]['open'] or recs[i + 1]['close']), action.name, i - i_sig)
            return _done(entry, float(r['close']), action.name, i - i_sig)
    return _done(entry, float(recs[-1]['close']), 'OPEN_MTM', len(recs) - 1 - i_sig)


def sim_live(strategy, recs, i_sig, take: float = None):
    """실전 워커 근사: 손절·익절·트레일 라인은 봉 안에서, 일봉 신호는 다음 날 시가.

    take: 추가 익절가(예: 엘리엇 목표). 주어지면 +30% 익절선과 둘 중 낮은 쪽에서 판다(사유 TAKE).
    """
    if i_sig + 1 >= len(recs):
        return None
    er = recs[i_sig + 1]
    entry = float(er['open'] or 0)
    if entry <= 0:
        return None
    ui = _ui(entry, er)
    stop = entry * (1 - strategy.stop_loss_pct)
    target = entry * (1 + strategy.take_profit_pct)
    peak = entry
    for i in range(i_sig + 1, len(recs)):
        r, prev_r = recs[i], recs[i - 1]
        o, h, l = float(r['open']), float(r['high']), float(r['low'])
        first = i == i_sig + 1
        # 트레일 라인은 직전 봉까지의 고점으로(봉 안에서 고점·저점 순서를 모르므로 보수적으로)
        atr = float(r['atr'] or ui.entry_atr or 0)
        trail = None
        if strategy.use_trailing and (peak - entry) / entry >= strategy.trail_activate_pct:
            trail, _ = strategy._trail_line_of(entry, peak, atr)
        if l <= stop:
            return _done(entry, stop if first else min(o, stop), 'SELL_STOP_LOSS', i - i_sig)
        if take is not None and take < target and h >= take:
            return _done(entry, take if first else max(o, take), 'TAKE', i - i_sig)
        if h >= target:
            return _done(entry, target if first else max(o, target), 'SELL_PROFIT', i - i_sig)
        if trail is not None and l <= trail:
            return _done(entry, min(o, trail), 'SELL_TRAIL', i - i_sig)
        # 일봉 신호(타임스탑 등) — 종가로 판정, 다음 날 시가
        peak = max(peak, h)
        prev_peak = ui.peak_high
        ui.peak_high = max(ui.peak_high, h)
        ui.peak_close = max(ui.peak_close, float(r['close'] or 0))
        ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
        ui.bars_held += 1
        ra = (strategy.get_action_in_active(UserCoinInfo.from_dict(prev_r), UserCoinInfo.from_dict(r), ui)
              or {}).get('result_action')
        if ra in SELL_ACTIONS and ra not in INTRADAY:
            if i + 1 < len(recs):
                return _done(entry, float(recs[i + 1]['open'] or recs[i + 1]['close']), ra.name, i - i_sig)
            return _done(entry, float(r['close']), ra.name, i - i_sig)
    return _done(entry, float(recs[-1]['close']), 'OPEN_MTM', len(recs) - 1 - i_sig)


def evaluate(reco, engine) -> pd.DataFrame:
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
        for _, rk in reco[reco['stock_code'] == code].iterrows():
            i = dates_idx.get(rk['datetime'])
            if i is None or i + 1 >= len(recs):
                continue
            out = {'bt_close': run_one_trade(strategy, recs, i, None),
                   'bt_noema': sim_close_noema(strategy, recs, i),
                   'live_intra': sim_live(strategy, recs, i)}
            row = {'datetime': rk['datetime'], 'stock_code': code, 'path': rk['path']}
            for m, t in out.items():
                row[f'{m}_ret'] = t['ret_net'] if t else np.nan
                row[f'{m}_why'] = t['reason'] if t else None
                row[f'{m}_bars'] = t['bars_held'] if t else np.nan
            rows.append(row)
        if n % 100 == 0 or n == len(codes):
            print(f"[eval] 종목 {n}/{len(codes)} · 신호 {len(rows)}", flush=True)
    res = pd.DataFrame(rows)
    res.to_pickle(os.path.join(OUT_DIR, 'reco_stop.pkl'))
    return res


def report(res, dedupe_days):
    res = dedupe(res, dedupe_days)
    done = res[[f'{m}_why' for m in METHODS]].ne('OPEN_MTM').all(axis=1) & res[[f'{m}_ret' for m in METHODS]].notna().all(axis=1)
    res = res[done]
    print(f"\n신호 {len(res)}건 (세 방식 모두 청산 확정, 같은 종목 {dedupe_days}일 내 재추천 제외)\n")
    print(f"{'방식':<34}{'승률':>7}{'평균':>8}{'중앙':>8}{'하위10%':>9}{'최악':>8}{'-10%↓':>8}{'보유':>6}")
    for m, name in METHODS.items():
        x = res[f'{m}_ret'] * 100
        k = int((x > 0).sum())
        print(f"{name:<34}{k / len(x) * 100:>6.1f}%{x.mean():>+8.2f}{x.median():>+8.2f}"
              f"{np.percentile(x, 10):>+9.2f}{x.min():>+8.1f}{(x < -10).mean() * 100:>7.1f}%{res[f'{m}_bars'].mean():>6.1f}")
    for m, name in METHODS.items():
        vc = res[f'{m}_why'].value_counts(normalize=True) * 100
        sl = res[res[f'{m}_why'] == 'SELL_STOP_LOSS'][f'{m}_ret'] * 100
        print(f"\n  {name}: " + ' '.join(f"{k}{v:.0f}%" for k, v in vc.items()))
        if len(sl):
            print(f"    손절로 끝난 매매 {len(sl)}건 — 평균 {sl.mean():+.2f}% · 중앙 {sl.median():+.2f}% · 최악 {sl.min():+.1f}%")
    d = (res['live_intra_ret'] - res['bt_close_ret']) * 100
    rng = np.random.default_rng(7)
    bs = [d.iloc[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    print(f"\n실전 방식 - 현행 백테스트: 평균 {d.mean():+.2f}%p [90% {np.percentile(bs, 5):+.2f}~{np.percentile(bs, 95):+.2f}]")
    for half, part in (('7월 전', res[res['datetime'] < '2026-07-01']), ('7월 후', res[res['datetime'] >= '2026-07-01'])):
        print(f"  {half} n={len(part)}: " + ' · '.join(
            f"{m} 승률 {(part[f'{m}_ret'] > 0).mean() * 100:.1f}% 평균 {part[f'{m}_ret'].mean() * 100:+.2f}%" for m in METHODS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--dedupe-days', type=int, default=5)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.report_only:
        res = pd.read_pickle(os.path.join(OUT_DIR, 'reco_stop.pkl'))
    else:
        engine = create_engine(DB_URL)
        reco = load_reco(engine)
        print(f"[reco] {len(reco)}건 / {reco['stock_code'].nunique()}종목", flush=True)
        res = evaluate(reco, engine)
    report(res, args.dedupe_days)


if __name__ == '__main__':
    main()
