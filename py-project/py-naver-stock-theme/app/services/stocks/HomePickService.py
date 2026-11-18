"""
홈 'AI 분석 종목 TOP 3' 서버 계산(2026-11-18).

예전에는 홈이 /stocks/buy-target 전체(종목당 120일 봉)를 받아 화면에서 다시 판정했다.
홈은 차트도 지표값도 그리지 않으므로, 같은 계산을 서버에서 하고 결과 몇 줄만 내려준다.

**정본은 화면 JS 다.** 아래 함수는 yangbong-store-vue/src/scripts 의 다음 함수를 그대로 옮긴 것이다.
  indicators.js   normalizeSettings · evaluate(match 만)
  persona.js      volatilityPct · orderForType
  stockSignals.js numOrNull · parseRate · volumeFacts · technicalRows
  recoReasons.js  recoReasons(top · rest 만)
JS 를 고치면 여기도 같이 고친다. 같은 결과인지는 운영 응답으로 JS·파이썬을 함께 돌려 비교한다
(scratchpad 의 비교 스크립트 방식 — 설계 메모 meetings/설계_2026-11-18_AI분석-비동기화.md 와 별개).

반올림은 JS 와 똑같이 맞춘다: Math.round·toFixed 는 .5 를 올리지만 파이썬 round 는 짝수로 보낸다.
"""
import math
import re
from decimal import Decimal, ROUND_HALF_UP

# ── indicators.js ─────────────────────────────────────────────

# 지표별 수치 범위(화면의 − + 입력 범위). (key, min, max)
INDICATOR_PARAMS = {
    "volume": [("ratio", 1, 10)],
    "surge":  [("ratio", 1.5, 10), ("days", 1, 10)],
    "macd":   [("fast", 3, 20), ("slow", 10, 60), ("signal", 3, 20), ("days", 1, 10)],
    "obv":    [("ma", 3, 30), ("days", 1, 10)],
    "ma":     [("period", 5, 120)],
    "bb":     [("period", 5, 60), ("std", 1, 3)],
    "cap":    [("minEok", 100, 100000)],
    "volat":  [("minPct", 1, 15)],
}
INDICATOR_KEYS = list(INDICATOR_PARAMS)
ORDER_KEYS = ("default", "market_cap", "volatility")

DEFAULT_SETTINGS = {
    "minPass": 2,
    "order": "default",
    "volume": {"on": True,  "ratio": 1.5},
    "surge":  {"on": False, "ratio": 3, "days": 5},
    "macd":   {"on": True,  "fast": 12, "slow": 26, "signal": 9, "days": 3},
    "obv":    {"on": True,  "ma": 9, "days": 3},
    "ma":     {"on": True,  "period": 20},
    "bb":     {"on": False, "period": 20, "std": 2},
    "cap":    {"on": False, "minEok": 1000},
    "volat":  {"on": False, "minPct": 3},
}


def _js_number(v):
    """JS Number(v) 와 같은 변환. 숫자가 아니면 NaN 대신 None."""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _js_round(x: float) -> int:
    """Math.round — .5 는 위로."""
    return math.floor(x + 0.5)


def _to_fixed(x: float, digits: int) -> str:
    """Number.prototype.toFixed — 실제 이진값 기준, 정확히 반이면 큰 쪽으로."""
    q = Decimal(1).scaleb(-digits)
    return str(Decimal(x).quantize(q, rounding=ROUND_HALF_UP))


def _clamp(v, lo, hi, fallback):
    n = _js_number(v)
    if n is None or not math.isfinite(n):
        return fallback
    return min(hi, max(lo, n))


def normalize_settings(s, base=DEFAULT_SETTINGS) -> dict:
    """indicators.normalizeSettings. 모르는 값·빠진 값·범위 밖 값을 기본값/범위로 바로잡는다."""
    s = s if isinstance(s, dict) else {}
    out = {}
    for key, params in INDICATOR_PARAMS.items():
        b = base.get(key) or DEFAULT_SETTINGS[key]
        v = s.get(key)
        v = v if isinstance(v, dict) else {}
        row = {"on": v["on"] if isinstance(v.get("on"), bool) else bool(b.get("on"))}
        for p, lo, hi in params:
            raw = v.get(p)
            if raw is None:
                raw = b.get(p)
            fb = b.get(p) if b.get(p) is not None else lo
            row[p] = _clamp(raw, lo, hi, fb)
        out[key] = row
    if out["macd"]["fast"] >= out["macd"]["slow"]:
        out["macd"]["fast"] = max(3, out["macd"]["slow"] - 1)
    out["order"] = s.get("order") if s.get("order") in ORDER_KEYS else (base.get("order") or "default")
    on = max(1, sum(1 for k in INDICATOR_KEYS if out[k]["on"]))
    raw_min = s.get("minPass")
    if raw_min is None:
        raw_min = base.get("minPass")
    out["minPass"] = _js_round(_clamp(raw_min, 1, on, min(on, 2)))
    return out


# ── stockSignals.js ───────────────────────────────────────────

def num_or_null(v):
    if v is None or v == "":
        return None
    n = _js_number(v)
    if n is None or math.isnan(n):
        return None
    return n


_RATE_RE = re.compile(r"^\s*([+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?)")


def parse_rate(rate):
    """stockSignals.parseRate — '6.94%' → 6.94 (parseFloat 처럼 앞부분 숫자만)."""
    if rate is None or rate == "":
        return None
    m = _RATE_RE.match(str(rate).replace("%", "", 1))
    return float(m.group(1)) if m else None


def _ymd_of(row) -> str:
    return str(row.get("date") or "")[:10].replace("-", "")


def _bars_until(item) -> list:
    """기준일(ymd) 이후 봉은 뺀다. ymd 가 없으면 그대로."""
    ymd = str(item.get("ymd") or "")
    return [r for r in (item.get("chart_data") or []) if not ymd or _ymd_of(r) <= ymd]


_AVG_WINDOW = 20
_SURGE_LOOKBACK = 5


def volume_facts(item) -> dict:
    """stockSignals.volumeFacts — avgRatio: 기준일 거래량 / 직전 20영업일 평균, surge: 최근 5일 중 전일 대비 최대 배수."""
    ymd = str(item.get("ymd") or "")
    rows = [r for r in (item.get("chart_data") or []) if _ymd_of(r) <= ymd]
    vols = [num_or_null(r.get("volume")) for r in rows]

    avg_ratio = None
    past = [v for v in vols[-_AVG_WINDOW - 1:-1] if v is not None and v > 0]
    today = vols[-1] if vols else None
    if len(past) >= 5 and today is not None:
        total = 0.0
        for v in past:
            total += v
        avg_ratio = today / (total / len(past))

    surge = None
    for i in range(max(1, len(rows) - _SURGE_LOOKBACK), len(rows)):
        prev, cur = vols[i - 1], vols[i]
        if not prev or cur is None:
            continue
        ratio = cur / prev
        if surge is None or ratio > surge["ratio"]:
            parts = str(rows[i].get("date"))[:10].split("-")
            m = parts[1] if len(parts) > 1 else "undefined"
            d = parts[2] if len(parts) > 2 else "undefined"
            surge = {"date": f"{m}/{d}", "ratio": ratio}
    return {"avgRatio": avg_ratio, "surge": surge}


# technicalRows: (라벨, 통과 판정) — 서버 플래그 그대로
_TECH_FLAGS = [
    ("MACD 크로스", lambda it: it.get("macd_cross") == "G"),
    ("OBV 크로스",  lambda it: it.get("obv_cross") == "G"),
    ("거래제한",    lambda it: it.get("is_vol_limit") == "Y"),
    ("거래급등",    lambda it: it.get("is_vol_surge") == "Y"),
    ("BB중심돌파",  lambda it: it.get("is_bb_mid_breakout") == "Y"),
    ("BB상단아래",  lambda it: it.get("is_under_bb_upper") == "Y"),
    ("중심선위",    lambda it: it.get("is_over_on_mid") == "Y"),
]


# ── persona.js ────────────────────────────────────────────────

_ATR_DAYS = 20


def volatility_pct(item):
    """persona.volatilityPct — 최근 20일 평균 실제 변동폭(ATR) ÷ 종가 (%)."""
    ymd = str(item.get("ymd") or "")
    rows = []
    for r in item.get("chart_data") or []:
        if _ymd_of(r) > ymd:
            continue
        h, l, c = num_or_null(r.get("high")), num_or_null(r.get("low")), num_or_null(r.get("close"))
        if h is not None and l is not None and c is not None:
            rows.append((h, l, c))
    if len(rows) < _ATR_DAYS + 1:
        return None
    recent = rows[-(_ATR_DAYS + 1):]
    total = 0
    for i in range(1, len(recent)):
        h, l, _ = recent[i]
        pc = recent[i - 1][2]
        total += max(h - l, abs(h - pc), abs(l - pc))
    close = recent[-1][2]
    return (total / _ATR_DAYS) / close * 100 if close > 0 else None


def order_for_type(items: list, order: str) -> list:
    """persona.orderForType — 값이 큰 순, 값 없으면 뒤로, 동률은 서버 순서."""
    key_of = {
        "market_cap": lambda it: num_or_null(it.get("market_cap")),
        "volatility": volatility_pct,
    }.get(order)
    if key_of is None:
        return list(items)
    indexed = [(i, it, key_of(it)) for i, it in enumerate(items)]
    indexed.sort(key=lambda x: (x[2] is None, -(x[2] or 0) if x[2] is not None else 0, x[0]))
    return [it for _, it, _ in indexed]


# ── indicators.evaluate (match 만) ────────────────────────────

def _ema(values, period):
    k = 2 / (period + 1)
    out, prev = [], None
    for v in values:
        if v is None:
            out.append(None)
            continue
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def _sma(values, period, end):
    seg = values[max(0, end - period + 1):end + 1]
    if len(seg) < period or any(v is None for v in seg):
        return None
    total = 0
    for v in seg:
        total += v
    return total / period


def _crossed_up(a, b, days) -> bool:
    i = len(a) - 1
    stop = max(1, len(a) - days)
    while i >= stop:
        if not any(x is None for x in (a[i], b[i], a[i - 1], b[i - 1])):
            if a[i - 1] <= b[i - 1] and a[i] > b[i]:
                return True
        i -= 1
    return False


def _js_gt(a, b) -> bool:
    """JS 의 a > b (null 은 0 으로 비교된다)."""
    return (0 if a is None else a) > (0 if b is None else b)


def _js_lt(a, b) -> bool:
    return (0 if a is None else a) < (0 if b is None else b)


def evaluate_match(item, settings) -> bool:
    """indicators.evaluate(...).match — 켜 둔 지표 중 minPass 개 이상 충족이면 True."""
    s = normalize_settings(settings)
    bars = _bars_until(item)
    closes = [num_or_null(r.get("close")) for r in bars]
    total = 0
    passed = 0

    for key in INDICATOR_KEYS:
        v = s[key]
        if not v["on"]:
            continue
        ok = False
        if key == "volume":
            avg = volume_facts({**item, "chart_data": bars})["avgRatio"]
            ok = avg is not None and avg >= v["ratio"]
        elif key == "surge":
            best = None
            # 일수·기간은 화면 입력이 1 단위라 정수로 쓴다(소수가 오면 JS 는 봉 인덱스에서 깨진다).
            for i in range(max(1, len(bars) - int(v["days"])), len(bars)):
                prev = num_or_null(bars[i - 1].get("volume"))
                cur = num_or_null(bars[i].get("volume"))
                if prev and cur is not None and (best is None or cur / prev > best):
                    best = cur / prev
            ok = best is not None and best >= v["ratio"]
        elif key == "macd":
            fast, slow, sig_p = v["fast"], v["slow"], v["signal"]
            if len(closes) >= slow + sig_p:
                e_fast, e_slow = _ema(closes, fast), _ema(closes, slow)
                line = [None if x is None or y is None else x - y for x, y in zip(e_fast, e_slow)]
                sig = _ema(line, sig_p)
                ok = _crossed_up(line, sig, v["days"])
        elif key == "obv":
            ma = v["ma"]
            if len(bars) > ma + 1:
                obv = [0]
                for i in range(1, len(bars)):
                    c, p = closes[i], closes[i - 1]
                    vol = num_or_null(bars[i].get("volume"))
                    vol = 0 if vol is None else vol
                    obv.append(obv[i - 1] + (vol if _js_gt(c, p) else (-vol if _js_lt(c, p) else 0)))
                period = int(ma)
                avg = [_sma(obv, period, i) for i in range(len(obv))]
                ok = _crossed_up(obv, avg, v["days"])
        elif key == "ma":
            period = int(v["period"])
            avg = _sma(closes, period, len(closes) - 1)
            last = closes[-1] if closes else None
            ok = avg is not None and last is not None and last > avg
        elif key == "bb":
            period = int(v["period"])
            end = len(closes) - 1
            mid = _sma(closes, period, end)
            if mid is not None:
                seg = closes[end - period + 1:end + 1]
                acc = 0
                for c in seg:
                    acc += (c - mid) ** 2
                sd = math.sqrt(acc / period)
                ok = closes[end] <= mid + v["std"] * sd
        elif key == "cap":
            cap = num_or_null(item.get("market_cap"))
            ok = cap is not None and cap >= v["minEok"]
        elif key == "volat":
            vol = volatility_pct({**item, "chart_data": bars})
            ok = vol is not None and vol >= v["minPct"]
        total += 1
        passed += 1 if ok else 0

    return total == 0 or passed >= min(s["minPass"], total)


# ── recoReasons.js (top · rest) ───────────────────────────────

_REASON_PRIORITY = ["거래급등", "MACD 크로스", "BB중심돌파", "OBV 크로스", "중심선위", "BB상단아래", "거래제한"]


def _ratio_text(r: float) -> str:
    return f"{_js_round(r):,}" if r >= 10 else _to_fixed(r, 1)


def _reason_text(key, facts) -> str:
    if key == "거래급등":
        s = facts["surge"]
        return f"거래량이 전날보다 {_ratio_text(s['ratio'])}배 늘었어요" if s else "거래량이 갑자기 늘었어요"
    return {
        "MACD 크로스": "오르는 흐름으로 바뀌는 신호예요",
        "BB중심돌파": "가격이 평균 범위 위로 올라섰어요",
        "OBV 크로스": "사려는 돈이 들어오고 있어요",
        "중심선위": "20일 평균 가격보다 위예요",
        "BB상단아래": "아직 많이 오르지 않았어요",
        "거래제한": "거래가 충분히 활발해요",
    }[key]


def reco_reason(item) -> dict:
    """recoReasons(item) 의 {top: 문장|None, rest: 나머지 충족 개수}."""
    passed_keys = [label for label, fn in _TECH_FLAGS if fn(item)]
    passed_keys.sort(key=_REASON_PRIORITY.index)
    if not passed_keys:
        return {"top": None, "rest": 0}
    return {"top": _reason_text(passed_keys[0], volume_facts(item)), "rest": len(passed_keys) - 1}


# ── 홈 응답 ───────────────────────────────────────────────────

def home_picks(items: list, settings, limit: int = 3, watch_codes=None) -> dict:
    """홈 'AI 분석 종목' 응답.
      candidate_count : 서버 후보 수(판정 전) — 0 이 아닌데 matched_count 가 0 이면 화면이 '설정 조정하기'를 보인다
      matched_count   : 내 설정으로 통과한 수
      ymd             : 표시일(YYYYMMDD)
      items           : 순서대로 최대 limit 개 {stock_code, stock_name, ymd, close, rate_pct, reason, reason_rest}
      watch_items     : 관심 종목(watch_codes) 중 오늘 후보에 있는 것 — 후보 행 그대로(chart_data 포함) + match(내 조건 충족).
                        화면의 관심 종목 '오늘 소식'(stockNews.judgeStockNews)이 이 봉과 match 로 판단한다.
                        후보에 없는 관심 종목은 화면이 /charts/stock 으로 따로 받는다.
    """
    s = normalize_settings(settings)
    matched = [it for it in items if evaluate_match(it, s)]
    ordered = order_for_type(matched, s["order"])
    out = []
    for it in ordered[:limit]:
        r = reco_reason(it)
        out.append({
            "stock_code": it.get("stock_code"),
            "stock_name": it.get("stock_name"),
            "ymd": it.get("ymd"),
            "close": it.get("close"),
            "rate_pct": parse_rate(it.get("rate")),
            "reason": r["top"],
            "reason_rest": r["rest"],
        })
    watch = set(watch_codes or [])
    watch_items = [{**it, "match": evaluate_match(it, s)} for it in items if it.get("stock_code") in watch]
    return {
        "watch_items": watch_items,
        "ymd": items[0].get("ymd") if items else None,
        "candidate_count": len(items),
        "matched_count": len(matched),
        "items": out,
    }
