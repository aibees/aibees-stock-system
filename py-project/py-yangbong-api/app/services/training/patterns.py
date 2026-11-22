"""
차트 퀴즈 패턴 판정. pattern.condition_json.type 별로 "그날 신호가 났는가"를 배열로 계산한다.

DEFAULT_PATTERNS 는 sql/yangbong/014 의 INSERT 와 같은 내용이다. DB 에 pattern 표가 없을 때(로컬 시험 --dry-run)
이 값으로 돌고, 표가 있으면 표의 행(id·condition_json)을 쓴다. 표에 없는 type 은 건너뛴다.

배열 이름(ctx): close·open·high·low·vol(원 단위 아님, 그대로)·volr(직전 20일 평균 대비)·ma{5,20,60,120}·rsi14·macd·signal·bbu·bbl
"""
import json

import numpy as np

DEFAULT_PATTERNS = [
    ("MA20_BREAK_VOL2", "20일선 돌파 + 거래량 2배", {"type": "MA_CROSS_UP", "ma": 20, "volMult": 2}),
    ("MA20_BREAKDOWN_VOL2", "20일선 이탈 + 거래량 2배", {"type": "MA_CROSS_DOWN", "ma": 20, "volMult": 2}),
    ("MA5_20_GOLDEN", "5일선이 20일선 위로", {"type": "MA_GOLDEN", "fast": 5, "slow": 20}),
    ("MA5_20_DEAD", "5일선이 20일선 아래로", {"type": "MA_DEAD", "fast": 5, "slow": 20}),
    ("HIGH60_BREAK_VOL2", "60일 최고가 돌파 + 거래량 2배", {"type": "HIGH_BREAK", "days": 60, "volMult": 2}),
    ("VOL3_LONG_UP", "거래량 3배 + 큰 양봉", {"type": "LONG_CANDLE_UP", "minChange": 5, "volMult": 3}),
    ("RSI30_REBOUND", "RSI 30 위로 회복", {"type": "RSI_CROSS_UP", "period": 14, "level": 30}),
    ("RSI70_DROP", "RSI 70 아래로", {"type": "RSI_CROSS_DOWN", "period": 14, "level": 70}),
    ("MACD_GOLDEN_BELOW0", "MACD 시그널 위로(0 아래)", {"type": "MACD_CROSS_UP", "below0": True}),
    ("BB_UPPER_BREAK", "볼린저밴드 상단 돌파", {"type": "BB_BREAK_UP", "period": 20, "k": 2}),
    ("BB_LOWER_BREAK", "볼린저밴드 하단 이탈", {"type": "BB_BREAK_DOWN", "period": 20, "k": 2}),
]

# 방향성: +1 은 "위로 넘는" 신호, -1 은 "아래로 내려가는" 신호. 속임수 돌파(Lv4) 판정에 쓴다.
# aux: 보조지표(RSI·MACD·볼린저)를 읽어야 하는 신호 — Lv3 후보.
TYPE_META = {
    "MA_CROSS_UP":    {"side": +1, "aux": False},
    "MA_CROSS_DOWN":  {"side": -1, "aux": False},
    "MA_GOLDEN":      {"side": +1, "aux": False},
    "MA_DEAD":        {"side": -1, "aux": False},
    "HIGH_BREAK":     {"side": +1, "aux": False},
    "LONG_CANDLE_UP": {"side": +1, "aux": False},
    "RSI_CROSS_UP":   {"side": +1, "aux": True},
    "RSI_CROSS_DOWN": {"side": -1, "aux": True},
    "MACD_CROSS_UP":  {"side": +1, "aux": True},
    "BB_BREAK_UP":    {"side": +1, "aux": True},
    "BB_BREAK_DOWN":  {"side": -1, "aux": True},
}

# 힌트: 어디를 보면 되는지만 말한다. 방향(오를지·내릴지)은 말하지 않는다.
HINTS = {
    "MA_CROSS_UP":    "마지막 봉의 종가가 20일선(초록)과 어떤 위치에 있는지, 그날 거래량이 평소보다 얼마나 많은지 보세요.",
    "MA_CROSS_DOWN":  "마지막 봉의 종가가 20일선(초록)과 어떤 위치에 있는지, 그날 거래량이 평소보다 얼마나 많은지 보세요.",
    "MA_GOLDEN":      "끝부분에서 5일선(노랑)과 20일선(초록)이 어떻게 만나는지 보세요.",
    "MA_DEAD":        "끝부분에서 5일선(노랑)과 20일선(초록)이 어떻게 만나는지 보세요.",
    "HIGH_BREAK":     "마지막 종가를 최근 석 달 동안의 높은 가격들과 비교하고, 그날 거래량도 함께 보세요.",
    "LONG_CANDLE_UP": "마지막 봉의 몸통 길이와 그날 거래량을 직전 한 달과 비교해 보세요.",
    "RSI_CROSS_UP":   "RSI 를 켜고 30 선 근처에서 마지막 며칠 동안 어떻게 움직였는지 보세요.",
    "RSI_CROSS_DOWN": "RSI 를 켜고 70 선 근처에서 마지막 며칠 동안 어떻게 움직였는지 보세요.",
    "MACD_CROSS_UP":  "MACD 를 켜고 끝부분에서 MACD 선과 시그널 선이 어떻게 만나는지, 0 선과는 어디에 있는지 보세요.",
    "BB_BREAK_UP":    "볼린저밴드를 켜고 마지막 종가가 띠의 어디에 있는지 보세요.",
    "BB_BREAK_DOWN":  "볼린저밴드를 켜고 마지막 종가가 띠의 어디에 있는지 보세요.",
}


def _prev(a: np.ndarray) -> np.ndarray:
    p = np.full(len(a), np.nan)
    p[1:] = a[:-1]
    return p


def _gt(a, b):
    with np.errstate(invalid='ignore'):
        return np.nan_to_num(a, nan=-np.inf) > np.nan_to_num(b, nan=np.inf)


def _le(a, b):
    with np.errstate(invalid='ignore'):
        return np.nan_to_num(a, nan=np.inf) <= np.nan_to_num(b, nan=-np.inf)


def _vol_ok(ctx, cond):
    m = cond.get("volMult")
    if not m:
        return np.ones(len(ctx["close"]), dtype=bool)
    return np.nan_to_num(ctx["volr"], nan=0.0) >= float(m)


def detect(cond: dict, ctx: dict) -> np.ndarray:
    """그날 신호가 났으면 True 인 bool 배열."""
    t = cond.get("type")
    c, pc = ctx["close"], _prev(ctx["close"])
    if t in ("MA_CROSS_UP", "MA_CROSS_DOWN"):
        ma = ctx["ma"][str(cond.get("ma", 20))]
        pma = _prev(ma)
        hit = (_le(pc, pma) & _gt(c, ma)) if t == "MA_CROSS_UP" else (_gt(pc, pma) & _le(c, ma))
        return hit & _vol_ok(ctx, cond)
    if t in ("MA_GOLDEN", "MA_DEAD"):
        f, s = ctx["ma"][str(cond.get("fast", 5))], ctx["ma"][str(cond.get("slow", 20))]
        pf, ps = _prev(f), _prev(s)
        hit = (_le(pf, ps) & _gt(f, s)) if t == "MA_GOLDEN" else (_gt(pf, ps) & _le(f, s))
        return hit & _vol_ok(ctx, cond)
    if t == "HIGH_BREAK":
        d = int(cond.get("days", 60))
        hi = np.full(len(c), np.nan)
        for i in range(d, len(c)):
            hi[i] = c[i - d:i].max()
        return _gt(c, hi) & _vol_ok(ctx, cond)
    if t == "LONG_CANDLE_UP":
        with np.errstate(divide='ignore', invalid='ignore'):
            chg = (c / pc - 1) * 100
        return (np.nan_to_num(chg, nan=0) >= float(cond.get("minChange", 5))) & (c > ctx["open"]) & _vol_ok(ctx, cond)
    if t in ("RSI_CROSS_UP", "RSI_CROSS_DOWN"):
        r = ctx["rsi14"]
        pr = _prev(r)
        lv = float(cond.get("level", 30))
        lvl = np.full(len(r), lv)
        return (_le(pr, lvl) & _gt(r, lvl)) if t == "RSI_CROSS_UP" else (_gt(pr, lvl) & _le(r, lvl))
    if t == "MACD_CROSS_UP":
        m, s = ctx["macd"], ctx["signal"]
        hit = _le(_prev(m), _prev(s)) & _gt(m, s)
        if cond.get("below0"):
            hit &= _le(m, np.zeros(len(m)))
        return hit
    if t == "BB_BREAK_UP":
        return _le(pc, _prev(ctx["bbu"])) & _gt(c, ctx["bbu"])
    if t == "BB_BREAK_DOWN":
        return _gt(pc, _prev(ctx["bbl"])) & _le(c, ctx["bbl"])
    return np.zeros(len(c), dtype=bool)


def signal_sentence(code: str, cond: dict, ctx: dict, i: int) -> str:
    """해설 첫 문장: 마지막 봉(기준일)에 무슨 신호가 있었나. 사실만 적는다."""
    t = cond.get("type")
    vr = ctx["volr"][i]
    vtxt = f"거래량은 직전 20일 평균의 {vr:.1f}배였어요." if np.isfinite(vr) else ""
    if t == "MA_CROSS_UP":
        return f"마지막 봉에서 종가가 20일선을 위로 넘었고, {vtxt}"
    if t == "MA_CROSS_DOWN":
        return f"마지막 봉에서 종가가 20일선 아래로 내려갔고, {vtxt}"
    if t == "MA_GOLDEN":
        return f"마지막 봉에서 5일선이 20일선을 아래에서 위로 넘었어요. {vtxt}".strip()
    if t == "MA_DEAD":
        return f"마지막 봉에서 5일선이 20일선을 위에서 아래로 넘었어요. {vtxt}".strip()
    if t == "HIGH_BREAK":
        return f"마지막 봉의 종가가 직전 60일 중 가장 높은 종가를 넘었고, {vtxt}"
    if t == "LONG_CANDLE_UP":
        chg = (ctx["close"][i] / ctx["close"][i - 1] - 1) * 100
        return f"마지막 봉은 하루에 {chg:.1f}% 오른 양봉이었고, {vtxt}"
    if t == "RSI_CROSS_UP":
        return f"마지막 봉에서 RSI 가 30 아래에 있다가 {ctx['rsi14'][i]:.0f} 로 올라왔어요."
    if t == "RSI_CROSS_DOWN":
        return f"마지막 봉에서 RSI 가 70 위에 있다가 {ctx['rsi14'][i]:.0f} 로 내려왔어요."
    if t == "MACD_CROSS_UP":
        return "마지막 봉에서 0 아래에 있던 MACD 선이 시그널 선을 아래에서 위로 넘었어요."
    if t == "BB_BREAK_UP":
        return "마지막 봉의 종가가 볼린저밴드 위쪽 선을 넘어섰어요."
    if t == "BB_BREAK_DOWN":
        return "마지막 봉의 종가가 볼린저밴드 아래쪽 선 밑으로 내려갔어요."
    return ""


def load_patterns(session) -> list[dict]:
    """[{id, code, name, cond, side, aux}] — 문제로 낼 수 있는(BASIC·공개) 패턴만.
    pattern 표가 없으면 DEFAULT_PATTERNS 로(id 는 None — 저장하지 않는 --dry-run 용)."""
    from sqlalchemy import text
    rows = None
    try:
        rows = session.execute(text(
            "SELECT id, code, name, condition_json FROM pattern WHERE tier = 'BASIC' AND is_public = 1 ORDER BY id")).all()
    except Exception:
        session.rollback()
    if rows is None:
        items = [{"id": None, "code": c, "name": n, "cond": cond} for c, n, cond in DEFAULT_PATTERNS]
    else:
        items = []
        for r in rows:
            cond = r.condition_json if isinstance(r.condition_json, dict) else json.loads(r.condition_json)
            items.append({"id": r.id, "code": r.code, "name": r.name, "cond": cond})
    out = []
    for p in items:
        meta = TYPE_META.get(p["cond"].get("type"))
        if meta:
            out.append({**p, **meta})
    return out
