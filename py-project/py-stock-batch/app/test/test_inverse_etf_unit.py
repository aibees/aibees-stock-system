"""
매수타겟 배치 인버스 ETF 추가(2026-11-17) 단위 검증 — DB / KIS 불필요.

무엇을 검증하나
    1. pick_inverse_etfs — 주식 인버스만(달러·채권·원자재 제외), 원래 배치 목록에 있던 코드는 다시 안 더함, 표시 키 붙음
    2. _inverse_etf_targets — 공통코드 INVERSE_ETF=N 이면 끔, INVERSE_ETF_EXCLUDE 로 제외 낱말 바꿈, 조회 실패해도 빈 목록
    3. _process_chunk — 추가 인버스 ETF 는 2파 후보(vol20 포함)에는 들어가고, 실전 게이트 모집단(univ_rows)·
       shape 학습셋(train_rows)에는 안 들어간다. 원래 종목은 예전과 똑같이 모집단·학습셋에 들어간다.

실행
    poetry run python -m app.test.test_inverse_etf_unit
"""
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.batches.jobs import StockBuyCheckJob as SJ
from app.common.constants.Literal import Literal
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  PASS ' if cond else '  FAIL ') + name + (f'  -- {detail}' if detail and not cond else ''))


ROWS = [
    {'stock_code': '114800', 'stock_name': 'KODEX 인버스'},                 # 원래 목록에 있음
    {'stock_code': '252670', 'stock_name': 'KODEX 200선물인버스2X'},
    {'stock_code': '251340', 'stock_name': 'KODEX 코스닥150선물인버스'},
    {'stock_code': '409810', 'stock_name': 'KODEX 미국나스닥100선물인버스(H)'},
    {'stock_code': '0193L0', 'stock_name': 'PLUS 삼성전자선물단일종목인버스2X'},
    {'stock_code': '465350', 'stock_name': 'RISE 2차전지TOP10인버스(합성)'},
    {'stock_code': '261270', 'stock_name': 'KODEX 미국달러선물인버스'},
    {'stock_code': '176950', 'stock_name': 'KODEX 국채선물10년인버스'},
    {'stock_code': '282000', 'stock_name': 'RISE 국고채3년선물인버스'},
    {'stock_code': '271050', 'stock_name': 'KODEX WTI원유선물인버스(H)'},
    {'stock_code': '280940', 'stock_name': 'KODEX 골드선물인버스(H)'},
    {'stock_code': '334700', 'stock_name': 'RISE 팔라듐선물인버스(H)'},
    {'stock_code': '069500', 'stock_name': 'KODEX 200'},                      # 인버스 아님
]
DEFAULT_EXCL = SJ.INVERSE_ETF_DEFAULT and SJ.INVERSE_ETF_EXCLUDE_DEFAULT.split(',')


def test_pick():
    print('\n[1] pick_inverse_etfs')
    got = SJ.pick_inverse_etfs(ROWS, DEFAULT_EXCL, {'114800', '005930'})
    codes = [r['stock_code'] for r in got]
    check('주식 인버스 5개만', codes == ['252670', '251340', '409810', '0193L0', '465350'], codes)
    check('원래 목록 코드(114800)는 안 더함', '114800' not in codes)
    check('달러·국채·국고채·원유·골드·팔라듐 제외',
          not {'261270', '176950', '282000', '271050', '280940', '334700'} & set(codes))
    check('표시 키 붙음', all(r.get(SJ.INVERSE_ADDED_KEY) is True for r in got))
    check('원본 행은 안 바뀜', SJ.INVERSE_ADDED_KEY not in ROWS[1])
    got2 = SJ.pick_inverse_etfs(ROWS, ['원유'], set())
    check('제외 낱말을 바꾸면 그대로 따름(원유만 제외 → 달러·채권 포함)',
          '261270' in [r['stock_code'] for r in got2] and '271050' not in [r['stock_code'] for r in got2])


class _Res:
    def __init__(self, v):
        self.v = v

    def first(self):
        return None if self.v is None else (self.v,)


class FakeSession:
    def __init__(self, settings):
        self.settings = settings

    def execute(self, stmt, params=None):
        return _Res(self.settings.get((params or {}).get('c')))


def _job(settings, rows=ROWS, fail=False):
    job = object.__new__(SJ.StockBuyCheckJob)
    job.session = FakeSession(settings)

    def _get(session):
        if fail:
            raise RuntimeError('db')
        return list(rows)
    job.stockServiceImpl = SimpleNamespace(get_inverse_etf_list=_get)
    return job


def test_targets():
    print('\n[2] _inverse_etf_targets (공통코드)')
    base = [{'stock_code': '114800'}, {'stock_code': '005930'}]
    check('공통코드 없음 → 기본 켬, 5종목', len(_job({})._inverse_etf_targets(base)) == 5)
    check('INVERSE_ETF=N → 끔', _job({'INVERSE_ETF': 'N'})._inverse_etf_targets(base) == [])
    check('INVERSE_ETF=y(소문자) → 켬', len(_job({'INVERSE_ETF': 'y'})._inverse_etf_targets(base)) == 5)
    got = _job({'INVERSE_ETF_EXCLUDE': '원유, 골드'})._inverse_etf_targets(base)
    check('INVERSE_ETF_EXCLUDE 로 제외 낱말 교체(공백 무시)',
          '261270' in [r['stock_code'] for r in got] and '280940' not in [r['stock_code'] for r in got])
    check('목록 조회 실패 → 빈 목록(배치는 계속)', _job({}, fail=True)._inverse_etf_targets(base) == [])


# ── 3. _process_chunk ──────────────────────────────────────────────────────
def _bars(n=300, seed=0):
    rng = np.random.default_rng(seed)
    c = 10000 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    d = pd.date_range('2025-08-01', periods=n, freq='B')
    return pd.DataFrame({'datetime': d, 'open': c, 'high': c * 1.01, 'low': c * 0.99, 'close': c,
                         'volume': np.full(n, 300000.0)})


class FakeKisService:
    def compute_indicator_df(self, ohlcv, user_info=None):
        df = ohlcv.copy()
        for col in SHAPE_FEATURE_COLUMNS:
            df[col] = 0.1
        df[Literal.EMA_20] = df['close'].rolling(20, min_periods=1).mean()
        df[Literal.EMA_120] = df['close'].rolling(120, min_periods=1).mean()
        df[Literal.ATR] = df['close'] * 0.03
        return df


class FakeStrategy:
    def get_result_with_action(self, trade_data, meta):
        return {'action_type': 'HOLD', 'todayStock': {}, 'indicator': {}}


class FakeEngine:
    def get_daily_ohlcv(self, code, start, end, min_days=0):
        return _bars(seed=int(code[:3], 36) % 97)


def test_process_chunk():
    print('\n[3] _process_chunk — 모집단·학습셋 제외, 후보는 그대로')
    saved = (SJ.time, SJ.KisService, SJ.shape_score, SJ.wave2_breakout, SJ.StockBuyCheckJob._make_strategy)
    try:
        SJ.time = SimpleNamespace(sleep=lambda s: None)
        SJ.KisService = FakeKisService
        SJ.shape_score = lambda feats: 0.5
        SJ.wave2_breakout = SimpleNamespace(
            today_signal=lambda ohlcv, shares, bad, code: {'vol_ratio': 3.0, 'retr': 0.5, 'to_h1': 0.1},
            universe_stats=lambda ohlcv, shares, bad, code: {'vol20': 0.03, 'above20': True},
        )
        SJ.StockBuyCheckJob._make_strategy = staticmethod(lambda p: FakeStrategy())
        job = object.__new__(SJ.StockBuyCheckJob)
        chunk = [
            {'stock_code': '005930', 'stock_name': '삼성전자', 'listed_shares': 1e9},
            {'stock_code': '114800', 'stock_name': 'KODEX 인버스', 'listed_shares': 6e8},   # 원래 목록의 ETF
            {'stock_code': '252670', 'stock_name': 'KODEX 200선물인버스2X', 'listed_shares': 7e9,
             SJ.INVERSE_ADDED_KEY: True},
        ]
        meta = SimpleNamespace(vol_limit=0)
        results, comp, train, w2, univ = job._process_chunk(None, FakeEngine(), chunk, 'KOSPI_1', meta,
                                                            '2025-01-01', '2026-11-17', '20261117')
    finally:
        (SJ.time, SJ.KisService, SJ.shape_score, SJ.wave2_breakout) = saved[:4]
        SJ.StockBuyCheckJob._make_strategy = saved[4]
    univ_codes = [u['stock_code'] for u in univ]
    train_codes = [t['coin'] for t in train]
    w2_codes = [w['stock_code'] for w in w2]
    check('모집단 = 원래 종목만(005930·114800)', univ_codes == ['005930', '114800'], univ_codes)
    check('학습셋 = 원래 종목만', train_codes == ['005930', '114800'], train_codes)
    check('2파 후보에는 추가 인버스 포함', w2_codes == ['005930', '114800', '252670'], w2_codes)
    check('추가 인버스 후보도 vol20 있음(게이트 백분위 판정 가능)',
          next(w for w in w2 if w['stock_code'] == '252670')['vol20'] == 0.03)


if __name__ == '__main__':
    test_pick()
    test_targets()
    test_process_chunk()
    print(f'\n결과: PASS {len(PASS)} / FAIL {len(FAIL)}')
    if FAIL:
        print('FAIL 목록:', FAIL)
        sys.exit(1)
    print('ALL PASS')
