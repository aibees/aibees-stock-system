"""
매수추천 단계(기본 → 고급 → 실전)별 목록 구성과 권한별 응답 가공.

단계는 **서로 다른 알고리즘이 만든 목록**이다(필터가 겹쳐지는 구조가 아니다).

    1 기본  BASIC    옛 기계식 알고리즘(watch 게이트: 이평 정배열·MACD/OBV 기울기·거래량 급증 등).
    2 고급  PREMIUM  현재 제공 알고리즘(2파 하락 추세선 돌파 + shape_proba 모델 + 외국인·기관 매수세).
                     PREMIUM 행이 있고, shape_proba 가 있고, 외국인+기관 순매수 합이 0보다 커야 인정한다.
    3 실전  PRIVATE  고급 종목을 30분봉으로 다시 검증해 순위를 재정비한 목록. 다른 세션에서 연구 중이며
                     결과가 나오기 전까지 PRIVATE 행이 없어 이 단계에는 종목이 없다.

알고리즘은 trade_buy_target_stock.algo 로 구분하고(행이 알고리즘마다 따로), 알고리즘→단계 대응은 공통코드
master_codes(stock/setting/reco_algo)에 기록한다(stock_shared.reco_algo). 읽는 쪽이 같은 종목을 한 줄로 합쳐
행마다 algos 를 갖는다.

한 종목이 두 알고리즘에 모두 걸리면 두 단계 목록에 모두 나온다. 행마다 reco_stages(통과한 단계 번호 목록)를
내려주고, 화면은 이 값으로 단계별 탭을 구성한다.

열람 가능한 최고 단계(user_level):
    WORKER_USER 권한(운영자가 직접 부여)  → 3
    RECO_ADVANCED 기능 플래그(관리자 부여, 추후 광고·구독) → 2
    그 외, 비로그인 포함                  → 1

권한 밖 단계의 종목은 **목록에서 아예 뺀다**(기본 사용자는 2파 종목이 있다는 사실도 알 수 없다).
기본 사용자에게는 고급 정보(shape_proba·종합순위·수급)도 응답에서 지운다.
수급은 추천일 다음 날 아침에야 적재되므로 단계는 저장하지 않고 조회 시 계산한다.
※ 화면 가림은 보안이 아니다. 권한 밖 정보는 이 모듈이 응답에서 지운다.
"""

from stock_shared.reco_algo import ALGO_PREMIUM, DEFAULT_ALGO_STAGE

LEVEL_BASIC = 1
LEVEL_ADVANCED = 2
LEVEL_LIVE = 3

WORKER_AUTH_ID = 'WORKER_USER'
ADVANCED_FEATURE = 'RECO_ADVANCED'

# 기본 단계 사용자에게 내려주면 안 되는 고급 정보(알고리즘 산출물·수급).
ADVANCED_ONLY_FIELDS = (
    'shape_proba', 'shape_exhaustion', 'momentum_composite', 'composite_rank_no',
    'investor_ymd', 'frgn_amt', 'orgn_amt', 'prsn_amt', 'frgn_qty', 'orgn_qty', 'prsn_qty',
)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def user_level(auth_ids, features) -> int:
    """열람 가능한 최고 단계. 비로그인은 auth_ids/features 가 비어 있어 1."""
    if WORKER_AUTH_ID in (auth_ids or []):
        return LEVEL_LIVE
    if ADVANCED_FEATURE in (features or []):
        return LEVEL_ADVANCED
    return LEVEL_BASIC


def flow_ok(item) -> bool:
    """외국인+기관 순매수 합이 0보다 큰가. 둘 다 없으면(수급 미적재) 통과시키지 않는다."""
    vals = [v for v in (_num(item.get('frgn_amt')), _num(item.get('orgn_amt'))) if v is not None]
    return bool(vals) and sum(vals) > 0


def premium_ok(item) -> bool:
    """PREMIUM(2파 + shape_proba + 외국인·기관 매수세) 알고리즘 종목으로 인정되는가.
    PREMIUM 행(종합순위 보유)이 있고, 모델 확률이 있고, 수급 조건을 통과해야 한다."""
    return (item.get('composite_rank_no') is not None
            and item.get('shape_proba') is not None
            and flow_ok(item))


def stages_of(item, algo_stage=None) -> list:
    """종목이 속한 단계 번호 목록(오름차순). 예: [1], [2], [1, 2].

    행의 algos(걸린 알고리즘 목록)를 공통코드의 알고리즘→단계 대응(algo_stage)으로 바꾼다.
    PRIVATE(연구 중)는 행이 생기면 자동으로 3단계에 잡힌다.
    """
    algo_stage = algo_stage or DEFAULT_ALGO_STAGE
    stages = set()
    for algo in item.get('algos') or []:
        stage = algo_stage.get(algo)
        if stage is None:
            continue
        if algo == ALGO_PREMIUM and not premium_ok(item):
            continue
        stages.add(stage)
    return sorted(stages)


def apply_levels(items, level, algo_stage=None) -> list:
    """응답용으로 단계를 붙이고, 열람 단계 밖 종목과 정보를 지운다. 새 리스트를 반환한다.

    - 각 행에 reco_stages 를 붙이되 사용자 단계까지만 담는다.
    - 열람 단계에 속한 단계가 하나도 없는 행은 목록에서 뺀다.
    - 기본 단계 사용자에게는 ADVANCED_ONLY_FIELDS 를 지운다.
    """
    out = []
    for it in items:
        stages = [s for s in stages_of(it, algo_stage) if s <= level]
        if not stages:
            continue
        it['reco_stages'] = stages
        if level < LEVEL_ADVANCED:
            for k in ADVANCED_ONLY_FIELDS:
                it.pop(k, None)
        out.append(it)
    return out
