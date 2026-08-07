"""매수타겟 정렬 규칙 (user_options.s1_buy_order).

worker(BuyExecutor)와 시뮬레이션이 **같은 순서로** 종목을 고르게 하려면
정렬 규칙이 한 곳에만 있어야 한다. 식을 복제하면 한쪽만 고쳐져
"시뮬 결과와 실제 매수가 다른" 상황이 생긴다.

스펙 문자열: "필드[:방향],필드[:방향],..."
    예) "score:desc,volume:desc,rank_no:asc"
        "volume,rate"          ← 방향 생략 시 필드별 기본방향
앞의 키가 동률일 때만 다음 키로 tie-break 한다.

★ 정렬 항목 추가 = ORDER_FIELDS 에 한 줄 추가. 그게 전부다.

SQL ORDER BY 를 쓰지 않는 이유:
  · score/rank_no/volume 이 nullable 인데 DB 별 NULL 정렬 위치가 갈린다.
    NULL 은 asc/desc 어느 쪽이든 **항상 후순위** 여야 한다.
  · rate 는 '12.5%' 형태 varchar 라 애초에 SQL 정렬이 불가능하다.
"""
import logging
from decimal import Decimal

log = logging.getLogger("stock_shared.buy_order")


def _num(v):
    """숫자형 추출. 변환 불가/None 이면 None(→ 항상 후순위)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v):
    """'12.5%' · '-3.2%' · 12.5 → float. 변환 불가면 None."""
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    s = str(v).strip().replace("%", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# 필드명 → (값 추출기, 기본 정렬방향)
#   기본방향: "그 필드로 정렬하라"고 했을 때 사람이 기대하는 쪽.
#   score/volume/rate 는 클수록 상위(desc), rank_no 는 작을수록 상위(asc).
ORDER_FIELDS = {
    "score":   (lambda r: _num(r.get("score")),   "desc"),
    "volume":  (lambda r: _num(r.get("volume")),  "desc"),
    "rate":    (lambda r: _pct(r.get("rate")),    "desc"),
    "rank_no": (lambda r: _num(r.get("rank_no")), "asc"),
    "close":   (lambda r: _num(r.get("close")),   "desc"),
    # ── 추가 예시(조회 컬럼만 넣으면 즉시 동작) ──
    # "per":   (lambda r: _num(r.get("per")),     "asc"),
}

# 스펙 미설정(NULL) 시 기본
DEFAULT_BUY_ORDER = "score:desc,rank_no:asc"


def parse_buy_order(spec):
    """스펙 문자열 → [(필드명, is_desc), ...]. 모르는 필드는 버린다.

    유효한 항목이 하나도 안 남으면 DEFAULT_BUY_ORDER 로 되돌린다.
    (유저가 오타를 내도 매수가 멈추면 안 되므로 예외를 던지지 않는다)
    """
    steps = []
    for token in (spec or "").split(","):
        token = token.strip()
        if not token:
            continue
        field, _, direction = token.partition(":")
        field = field.strip().lower()
        entry = ORDER_FIELDS.get(field)
        if entry is None:
            log.warning("[매수정렬] 알 수 없는 필드 무시: %r (허용: %s)",
                        field, ", ".join(ORDER_FIELDS))
            continue
        direction = (direction.strip().lower() or entry[1])
        steps.append((field, direction == "desc"))

    if not steps:
        if spec:
            log.warning("[매수정렬] 유효 항목 없음(%r) → 기본값 사용", spec)
        return [(f, d == "desc") for f, d in
                ((t.partition(":")[0], t.partition(":")[2])
                 for t in DEFAULT_BUY_ORDER.split(","))]
    return steps


def make_buy_order_key(spec):
    """스펙에 맞는 sort key 함수를 만들어 반환.

    각 키는 (is_null, value) 2-튜플이다.
      · is_null 0/1 → NULL 행은 정렬 **방향과 무관하게** 항상 뒤로 간다.
        (float('inf') 방식은 desc 로 뒤집으면 NULL 이 맨 앞으로 오는 함정이 있다)
      · desc 는 값의 부호를 뒤집어 오름차순 sort 하나로 처리한다.
    마지막에 stock_code 를 넣어 전 키 동률일 때도 순서가 흔들리지 않게 한다
    (DB 가 행 순서를 보장하지 않으므로 없으면 실행마다 1순위가 바뀔 수 있다).
    """
    steps = parse_buy_order(spec)

    def key(row):
        out = []
        for field, is_desc in steps:
            v = ORDER_FIELDS[field][0](row)
            out.append((1, 0.0) if v is None else (0, -v if is_desc else v))
        return (tuple(out), str(row.get("stock_code") or ""))

    return key


def describe_buy_order(spec) -> str:
    """로그·화면용 요약 — 실제 적용된 정렬을 문자열로."""
    return ",".join(f"{f}:{'desc' if d else 'asc'}" for f, d in parse_buy_order(spec))
