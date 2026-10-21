"""
bt_reco_history.py — 실제 매수추천 이력(trade_buy_target_stock)에 차트 분석 조건을 붙여 항목별 가중치를 추정한다.

bt_reco_chart_analysis.py 는 과거 추천을 "재현"해야 해서 전 종목 일봉이 필요하다. 여기서는 실제로 추천된
(날짜, 종목)을 그대로 쓰므로 그 종목들의 일봉만 있으면 된다(stock_ohlcv_daily — 배치가 채움).

절차
    1) 추천 행마다 그 종목 일봉(stock_ohlcv_daily) → KisService.compute_indicator_df(라이브와 같은 함수)
    2) 추천일 D 까지의 봉만으로 stock_shared.chart_analysis 를 다시 계산 → 항목값(아래 FEATURES)
    3) eval_shape_proba.run_one_trade — D+1 시가 진입, KospiStrategy1 매도, 왕복 수수료
       아직 청산 안 된(OPEN_MTM) 최근 신호는 결과가 확정되지 않아 뺀다.
    4) 항목별 단순 비교(해당/비해당 승률) + 전 항목 동시 로지스틱 회귀(L2) 계수
       기간을 앞/뒤로 나눠 같은 방향인지 본다.

항목 정의(부호 있는 0/1 더미 — 같은 축의 상태를 쪼개 둔다. 예: 피보 매도 쪽이라도 "반등 대기"와
"매도 구간 위로 돌파"는 뜻이 반대라 따로 본다)

사용
    poetry run python -m app.test.bt_reco_history
    poetry run python -m app.test.bt_reco_history --split 2026-07-01
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService
from app.test.eval_shape_proba import DB_URL, _base_user_info, run_one_trade, _wilson
from app.test.bt_reco_chart_analysis import load_bars, flatten, ANALYSIS_BARS, VIEW_BARS
from stock_shared import chart_analysis
from stock_shared.strategy.kospi1 import KospiStrategy1

OUT_DIR = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')

FEATURES = {
    # 추세 구조
    'struct_up':        lambda f: f['struct_trend'] == 'up',
    'struct_down':      lambda f: f['struct_trend'] == 'down',
    # 엘리엇 종합
    'el_up':            lambda f: f['el_label'] == '상승 우세',
    'el_down':          lambda f: f['el_label'] == '하락 우세',
    'el_unan_down':     lambda f: bool(f['el_unan_down']),
    'el_primary_up':    lambda f: f['el_primary_bias'] == 'up',
    # 피보나치 — 같은 쪽이라도 상태별로 쪼갠다
    'fib_buy_zone':     lambda f: f['fib_side'] == 'buy' and f['fib_status'] == 'in_zone',
    'fib_buy_wait':     lambda f: f['fib_side'] == 'buy' and f['fib_status'] == 'waiting',
    'fib_buy_broken':   lambda f: f['fib_side'] == 'buy' and f['fib_status'] in ('stopped', 'invalid'),
    'fib_sell_leg':     lambda f: f['fib_side'] == 'sell' and f['fib_status'] in ('waiting', 'in_zone'),
    'fib_sell_broken':  lambda f: f['fib_side'] == 'sell' and f['fib_status'] in ('stopped', 'invalid'),
    # 패턴 — 확정과 대기를 나눈다
    'pat_bull_conf':    lambda f: f['pat_dbl_bottom'] == 'triggered' or f['pat_abcd_bull'] == 'triggered',
    'pat_bull_wait':    lambda f: f['pat_dbl_bottom'] in ('forming', 'waiting') or f['pat_abcd_bull'] == 'waiting',
    'pat_bear_conf':    lambda f: f['pat_dbl_top'] == 'triggered' or f['pat_abcd_bear'] == 'triggered',
    'pat_bear_wait':    lambda f: f['pat_dbl_top'] in ('forming', 'waiting') or f['pat_abcd_bear'] == 'waiting',
    # 다이버전스(최근 10봉)
    'div_bull':         lambda f: bool(f['div_bull_recent']),
    'div_bear':         lambda f: bool(f['div_bear_recent']),
}

LABELS = {
    'struct_up': '추세 구조 상승', 'struct_down': '추세 구조 하락',
    'el_up': '엘리엇 상승 우세', 'el_down': '엘리엇 하락 우세', 'el_unan_down': '엘리엇 전부 하락',
    'el_primary_up': '주요 해석 다음 상승',
    'fib_buy_zone': '피보 매수 구간 진입', 'fib_buy_wait': '피보 눌림 대기', 'fib_buy_broken': '피보 매수 손절 이탈',
    'fib_sell_leg': '피보 하락 파동 반등 중', 'fib_sell_broken': '피보 매도 구간 위로 돌파',
    'pat_bull_conf': '상승 패턴 확정', 'pat_bull_wait': '상승 패턴 대기',
    'pat_bear_conf': '하락 패턴 확정', 'pat_bear_wait': '하락 패턴 대기',
    'div_bull': '최근 상승 다이버전스', 'div_bear': '최근 하락 다이버전스',
}


def load_reco(engine) -> pd.DataFrame:
    df = pd.read_sql(text(
        "SELECT t.ymd, t.stock_code, t.stock_name, t.rank_no, t.composite_rank_no, t.shape_proba "
        "FROM trade_buy_target_stock t "
        "JOIN stock_ohlcv_daily_state s ON s.stock_code = t.stock_code AND s.bar_cnt > 0 "
        "ORDER BY t.ymd, t.stock_code"), engine)
    df['datetime'] = pd.to_datetime(df['ymd']).dt.strftime('%Y-%m-%d')
    df['path'] = np.where(df['composite_rank_no'].notna(), 'composite', 'watch')
    return df.drop_duplicates(['datetime', 'stock_code'])


def evaluate(reco: pd.DataFrame, engine) -> pd.DataFrame:
    strategy = KospiStrategy1()
    rows, skipped = [], {'no_bars': 0, 'no_date': 0, 'no_trade': 0}
    codes = reco['stock_code'].unique()
    for n, code in enumerate(codes, 1):
        bars = load_bars('db', code, engine)
        if bars is None or len(bars) < 60:
            skipped['no_bars'] += 1
            continue
        computed = KisService().compute_indicator_df(bars.copy(), user_info=_base_user_info())
        computed['coin'] = code
        computed['datetime'] = computed['datetime'].astype(str).str[:10]
        recs = computed.to_dict('records')
        dates_idx = {d: k for k, d in enumerate(computed['datetime'])}
        ohlc = computed[['datetime', 'open', 'high', 'low', 'close']].rename(columns={'datetime': 'ymd'})
        for _, rk in reco[reco['stock_code'] == code].iterrows():
            i = dates_idx.get(rk['datetime'])
            if i is None:
                skipped['no_date'] += 1
                continue
            trade = run_one_trade(strategy, recs, i, None)
            if not trade:
                skipped['no_trade'] += 1
                continue
            full = ohlc.iloc[max(0, i - ANALYSIS_BARS + 1): i + 1]
            ctx = chart_analysis.Context(full, VIEW_BARS)
            a = {name: fn(ctx) for name, fn in chart_analysis.MODULES.items() if name not in ('swing', 'rsi')}
            row = {**rk.to_dict(), 'ret_net': trade['ret_net'], 'reason': trade['reason'],
                   'bars_held': trade['bars_held']}
            row.update(flatten(a, ctx, dates_idx, i))
            rows.append(row)
        if n % 50 == 0 or n == len(codes):
            print(f"[eval] 종목 {n}/{len(codes)} · 신호 {len(rows)}", flush=True)
    print(f"[eval] 제외: {skipped}", flush=True)
    res = pd.DataFrame(rows)
    for k, fn in FEATURES.items():
        res[k] = res.apply(fn, axis=1).astype(int)
    res.to_pickle(os.path.join(OUT_DIR, 'reco_history.pkl'))
    res.to_csv(os.path.join(OUT_DIR, 'reco_history.csv'), index=False)
    return res


def _fit(df: pd.DataFrame, C: float):
    from sklearn.linear_model import LogisticRegression
    X, y = df[list(FEATURES)].values, (df['ret_net'] > 0).astype(int).values
    if len(np.unique(y)) < 2:
        return None
    return LogisticRegression(C=C, max_iter=2000).fit(X, y).coef_[0]


def dedupe(res: pd.DataFrame, days: int) -> pd.DataFrame:
    """같은 종목이 days 일(캘린더) 안에 다시 추천되면 첫 건만 남긴다 — 연속 추천은 결과가 겹친 같은 표본이다."""
    if days <= 0:
        return res
    keep = []
    for _, g in res.sort_values('datetime').groupby('stock_code', sort=False):
        last = None
        for idx, d in zip(g.index, pd.to_datetime(g['datetime'])):
            if last is None or (d - last).days > days:
                keep.append(idx)
                last = d
    return res.loc[sorted(keep)]


def report(res: pd.DataFrame, split: str, C: float, boot: int, dedupe_days: int = 0):
    res = res[res['reason'] != 'OPEN_MTM'].copy()
    n0 = len(res)
    res = dedupe(res, dedupe_days)
    if dedupe_days:
        print(f"[dedupe] 같은 종목 {dedupe_days}일 내 재추천 제외: {n0} → {len(res)}건", flush=True)
    first, second = res[res['datetime'] < split], res[res['datetime'] >= split]

    def wr(s):
        return (s > 0).mean() * 100 if len(s) else float('nan')

    print(f"\n신호 {len(res)}건 (청산 확정분) · 앞 {len(first)}건 / 뒤 {len(second)}건 (기준 {split})")
    for name, sub in (('전체', res), ('composite 경로', res[res['path'] == 'composite']),
                      ('watch 경로', res[res['path'] == 'watch'])):
        lo, hi = _wilson(int((sub['ret_net'] > 0).sum()), len(sub)) if len(sub) else (0, 0)
        print(f"  {name:<14} n={len(sub):<5} 승률 {wr(sub['ret_net']):5.1f}% [{lo:4.1f}~{hi:4.1f}]  "
              f"평균 {sub['ret_net'].mean() * 100:+.2f}%")

    print("\n── 항목별 단순 비교: 해당 / 비해당 승률(%) · 평균수익(%) · 해당 건수 — 앞 | 뒤")
    for k in FEATURES:
        cells = []
        for part in (first, second):
            on, off = part[part[k] == 1]['ret_net'], part[part[k] == 0]['ret_net']
            cells.append(f"{wr(on):5.1f}/{wr(off):5.1f}  {on.mean() * 100 if len(on) else float('nan'):+6.2f}  n={len(on):<4}")
        print(f"  {LABELS[k]:<18} {cells[0]} | {cells[1]}")

    # 전 항목 동시 로지스틱 — 겹치는 항목(엘리엇·구조 등)은 서로 나눠 가진다
    coef_all = _fit(res, C)
    coef_a, coef_b = _fit(first, C), _fit(second, C)
    # 종목 단위 부트스트랩 — 같은 종목 신호끼리 결과가 닮아 있으니 종목을 통째로 뽑는다
    rng = np.random.default_rng(7)
    groups = [g for _, g in res.groupby('stock_code')]
    boots = []
    for _ in range(boot):
        smp = pd.concat([groups[k] for k in rng.integers(0, len(groups), len(groups))])
        c = _fit(smp, C)
        if c is not None:
            boots.append(c)
    boots = np.array(boots)
    print(f"\n── 로지스틱 회귀 계수(승리 확률, L2 C={C}) — 전체 [부트스트랩 90% 구간] · 앞 · 뒤")
    order = np.argsort(-np.abs(coef_all))
    for j in order:
        k = list(FEATURES)[j]
        lo, hi = np.percentile(boots[:, j], [5, 95]) if len(boots) else (np.nan, np.nan)
        same = (coef_a is not None and coef_b is not None and np.sign(coef_a[j]) == np.sign(coef_b[j]))
        sure = lo > 0 or hi < 0
        mark = '★' if same and sure else ('·' if same else ' ')
        print(f"  {mark} {LABELS[k]:<18} {coef_all[j]:+.3f} [{lo:+.2f}~{hi:+.2f}]  "
              f"앞 {coef_a[j] if coef_a is not None else float('nan'):+.3f}  뒤 {coef_b[j] if coef_b is not None else float('nan'):+.3f}  "
              f"(해당 {int(res[k].sum())}건)")
    print("\n★ = 앞·뒤 기간 부호가 같고 90% 구간이 0 을 포함하지 않음(채택 후보). · = 부호만 같음.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', default='2026-07-01', help='앞/뒤 기간 나누는 날짜')
    ap.add_argument('--C', type=float, default=0.5, help='로지스틱 L2 강도(작을수록 0 쪽으로 강하게 줄임)')
    ap.add_argument('--boot', type=int, default=300)
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--dedupe-days', type=int, default=5, help='같은 종목 재추천을 묶는 일수(0=끔)')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    if args.report_only:
        res = pd.read_pickle(os.path.join(OUT_DIR, 'reco_history.pkl'))
    else:
        engine = create_engine(DB_URL)
        reco = load_reco(engine)
        print(f"[reco] 일봉 있는 추천 {len(reco)}건 / {reco['stock_code'].nunique()}종목 "
              f"({reco['datetime'].min()} ~ {reco['datetime'].max()})", flush=True)
        res = evaluate(reco, engine)
    report(res, args.split, args.C, args.boot, args.dedupe_days)


if __name__ == '__main__':
    main()
