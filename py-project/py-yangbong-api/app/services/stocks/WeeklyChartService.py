"""
홈 '이번 주의 차트' 서버 계산(2026-11-22 회의 결정 3번).

전 주(월~금)에 양봉상회가 실제로 골랐던 종목 중 **신호가 가장 선명한 1개**를 봉과 함께 돌려준다.
  - 선정 기준은 '많이 오른 종목'이 아니다. 그 날 충족한 신호(MACD·OBV·거래급등 …) 개수가 가장 많은 종목이다.
    같으면 거래량 급증 배수가 큰 쪽, 그래도 같으면 종목코드 순 — 결과를 보고 고르지 않는다(주가 흐름은 선정에 쓰지 않는다).
  - 날짜·당시 가격·신호 조건은 그날 저장된 추천 행 그대로다. 사후 각색 금지(QA 조건).
  - 선정 이후의 봉도 그대로 붙인다(오르지 않은 경우도 보여 주기 위해). 수익률 같은 성과 숫자는 만들지 않는다.
  - 주체 표기는 '양봉상회'로 통일(마케팅 조건) — 문구는 화면에서 만든다.

판정 함수(플래그·이유 문장)는 HomePickService 와 같은 것을 쓴다.
"""
import logging
from datetime import date, datetime, timedelta

from app.services.stocks.HomePickService import _TECH_FLAGS, _REASON_PRIORITY, _reason_text, volume_facts

_CACHE = {}                 # {선정일 기준 주 시작일: (저장 시각, 결과)}
_CACHE_SECONDS = 6 * 3600
_BARS_BEFORE = 40           # 선정일 이전 표시 봉 수


SWITCH_HOUR = 8             # 월요일 이 시각에 '전 주'가 막 끝난 주로 바뀐다(2026-11-22 사용자 결정)


def week_days(now) -> list:
    """전 주 금→월 순 날짜(YYYYMMDD). now 는 datetime(date 면 그날 0시로 본다).
    주는 월요일 08:00 에 바뀐다 — 월요일 08:00 전(토·일·월 새벽)까지는 그 전 주를 계속 보여 준다.
    예) 11-22(일)·11-23(월) 07:59 → 11-09~13 주, 11-23(월) 08:00 부터 → 11-16~20 주."""
    if not isinstance(now, datetime):
        now = datetime(now.year, now.month, now.day)
    ref = (now - timedelta(hours=SWITCH_HOUR)).date()
    this_monday = ref - timedelta(days=ref.weekday())
    prev_monday = this_monday - timedelta(days=7)
    return [(prev_monday + timedelta(days=i)).strftime("%Y%m%d") for i in (4, 3, 2, 1, 0)]


def _passed_keys(item) -> list:
    keys = [label for label, fn in _TECH_FLAGS if fn(item)]
    keys.sort(key=_REASON_PRIORITY.index)
    return keys


def _clarity(item):
    """정렬 키(작을수록 선명): 충족 신호 수↓, 거래량 급증 배수↓, 종목코드↑."""
    keys = _passed_keys(item)
    surge = volume_facts(item)["surge"]
    return (-len(keys), -(surge["ratio"] if surge else 0), str(item.get("stock_code") or ""))


def pick_weekly(items: list):
    """후보 중 신호가 가장 선명한 1개와 그 신호 문장(최대 3줄). 신호가 하나도 없으면 None."""
    scored = [it for it in items if _passed_keys(it)]
    if not scored:
        return None
    best = min(scored, key=_clarity)
    facts = volume_facts(best)
    lines = [_reason_text(k, facts) for k in _passed_keys(best)[:3]]
    return best, lines


def _bar(row) -> dict:
    return {"date": str(row.get("date"))[:10], "open": row.get("open"), "high": row.get("high"),
            "low": row.get("low"), "close": row.get("close"), "volume": row.get("volume")}


def _bars_after(stock_service, session, code, sel_iso, today: date) -> list:
    """선정 다음 날부터 오늘까지의 일봉(DB 일봉은 전 거래일까지). 실패하면 빈 목록 — 선정일까지만 보여 준다."""
    try:
        start = (datetime.strptime(sel_iso, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        df = stock_service._bars_between(session, code, start, today.strftime("%Y-%m-%d"))
        out = []
        for r in df.to_dict("records"):
            out.append({"date": str(r.get("ymd") or r.get("date"))[:10], "open": int(r["open"]), "high": int(r["high"]),
                        "low": int(r["low"]), "close": int(r["close"]), "volume": int(r["volume"])})
        return out
    except Exception as e:  # noqa: BLE001
        logging.warning(f"[weekly-chart] 선정 이후 봉 조회 실패 {code}: {e}")
        return []


FALLBACK_DAYS = 28          # 전 주가 비었을 때 어제부터 거슬러 찾는 범위(달력일)


def _recent_days(today: date, skip: set) -> list:
    """어제부터 FALLBACK_DAYS 일 거슬러 올라가는 평일(YYYYMMDD), skip 은 뺀다."""
    out = []
    for i in range(1, FALLBACK_DAYS + 1):
        d = today - timedelta(days=i)
        ymd = d.strftime("%Y%m%d")
        if d.weekday() < 5 and ymd not in skip:
            out.append(ymd)
    return out


def _build(stock_service, session, load_items, ymd, today):
    items = load_items(ymd)
    if not items:
        return None
    picked = pick_weekly(items)
    if not picked:
        return None
    item, lines = picked
    sel_iso = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    before = [_bar(r) for r in (item.get("chart_data") or []) if str(r.get("date"))[:10] <= sel_iso][-_BARS_BEFORE:]
    after = _bars_after(stock_service, session, item["stock_code"], sel_iso, today)
    return {
        "ymd": ymd,
        "stock_code": item["stock_code"],
        "stock_name": item["stock_name"],
        "close": item.get("close"),     # 선정일 종가(당시 가격)
        "lines": lines,
        "bars": before + after,
        "marker_date": sel_iso,
    }


def weekly_chart(stock_service, session, load_items, today: date = None) -> dict:
    """load_items(ymd) → 그 날 추천 목록(요청자 열람 단계로 가공된 것). 전 주 금요일부터 거슬러 올라가 처음 나오는 날을 쓴다.
    전 주에 보여 줄 종목이 하나도 없으면 어제부터 거슬러 가장 최근에 종목이 있는 날을 쓴다(2026-11-22 사용자 결정 —
    기본 단계 목록이 11-18 부터 쌓여 그 전 주는 비어 있었고, 그동안 홈에서 블록이 사라졌다)."""
    now_dt = datetime.now() if today is None else datetime(today.year, today.month, today.day)
    today = now_dt.date()
    days = week_days(now_dt)   # 월요일 08:00 에 주가 바뀐다
    cached = _CACHE.get(days[-1])
    now = datetime.now().timestamp()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]

    result = None
    for ymd in days + _recent_days(today, set(days)):
        result = _build(stock_service, session, load_items, ymd, today)
        if result:
            break
    _CACHE[days[-1]] = (now, result)
    return result
