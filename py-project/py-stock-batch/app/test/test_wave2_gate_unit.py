"""
실전 매수 게이트(2026-11-16) 단위 검증 — DB / KIS 불필요.

무엇을 검증하나
    1. universe_stats: 사전 필터 미달·봉 부족이면 None, 통과하면 vol20(로그수익 20개 표준편차)·above20(종가 > 20일 평균)
    2. gate_pool: 시장 폭 < 하한이면 그날 0건(쉼) / 이상이면 변동성 백분위 하한 이상만 남김
    3. 백분위가 pandas rank(pct=True) 와 같다(백테스트와 같은 정의)
    4. 모집단이 비면 게이트를 걸지 않는다(배치 일부 실패 시 매수가 멈추지 않게)
    5. 하한 0 은 끔(전부 통과)
    6. StockBuyCheckJob._select_top10 이 게이트 통과분만 거래량 배수 순으로 순위를 매긴다

실행
    poetry run python -m app.test.test_wave2_gate_unit
"""
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')
from stock_shared.strategy import wave2_breakout as W  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  ✓ ' if cond else '  ✗ ') + name + (f'  ({detail})' if detail and not cond else ''))


def bars(n=300, start=10000.0, drift=0.001, vol=0.02, volume=200000, seed=0):
    rng = np.random.default_rng(seed)
    c = start * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return pd.DataFrame({'open': c, 'high': c * 1.01, 'low': c * 0.99, 'close': c, 'volume': np.full(n, float(volume))})


def main():
    print('[1] universe_stats')
    df = bars()
    u = W.universe_stats(df, 10_000_000, False, '005930')
    exp_vol = float(pd.Series(np.log(df.close.to_numpy())).diff().rolling(20).std().iloc[-1])
    check('통과 종목은 값이 나온다', u is not None)
    check('vol20 = 최근 20개 로그수익 표준편차', u is not None and abs(u['vol20'] - exp_vol) < 1e-12, f"{u and u['vol20']} vs {exp_vol}")
    check('above20 = 종가 > 20일 평균', u is not None and u['above20'] == bool(df.close.iloc[-1] > df.close.iloc[-20:].mean()))
    check('봉 부족 → None', W.universe_stats(df.iloc[-100:], 10_000_000, False, '005930') is None)
    check('우선주(끝자리 0 아님) → None', W.universe_stats(df, 10_000_000, False, '005935') is None)
    check('관리·정지 → None', W.universe_stats(df, 10_000_000, True, '005930') is None)
    check('거래대금 미달 → None', W.universe_stats(bars(volume=100), 10_000_000, False, '005930') is None)
    check('시총 미달 → None', W.universe_stats(df, 1000, False, '005930') is None)

    print('[2] gate_pool')
    rng = np.random.default_rng(1)
    universe = [{'stock_code': f'{i:05d}0', 'vol20': float(v), 'above20': i % 2 == 0} for i, v in enumerate(rng.uniform(0.01, 0.06, 300))]
    pct = pd.Series([u['vol20'] for u in universe]).rank(pct=True).to_numpy()
    pool = [{'stock_code': universe[i]['stock_code'], 'vol20': universe[i]['vol20'], 'vol_ratio': 2 + i % 7} for i in range(0, 300, 7)]
    kept, info = W.gate_pool(pool, universe, 2 / 3, 0.40)
    want = {universe[i]['stock_code'] for i in range(0, 300, 7) if pct[i] >= 2 / 3}
    check('시장 폭 50% ≥ 40% → 쉬지 않음', not info['skipped_day'] and abs(info['breadth'] - 0.5) < 1e-9)
    check('변동성 백분위 2/3 이상만 남는다(pandas rank 와 같음)', {r['stock_code'] for r in kept} == want, f"{len(kept)} vs {len(want)}")
    check('남은 항목에 vol_pct 가 붙는다', all(abs(r['vol_pct'] - pct[int(r['stock_code'][:5])]) < 1e-12 for r in kept))
    weak = [{**u, 'above20': i % 10 < 3} for i, u in enumerate(universe)]
    kept2, info2 = W.gate_pool(pool, weak, 2 / 3, 0.40)
    check('시장 폭 30% < 40% → 그날 0건(쉼)', kept2 == [] and info2['skipped_day'])
    kept3, info3 = W.gate_pool(pool, [], 2 / 3, 0.40)
    check('모집단 없으면 게이트 생략(전부 통과)', len(kept3) == len(pool) and info3['breadth'] is None)
    kept4, _ = W.gate_pool(pool, weak, 0.0, 0.0)
    check('하한 0·0 이면 끔(전부 통과)', len(kept4) == len(pool))
    kept5, _ = W.gate_pool([{'stock_code': 'X', 'vol20': None, 'vol_ratio': 9}], universe, 0.0, 0.0)
    check('vol20 없는 신호는 뺀다', kept5 == [])

    print('[3] StockBuyCheckJob._select_top10')
    from app.batches.jobs.StockBuyCheckJob import StockBuyCheckJob
    job = StockBuyCheckJob.__new__(StockBuyCheckJob)
    job._buy_rank_mode = lambda: 'WAVE2'
    job._setting_float = lambda code, default: default
    base = {'stock_name': 'n', 'close': 1.0, 'proba': 0.5, 'action_type': 'HOLD', 'today_stock': {}, 'indicator': {}, 'chart_data': []}
    p2 = [{**base, **r} for r in pool]
    top = job._select_top10([], p2, '20261116', universe)
    exp = sorted([r for r in p2 if r['stock_code'] in want], key=lambda r: (-r['vol_ratio'], r['stock_code']))[:10]
    check('게이트 통과분만 거래량 배수 순 1~10위', [t['stock_code'] for t in top] == [r['stock_code'] for r in exp]
          and [t['composite_rank_no'] for t in top] == list(range(1, len(exp) + 1)))
    check('시장 폭 미달이면 순위 0건(MOMENTUM 폴백 안 함)', job._select_top10([], p2, '20261116', weak) == [])

    print(f'\n통과 {len(PASS)} · 실패 {len(FAIL)}')
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
