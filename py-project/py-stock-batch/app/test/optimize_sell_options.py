"""
trade_buy_target_stock_test(오프라인 테스트 알고리즘 추천) 데이터를 고정하고,
KospiStrategy1 의 매도 옵션(손절/익절/트레일링/피보나치 되돌림/타임스탑)만
grid search 로 바꿔가며 시뮬레이션 → Profit Factor 기준 최적 조합을 찾는다.

전제:
  - 매수 판단(추천 종목/추천일)은 이미 trade_buy_target_stock_test 에 고정되어
    있다고 보고 건드리지 않는다. 여기서 바꾸는 건 오직 "언제 파느냐"뿐이다.
  - sim_buy_target.py 의 _simulate() 를 그대로 재사용한다(진입/체결 로직 동일).
  - candle 데이터는 sim_buy_target._candle_cache 에 캐시되어 조합 간 재사용된다
    (조합마다 DB 재조회하면 조합 수 * 88일치 쿼리라 너무 느려짐).

사용:
    poetry run python -m app.test.optimize_sell_options
    poetry run python -m app.test.optimize_sell_options --start 2026-04-01 --end 2026-08-07
    poetry run python -m app.test.optimize_sell_options --quick   # 벤치마크용 축소 그리드
"""
import itertools
import time

from app.test import sim_buy_target as sbt
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.strategy.backtester import KisBacktester

MIN_TRADES = 8  # 이보다 적으면 PF가 표본부족으로 왜곡되므로 순위 산정에서 제외


def _pf_key(pf):
    """profit_factor 정렬용 숫자 변환. 'inf'(손실 거래 0건)는 큰 상수로 취급."""
    return 999.0 if pf == 'inf' else float(pf)


def build_grid(quick: bool = False):
    """(라벨, kwargs dict) 튜플 리스트. kwargs 는 KospiStrategy1 인스턴스 속성명 기준."""
    if quick:
        stop_loss_list = [0.05, 0.08]
        take_profit_list = [0.20, 0.30]
        trail_activate_list = [0.08]
        k_trail_atr_list = [3.0]
        dd_dual_list = [(None, True), (0.05, True)]
        fib_list = [(False, 0.382), (True, 0.5)]
        timestop_list = [(12, 20, True, 0.02)]
    else:
        stop_loss_list = [0.04, 0.06, 0.08, 0.10]
        take_profit_list = [0.15, 0.20, 0.30]
        trail_activate_list = [0.05, 0.08]
        k_trail_atr_list = [2.0, 3.0, 4.0]
        # (trail_drawdown_pct, trail_dual) — dd=None이면 dual 여부 무의미하므로 1개만
        dd_dual_list = []
        for dd in (None, 0.03, 0.05, 0.08):
            for dual in ((True,) if dd is None else (True, False)):
                dd_dual_list.append((dd, dual))
        # (trail_fib_use, trail_fib_level) — use=False면 level 무의미하므로 1개만
        fib_list = [(False, 0.382)] + [(True, lv) for lv in (0.382, 0.5, 0.618)]
        # (max_hold_bars, max_hold_bars_hard, time_stop_extend, time_stop_band)
        timestop_list = [
            (10, 18, True, 0.02), (15, 23, True, 0.02),
            (20, 28, True, 0.02), (15, 23, False, 0.02),
        ]

    combos = []
    for sl, tp, ta, katr, (dd, dual), (fu, fl), (mhb, mhbh, ext, band) in itertools.product(
            stop_loss_list, take_profit_list, trail_activate_list, k_trail_atr_list,
            dd_dual_list, fib_list, timestop_list):
        label = (f"SL{sl:.0%}_TP{tp:.0%}_ACT{ta:.0%}_ATR{katr:.1f}_"
                 f"DD{'-' if dd is None else f'{dd:.0%}'}_DUAL{int(dual)}_"
                 f"FIB{'off' if not fu else f'{fl:.3f}'}_"
                 f"MHB{mhb}-{mhbh}{'ext' if ext else ''}")
        kwargs = dict(
            stop_loss_pct=sl, take_profit_pct=tp,
            trail_activate_pct=ta, k_trail_atr=katr,
            trail_drawdown_pct=dd, trail_dual=dual,
            trail_fib_use=fu, trail_fib_level=fl,
            max_hold_bars=mhb, max_hold_bars_hard=mhbh,
            time_stop_extend=ext, time_stop_band=band,
        )
        combos.append((label, kwargs))
    return combos


def run_grid(start: str, end: str, table: str = None, quick: bool = False, min_trades: int = MIN_TRADES):
    table = table or sbt.TABLE_TEST
    days = sbt._trading_days(start, end)
    if not days:
        print(f'거래일 데이터 없음: {start} ~ {end}')
        return []
    reco = sbt._reco_by_day(start, end, table=table)
    names = sbt._name_map(table=table)
    ui = sbt._user_info()

    combos = build_grid(quick=quick)
    print(f'조합 수: {len(combos)}  |  기간: {start} ~ {end} ({len(days)}거래일)  |  소스: {table}')

    results = []
    t0 = time.time()
    for i, (label, kwargs) in enumerate(combos, 1):
        strategy = KospiStrategy1()
        for k, v in kwargs.items():
            setattr(strategy, k, v)
        trades = sbt._simulate(strategy, ui, days, reco, names,
                                fee_rate=sbt.FEE_RATE, skip_gapup=sbt.SKIP_GAPUP)
        summary = KisBacktester(strategy=strategy)._summarize('SIM', trades)
        results.append({'label': label, **kwargs, **summary})
        if i % 500 == 0:
            elapsed = time.time() - t0
            print(f'  ...{i}/{len(combos)}  ({elapsed:.1f}s 경과, 조합당 {elapsed/i*1000:.1f}ms)')

    elapsed = time.time() - t0
    print(f'완료: {len(combos)}개 조합, {elapsed:.1f}초 (조합당 평균 {elapsed/len(combos)*1000:.1f}ms)')
    return results


def top_n(results: list, n: int = 15, metric: str = 'profit_factor', min_trades: int = MIN_TRADES):
    eligible = [r for r in results if r['trades'] >= min_trades]
    if not eligible:
        print(f'[경고] trades>={min_trades} 조건을 만족하는 조합이 없음 — min_trades를 낮추세요.')
        eligible = results
    ranked = sorted(eligible, key=lambda r: _pf_key(r[metric]), reverse=True)
    return ranked[:n]


def _print_top(ranked: list):
    print(f"\n{'순위':<4}{'PF':>7}{'승률%':>8}{'총수익%':>9}{'MDD%':>8}{'거래':>5}{'평균봉':>7}  라벨")
    print('-' * 100)
    for i, r in enumerate(ranked, 1):
        print(f"{i:<4}{str(r['profit_factor']):>7}{r['win_rate']:>8}{r['total_return']:>9}"
              f"{r['mdd']:>8}{r['trades']:>5}{r['avg_bars']:>7}  {r['label']}")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='매도 옵션 grid search (trade_buy_target_stock_test 기준)')
    ap.add_argument('--start', default='2026-04-01')
    ap.add_argument('--end', default='2026-08-07')
    ap.add_argument('--table', choices=['prod', 'test'], default='test')
    ap.add_argument('--quick', action='store_true', help='축소 그리드로 속도 벤치마크만')
    ap.add_argument('--min-trades', type=int, default=MIN_TRADES)
    ap.add_argument('--top', type=int, default=15)
    args = ap.parse_args()

    table = sbt.TABLE_PROD if args.table == 'prod' else sbt.TABLE_TEST
    results = run_grid(args.start, args.end, table=table, quick=args.quick, min_trades=args.min_trades)
    if results:
        ranked = top_n(results, n=args.top, min_trades=args.min_trades)
        _print_top(ranked)
