"""
매수추천 알고리즘별 행 합치기·단계 구성·권한별 가공 단위 검증 — DB 불필요.

실행
    cd py-project/py-naver-stock-theme
    PYTHONPATH=. python -m app.test.test_reco_level_unit

stock_shared 패키지는 import 시 SQLAlchemy 를 끌어오므로, DB 가 없는 환경에서도 돌 수 있게
reco_algo.py(순수 파이썬)만 파일 경로로 직접 올린다.
"""
import importlib.util
import pathlib
import sys
import types

_SHARED = pathlib.Path(__file__).resolve().parents[3] / 'shared' / 'stock_shared' / 'reco_algo.py'
if 'stock_shared.reco_algo' not in sys.modules:
    try:
        import stock_shared.reco_algo  # noqa: F401  (정상 환경)
    except Exception:  # noqa: BLE001
        pkg = types.ModuleType('stock_shared')
        pkg.__path__ = []
        sys.modules['stock_shared'] = pkg
        spec = importlib.util.spec_from_file_location('stock_shared.reco_algo', _SHARED)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['stock_shared.reco_algo'] = mod
        spec.loader.exec_module(mod)

from stock_shared.reco_algo import merge_algo_rows, merge_reco_sources, algo_stage_map  # noqa: E402
from app.services.stocks import RecoLevel as R  # noqa: E402


def row(algo, code='A', **kw):
    base = {'ymd': '20261113', 'stock_code': code, 'algo': algo, 'rank_no': None, 'score': None,
            'composite_rank_no': None, 'shape_proba': None, 'momentum_composite': None,
            'frgn_amt': 100, 'orgn_amt': 50, 'prsn_amt': -150, 'investor_ymd': '20261112', 'close': 1000}
    base.update(kw)
    return base


def basic(code='A', **kw):
    return row('BASIC', code, **{'rank_no': 1, 'score': 80, 'shape_proba': 0.4, **kw})


def premium(code='A', **kw):
    return row('PREMIUM', code, **{'composite_rank_no': 1, 'shape_proba': 0.8, 'momentum_composite': 2.5, **kw})


def merged(*rows):
    return merge_algo_rows(list(rows))


def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    return cond


def main():
    ok = True
    # 사용자 단계
    ok &= check('비로그인=1', R.user_level([], []) == 1)
    ok &= check('고급 플래그=2', R.user_level([], ['RECO_ADVANCED']) == 2)
    ok &= check('WORKER_USER=3', R.user_level(['WORKER_USER'], []) == 3)
    ok &= check('ADMIN 이라고 자동 3 아님', R.user_level(['ADMIN'], []) == 1)

    # 공통코드 대응
    ok &= check('공통코드 없으면 기본 대응', algo_stage_map([]) == {'BASIC': 1, 'PREMIUM': 2, 'PRIVATE': 3})
    ok &= check('공통코드 값 반영', algo_stage_map([{'code': 'PRIVATE', 'desc': '2'}])['PRIVATE'] == 2)
    ok &= check('공통코드 잘못된 값 무시', algo_stage_map([{'code': 'PREMIUM', 'desc': 'x'}, {'code': 'ZZZ', 'desc': '1'}])
                == {'BASIC': 1, 'PREMIUM': 2, 'PRIVATE': 3})

    # 알고리즘별 행 합치기: 종목당 한 줄, 값 있는 칸만 덮어쓴다
    m = merged(basic('A'), premium('A'), basic('B'))
    ok &= check('합치기: 종목당 한 줄', sorted(x['stock_code'] for x in m) == ['A', 'B'])
    a = next(x for x in m if x['stock_code'] == 'A')
    ok &= check('합치기: algos', a['algos'] == ['BASIC', 'PREMIUM'])
    ok &= check('합치기: BASIC 점수·순위 유지', a['rank_no'] == 1 and a['score'] == 80)
    ok &= check('합치기: PREMIUM 종합순위·모델 확률이 덮음', a['composite_rank_no'] == 1 and a['shape_proba'] == 0.8)
    ok &= check('합치기: algo 칸 제거', 'algo' not in a)

    # 두 테이블 합치기: trade_buy_target_stock(2파) + trade_buy_target_basic(기본)
    def main_row(code, **kw):   # 2파 테이블 행(algo 칸 없음)
        r = premium(code, **kw)
        r.pop('algo')
        return r

    def basic_tbl_row(code, **kw):   # 기본 테이블 행(algo 칸 없음)
        r = basic(code, **kw)
        r.pop('algo')
        return r

    legacy = main_row('L', rank_no=3, score=70)   # 예전에 2파 테이블에 같이 저장된 기본 알고리즘 행(둘 다 있음)
    mixed = merge_reco_sources([main_row('P'), legacy], [basic_tbl_row('B'), basic_tbl_row('P')])
    ok &= check('두 테이블: 종목당 한 줄', sorted(x['stock_code'] for x in mixed) == ['B', 'L', 'P'])
    ok &= check('두 테이블: 순서 = 2파 목록 먼저, 기본 전용 뒤', [x['stock_code'] for x in mixed] == ['P', 'L', 'B'])
    by = {x['stock_code']: x for x in mixed}
    ok &= check('두 테이블: 양쪽 테이블에 있으면 [BASIC, PREMIUM]', by['P']['algos'] == ['BASIC', 'PREMIUM'])
    ok &= check('두 테이블: 기본 전용 = [BASIC]', by['B']['algos'] == ['BASIC'])
    ok &= check('두 테이블: 옛 겸용 행 = [BASIC, PREMIUM]', by['L']['algos'] == ['BASIC', 'PREMIUM'])
    only_main = merge_reco_sources([main_row('Q')], [])[0]
    ok &= check('두 테이블: 2파 테이블에만 있으면 [PREMIUM]', only_main['algos'] == ['PREMIUM'])
    ok &= check('두 테이블: 2파 행 값이 합쳐짐', by['P']['composite_rank_no'] == 1 and by['P']['rank_no'] == 1)
    bare = merge_reco_sources([main_row('Z', composite_rank_no=None, rank_no=None)], [])[0]
    ok &= check('종합순위도 순위도 없는 최소 행은 단계 없음', R.stages_of(bare) == [])

    # 단계 구성
    ok &= check('BASIC 만 → [1]', R.stages_of(merged(basic())[0]) == [1])
    ok &= check('PREMIUM 만 → [2]', R.stages_of(merged(premium())[0]) == [2])
    ok &= check('둘 다 → [1,2]', R.stages_of(merged(basic(), premium())[0]) == [1, 2])
    ok &= check('수급 합 음수면 PREMIUM 탈락', R.stages_of(merged(premium(frgn_amt=-100, orgn_amt=50))[0]) == [])
    ok &= check('수급 없음이면 PREMIUM 탈락', R.stages_of(merged(premium(frgn_amt=None, orgn_amt=None))[0]) == [])
    ok &= check('shape_proba 없으면 PREMIUM 탈락', R.stages_of(merged(premium(shape_proba=None))[0]) == [])
    ok &= check('BASIC 은 수급이 음수여도 유지', R.stages_of(merged(basic(frgn_amt=-9, orgn_amt=-9))[0]) == [1])
    ok &= check('PRIVATE 행이 생기면 3단계', R.stages_of(merged(row('PRIVATE'), premium())[0]) == [2, 3])
    ok &= check('공통코드로 단계 바꾸면 따라감',
                R.stages_of(merged(premium())[0], {'BASIC': 1, 'PREMIUM': 3, 'PRIVATE': 3}) == [3])

    # 기본 사용자: PREMIUM 전용 종목은 목록에서 빠지고, 고급 정보는 지워진다
    rows = merged(basic('A'), premium('B'), basic('C'), premium('C'))
    b = R.apply_levels(rows, 1)
    ok &= check('기본: PREMIUM 전용 종목 제외', [r['stock_code'] for r in b] == ['A', 'C'])
    ok &= check('기본: 단계는 [1] 만', all(r['reco_stages'] == [1] for r in b))
    ok &= check('기본: 고급 필드 제거', not any(k in r for r in b for k in R.ADVANCED_ONLY_FIELDS))
    ok &= check('기본: 일반 필드 유지', b[0]['score'] == 80 and b[0]['rank_no'] == 1)

    # 고급 사용자: 두 목록 모두, 고급 정보 유지
    rows = merged(basic('A'), premium('B'), basic('C'), premium('C'))
    g = R.apply_levels(rows, 2)
    ok &= check('고급: 세 종목 모두', [r['stock_code'] for r in g] == ['A', 'B', 'C'])
    ok &= check('고급: 단계 목록', [r['reco_stages'] for r in g] == [[1], [2], [1, 2]])
    ok &= check('고급: 고급 필드 유지', 'shape_proba' in g[1] and 'frgn_amt' in g[1])

    # 실전 권한자: PRIVATE 행이 없으면 3단계 종목도 없다
    live = R.apply_levels(merged(basic('A'), premium('B')), 3)
    ok &= check('실전 권한자도 PRIVATE 행이 없으면 3단계 종목 없음', all(3 not in r['reco_stages'] for r in live))
    # 일반 사용자에게 PRIVATE 종목은 안 보인다
    pr = R.apply_levels(merged(row('PRIVATE', 'P')), 2)
    ok &= check('고급 사용자에게 PRIVATE 종목 숨김', pr == [])

    print('\nALL PASS' if ok else '\nFAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
