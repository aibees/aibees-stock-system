"""
매수추천 알고리즘 구분(algo)과 단계 대응, 두 테이블 합치기.

    BASIC    옛 기계식 알고리즘(watch 게이트: 이평 정배열·MACD/OBV 기울기·거래량 급증 …).
             → 별도 테이블 trade_buy_target_basic (score/rank_no)
    PREMIUM  현재 제공 알고리즘(2파 하락 추세선 돌파 + shape_proba 모델 + 외국인·기관 수급).
             → trade_buy_target_stock (composite_rank_no). **워커가 읽는 테이블**이라 그대로 둔다.
    PRIVATE  고급 종목을 30분봉으로 다시 검증해 순위를 재정비한 목록(운영자 전용, 연구 중 — 아직 없음).

알고리즘 코드와 열람 단계(1 기본/2 고급/3 실전)의 대응은 공통코드 master_codes 에 기록한다:
    system='stock', source='setting', category='reco_algo', code=<알고리즘>, desc=<단계 번호>
(행이 없거나 값이 잘못되면 아래 DEFAULT_ALGO_STAGE 를 쓴다.)

서버는 두 테이블의 행을 종목당 한 줄로 합쳐(merge_reco_sources) 행마다 algos(걸린 알고리즘)를 붙인다.
"""

ALGO_BASIC = 'BASIC'
ALGO_PREMIUM = 'PREMIUM'
ALGO_PRIVATE = 'PRIVATE'

# 합칠 때의 적용 순서(뒤가 앞을 덮어쓴다 — 단, 값이 있는 칸만).
ALGO_ORDER = (ALGO_BASIC, ALGO_PREMIUM, ALGO_PRIVATE)

DEFAULT_ALGO_STAGE = {ALGO_BASIC: 1, ALGO_PREMIUM: 2, ALGO_PRIVATE: 3}

MASTER_CODES_KEY = {'system': 'stock', 'source': 'setting', 'category': 'reco_algo'}


def algo_stage_map(rows=None) -> dict:
    """공통코드 행(code, desc)들에서 {알고리즘: 단계 번호}. 빠졌거나 잘못된 값은 기본 대응을 쓴다."""
    out = dict(DEFAULT_ALGO_STAGE)
    for r in rows or []:
        code = str(r.get('code') or '').strip().upper()
        try:
            stage = int(str(r.get('desc') or '').strip())
        except ValueError:
            continue
        if code in out and 1 <= stage <= 3:
            out[code] = stage
    return out


def merge_algo_rows(rows, key=('ymd', 'stock_code')) -> list:
    """같은 key 의 알고리즘별 행을 한 줄로 합친다(첫 등장 순서 유지).

    ALGO_ORDER 순으로 값이 있는(None 이 아닌) 칸만 덮어쓴다. 결과에 algos(들어 있던 알고리즘 목록)를 붙인다.
    algo 칸이 없는 행은 BASIC 으로 본다.
    """
    rank = {a: i for i, a in enumerate(ALGO_ORDER)}
    groups = {}
    for r in rows:
        k = tuple(r.get(c) for c in key)
        groups.setdefault(k, []).append(r)

    merged = []
    for grp in groups.values():
        grp = sorted(grp, key=lambda r: rank.get(r.get('algo') or ALGO_BASIC, 99))
        out = {}
        for r in grp:
            for col, v in r.items():
                if v is not None or col not in out:
                    out[col] = v
        out['algos'] = [r.get('algo') or ALGO_BASIC for r in grp]
        out.pop('algo', None)
        merged.append(out)
    return merged


def merge_reco_sources(main_rows, basic_rows) -> list:
    """trade_buy_target_stock(2파 종합순위) 행과 trade_buy_target_basic(기본) 행을 종목당 한 줄로 합친다.

    순서: 2파 목록(쿼리 정렬 그대로) → 기본 목록에만 있는 종목. 각 행에 algos 를 붙인다.
    main 행은 composite_rank_no 가 있으면 PREMIUM, rank_no 가 남아 있으면(예전에 기본 알고리즘이 같은
    테이블에 저장되던 시절의 행) BASIC 도 겸한다. 둘 다 없는 최소 행은 PREMIUM 후보로만 둔다 — 단계 판정에서 걸러진다.
    """
    tagged = []
    for r in main_rows:
        algos = []
        if r.get('composite_rank_no') is not None:
            algos.append(ALGO_PREMIUM)
        if r.get('rank_no') is not None:
            algos.append(ALGO_BASIC)
        for a in algos or [ALGO_PREMIUM]:
            tagged.append({**r, 'algo': a})
    for r in basic_rows:
        tagged.append({**r, 'algo': ALGO_BASIC})
    return merge_algo_rows(tagged, key=('stock_code',))
