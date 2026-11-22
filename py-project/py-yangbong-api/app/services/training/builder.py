"""
차트 퀴즈 문제 생성·패턴 통계(명세 4장). 워커(app/workers/training_worker.py)가 하루 1번 부른다.

  ① 기준일 선정   데이터 마지막 날에서 20거래일 전(D+20 결과가 있어야 하므로)
  ② 패턴 스캔     문제로 낼 수 있는 패턴(BASIC·공개)으로 전 종목
  ③ 후보 필터     EXCLUDE 규칙(아래 _eligible)
  ④ 결과 라벨링   D+20 종가 → ret·direction, 가는 길 최저·최고(장중 저가·고가)
  ⑤ 정규화       기준일(D) 종가 = 100
  ⑥ 난이도       _level
  ⑦ 스냅샷 저장   과거 120봉 + 미래 20봉 + 지표를 JSON 으로 동결

③ 제외 규칙과 한계
  - 일반 주식만(master_stock.group_code='ST' — ETF·ETN·리츠 등 제외), 우선주(코드 끝자리 0 아님)·스팩(이름) 제외
  - 관리종목·거래정지·시장 경고(master_stock.admin_issue / trading_halt / market_stop = 'Y') 제외.
    ⚠ 이 표시는 "지금" 상태다(과거 이력은 없다). 투자경고·위험 이력 데이터도 없어 market_stop 으로만 거른다.
  - 기준일 거래대금 10억 미만 제외
  - 수정주가 이슈: 보여 주는 구간~D+20 사이에 하루 ±30% 를 넘는 종가 변화(상하한가 밖 = 분할·병합 흔적)가 있으면 제외
  - 거래정지 이력: 같은 구간에 거래량 0 인 날이 있으면 제외
  - 기간 중 상장폐지: D+20 봉이 없으면 자연히 빠진다
  - 최근 90일 안에 같은 종목이 이미 출제됐으면 제외(문제 저장 시)
  - 패턴 통계(12개월) 발생 건수가 0 인 패턴은 내지 않는다

데이터: yangbong.stock_ohlcv_daily · master_stock 뷰(sql/yangbong/003). 로컬 --dry-run 은 stock 스키마 같은 이름 표로도 돈다.
"""
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from app.services.training import indicators as ind
from app.services.training import patterns as pat
from app.services.training.scoring import HOLD_DAYS, direction_of

log = logging.getLogger("training_builder")

LOOKBACK = 120            # 문제에 보여 주는 과거 봉 수(기준일 포함)
FUTURE = HOLD_DAYS        # 결과 화면에 이어 그리는 봉 수
MIN_INDEX = 180           # 보여 주는 첫 봉에서 60일선이 이미 있어야 한다(i-119 >= 59) + 여유
MIN_AMOUNT = 1_000_000_000
SPLIT_JUMP = 0.30
REPEAT_DAYS = 90
STAT_WINDOWS = (12, 36, 60)
FAKE_WITHIN = 3           # 속임수 돌파: 신호 뒤 이 봉 수 안에 신호 전날 종가 반대편으로 되돌아감
DEFAULT_PER_DAY = 12      # 기준일 하나에 저장할 문제 수 상한
PER_PATTERN_PER_DAY = 2


@dataclass
class StockSeries:
    code: str
    dates: np.ndarray       # datetime64[D]
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    amt: np.ndarray


# ── 데이터 ────────────────────────────────────────────────────────────────
def load_universe(session) -> set:
    rows = session.execute(text(
        "SELECT stock_code, stock_name, admin_issue, trading_halt, market_stop "
        "FROM master_stock WHERE group_code = 'ST'")).all()
    out = set()
    for r in rows:
        code = (r.stock_code or '').strip()
        if len(code) != 6 or not code.endswith('0'):
            continue   # 우선주(끝자리 5·7·9·K 등)
        if '스팩' in (r.stock_name or ''):
            continue
        if 'Y' in (r.admin_issue, r.trading_halt, r.market_stop):
            continue
        out.add(code)
    return out


def load_series(session, since: date, universe: set) -> dict:
    """종목별 일봉 배열. 날짜 범위 조회라 전 범위 스캔이다(하루 1번 워커 전용)."""
    log.info(f"일봉 읽는 중(since={since}) …")
    res = session.execute(text(
        "SELECT stock_code, trade_date, open_price, high_price, low_price, close_price, volume, amount "
        "FROM stock_ohlcv_daily WHERE trade_date >= :since ORDER BY stock_code, trade_date"), {"since": since})
    df = pd.DataFrame(res.fetchall(), columns=["code", "d", "o", "h", "l", "c", "v", "amt"])
    log.info(f"일봉 {len(df):,}행")
    if df.empty:
        return {}
    df = df[df["code"].isin(universe)]
    out = {}
    for code, g in df.groupby("code", sort=False):
        if len(g) < MIN_INDEX + FUTURE + 1:
            continue
        out[code] = StockSeries(
            code=code,
            dates=g["d"].to_numpy(dtype="datetime64[D]"),
            o=g["o"].to_numpy(float), h=g["h"].to_numpy(float), l=g["l"].to_numpy(float),
            c=g["c"].to_numpy(float), v=g["v"].to_numpy(float), amt=g["amt"].to_numpy(float))
    return out


def trading_dates(series: dict) -> np.ndarray:
    allds = np.unique(np.concatenate([s.dates for s in series.values()])) if series else np.array([], dtype="datetime64[D]")
    return allds


# ── 종목 하나 계산 ───────────────────────────────────────────────────────
def _context(s: StockSeries) -> dict:
    allind = ind.compute_all(s.c)
    return {
        "close": s.c, "open": s.o, "high": s.h, "low": s.l, "vol": s.v,
        "volr": ind.volume_ratio(s.v),
        "ma": allind["ma"], "rsi14": allind["rsi14"],
        "macd": allind["macd"]["macd"], "signal": allind["macd"]["signal"],
        "bbu": allind["bollinger"]["upper"], "bbl": allind["bollinger"]["lower"],
        "_all": allind,
    }


def _bad_window(s: StockSeries) -> np.ndarray:
    """i 를 기준일로 썼을 때 [i-LOOKBACK-20, i+FUTURE] 안에 분할 흔적(±30%) 또는 거래량 0 이 있으면 True."""
    n = len(s.c)
    jump = np.zeros(n, dtype=bool)
    with np.errstate(divide='ignore', invalid='ignore'):
        r = s.c[1:] / s.c[:-1] - 1
    jump[1:] = ~np.isfinite(r) | (np.abs(r) > SPLIT_JUMP)
    zero = s.v <= 0
    flag = (jump | zero).astype(int)
    cs = np.concatenate([[0], np.cumsum(flag)])
    bad = np.ones(n, dtype=bool)
    lo_off, hi_off = LOOKBACK + 20, FUTURE
    for i in range(n):
        a, b = max(0, i - lo_off), min(n, i + hi_off + 1)
        bad[i] = (cs[b] - cs[a]) > 0
    return bad


def _eligible(s: StockSeries, bad: np.ndarray) -> np.ndarray:
    n = len(s.c)
    ok = np.zeros(n, dtype=bool)
    ok[MIN_INDEX:n - FUTURE] = True
    ok &= ~bad
    ok &= s.amt >= MIN_AMOUNT
    return ok


def _outcome(s: StockSeries, i: int) -> dict:
    base = s.c[i]
    ret = (s.c[i + FUTURE] / base - 1) * 100
    lo = (s.l[i + 1:i + FUTURE + 1].min() / base - 1) * 100
    hi = (s.h[i + 1:i + FUTURE + 1].max() / base - 1) * 100
    return {"ret": round(ret, 1), "direction": direction_of(round(ret, 1)),
            "maxDrawdown": round(min(lo, 0.0), 1), "maxGain": round(max(hi, 0.0), 1)}


def _is_fake(s: StockSeries, i: int, side: int, direction: str) -> bool:
    """속임수 돌파: 위로 넘는 신호였는데 FAKE_WITHIN 봉 안에 신호 전날 종가 밑으로 되돌아갔고 결국 -5% 이하(반대도 같다)."""
    ref = s.c[i - 1]
    nxt = s.c[i + 1:i + 1 + FAKE_WITHIN]
    if side > 0:
        return direction == "DOWN" and bool((nxt < ref).any())
    return direction == "UP" and bool((nxt > ref).any())


def _level(p: dict, signals: list[dict], volr: float, outcome: dict, fake: bool) -> int:
    """명세 4-⑥. Lv1 단일 신호+거래량 3배+|결과|≥10 / Lv2 거래량 2배+|결과| 5~10 / Lv3 보조지표 해석·애매한 결과 / Lv4 복합 신호·속임수 돌파.
    복합 신호 = 같은 날 서로 반대쪽 신호가 함께 난 경우. 같은 쪽 신호가 겹치는 건 흔해서(60일 최고가 돌파 + 볼린저 상단 돌파 등)
    그것까지 Lv4 로 보내면 Lv4 가 절반을 넘어 무료(Lv1~2) 문제가 거의 남지 않는다(2026-11-22 실측)."""
    a = abs(outcome["ret"])
    vr = volr if np.isfinite(volr) else 0.0
    if len({x["side"] for x in signals}) > 1 or fake:
        return 4
    if p["aux"]:
        return 3
    if vr >= 3 and a >= 10:
        return 1
    if vr >= 2 and 5 <= a < 10:
        return 2
    if vr >= 3 and a >= 5:
        return 2
    return 3


# ── 스냅샷 ───────────────────────────────────────────────────────────────
def _r(x, nd=2):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _arr(a: np.ndarray, nd=2) -> list:
    return [_r(x, nd) for x in a]


def _indicator_slice(allind: dict, scale: float, a: int, b: int) -> dict:
    sc = lambda arr: _arr(arr[a:b] * scale)  # noqa: E731
    return {
        "ma": {k: sc(v) for k, v in allind["ma"].items()},
        "rsi14": _arr(allind["rsi14"][a:b], 1),
        "macd": {k: _arr(v[a:b] * scale, 3) for k, v in allind["macd"].items()},
        "bollinger": {k: sc(v) for k, v in allind["bollinger"].items()},
    }


def build_snapshot(s: StockSeries, ctx: dict, i: int) -> dict:
    """기준일 종가 = 100 으로 정규화. 거래량은 보여 주는 120봉 평균 = 100 으로 맞춘다(실제 거래량을 감춘다)."""
    scale = 100.0 / s.c[i]
    a, b = i - LOOKBACK + 1, i + 1
    vavg = s.v[a:b].mean() or 1.0
    vs = 100.0 / vavg

    def candles(lo, hi, label):
        return [{"t": label(k), "o": _r(s.o[k] * scale), "h": _r(s.h[k] * scale), "l": _r(s.l[k] * scale),
                 "c": _r(s.c[k] * scale), "v": _r(s.v[k] * vs, 1)} for k in range(lo, hi)]

    snap = {
        "normalizedBase": int(round(s.c[i])),
        "candles": candles(a, b, lambda k: "D" if k == i else f"D-{i - k}"),
        "indicators": _indicator_slice(ctx["_all"], scale, a, b),
        "futureCandles": candles(b, b + FUTURE, lambda k: f"D+{k - i}"),
        "futureIndicators": _indicator_slice(ctx["_all"], scale, b, b + FUTURE),
    }
    snap["candles"][-1]["c"] = 100.0   # 반올림 오차 없이 정확히 100
    return snap


def _explanation(p: dict, ctx: dict, i: int, outcome: dict, fake: bool, others: list) -> str:
    lines = [pat.signal_sentence(p["code"], p["cond"], ctx, i)]
    if others:
        lines.append(f"같은 날 {', '.join(others)} 신호도 함께 나왔어요.")
    if fake:
        lines.append(f"신호 뒤 {FAKE_WITHIN}일 안에 신호 전날 가격 반대편으로 되돌아갔어요.")
    lines.append(f"이후 20일 동안 가장 낮을 때는 기준가보다 {abs(outcome['maxDrawdown']):.1f}% 아래, "
                 f"가장 높을 때는 {outcome['maxGain']:.1f}% 위까지 갔어요.")
    end = 100 + outcome["ret"]
    diff = abs(outcome['ret'])
    lines.append(f"20일째 종가는 {end:.1f}, 기준가 100보다 {diff:.1f}% "
                 f"{'높았어요' if outcome['ret'] > 0 else '낮았어요' if outcome['ret'] < 0 else '그대로였어요'}.")
    return " ".join(x for x in lines if x)


# ── 스캔 ─────────────────────────────────────────────────────────────────
def scan(series: dict, patterns: list[dict]):
    """종목마다 (ctx, eligible, {pattern code: hit 배열}). 메모리를 아끼려고 생성기로 준다."""
    for s in series.values():
        ctx = _context(s)
        ok = _eligible(s, _bad_window(s))
        hits = {p["code"]: pat.detect(p["cond"], ctx) & ok for p in patterns}
        yield s, ctx, hits


def compute_stats(series: dict, patterns: list[dict], last_date: np.datetime64) -> dict:
    """{pattern code: {window: (occ, up, down, flat)}} — 기준일이 마지막 날에서 window 개월 안(그리고 D+20 이 있는 날)."""
    cutoffs = {w: np.datetime64(pd.Timestamp(last_date) - pd.DateOffset(months=w), 'D') for w in STAT_WINDOWS}
    acc = {p["code"]: {w: [0, 0, 0, 0] for w in STAT_WINDOWS} for p in patterns}
    for s, ctx, hits in scan(series, patterns):
        for code, hit in hits.items():
            idx = np.nonzero(hit)[0]
            if not len(idx):
                continue
            ret = (s.c[idx + FUTURE] / s.c[idx] - 1) * 100
            ret = np.round(ret, 1)
            for w, cut in cutoffs.items():
                m = s.dates[idx] >= cut
                if not m.any():
                    continue
                r = ret[m]
                a = acc[code][w]
                a[0] += int(len(r))
                a[1] += int((r >= 5.0).sum())
                a[2] += int((r <= -5.0).sum())
                a[3] += int(((r > -5.0) & (r < 5.0)).sum())
    return acc


def find_candidates(series: dict, patterns: list[dict], base_dates: set) -> list[dict]:
    """base_dates 에 신호가 난 (종목, 패턴) 후보. 한 종목·하루에 신호가 여럿이면 1건(복합 신호)으로 묶는다."""
    out = []
    by_code = {p["code"]: p for p in patterns}
    for s, ctx, hits in scan(series, patterns):
        in_dates = np.isin(s.dates, np.array(sorted(base_dates), dtype="datetime64[D]"))
        fired = {code: np.nonzero(hit & in_dates)[0] for code, hit in hits.items()}
        per_i = {}
        for code, idx in fired.items():
            for i in idx:
                per_i.setdefault(int(i), []).append(code)
        for i, codes in per_i.items():
            primary = by_code[codes[0]]
            outcome = _outcome(s, i)
            fake = _is_fake(s, i, primary["side"], outcome["direction"])
            volr = float(ctx["volr"][i])
            level = _level(primary, [by_code[c] for c in codes], volr, outcome, fake)
            outcome.update({"volRatio": _r(volr, 2), "patternCodes": codes, "fake": fake})
            out.append({
                "stock_code": s.code, "base_date": str(s.dates[i]), "pattern": primary, "level": level,
                "volr": volr if np.isfinite(volr) else 0.0, "outcome": outcome,
                "snapshot": build_snapshot(s, ctx, i),
                "explanation": _explanation(primary, ctx, i, outcome, fake, [by_code[c]["name"] for c in codes[1:]]),
                "hint": pat.HINTS.get(primary["cond"]["type"], "")[:255],
            })
    return out


def pick_questions(cands: list[dict], recent_codes: set, stat_ok: set, per_day: int) -> list[dict]:
    """기준일마다: 최근 90일 출제 종목·통계 0 패턴 제외 → 패턴당 2건(거래량 배수 큰 순) → 하루 per_day 건.
    난이도가 고르게 섞이도록 레벨별로 돌아가며 고른다."""
    picked = []
    for d in sorted({c["base_date"] for c in cands}):
        day = [c for c in cands if c["base_date"] == d
               and c["stock_code"] not in recent_codes and c["pattern"]["code"] in stat_ok]
        day.sort(key=lambda c: -c["volr"])
        per_pat, chosen, used_codes = {}, [], set()
        for c in day:
            k = c["pattern"]["code"]
            if per_pat.get(k, 0) >= PER_PATTERN_PER_DAY or c["stock_code"] in used_codes:
                continue
            per_pat[k] = per_pat.get(k, 0) + 1
            used_codes.add(c["stock_code"])
            chosen.append(c)
        by_lv = {lv: [c for c in chosen if c["level"] == lv] for lv in (1, 2, 3, 4)}
        out = []
        while len(out) < per_day and any(by_lv.values()):
            for lv in (1, 2, 3, 4):
                if by_lv[lv] and len(out) < per_day:
                    out.append(by_lv[lv].pop(0))
        picked.extend(out)
        recent_codes |= {c["stock_code"] for c in out}
    return picked


# ── 저장 ─────────────────────────────────────────────────────────────────
def recent_question_codes(session, since: date) -> set:
    try:
        rows = session.execute(text("SELECT DISTINCT stock_code FROM training_question WHERE base_date >= :d"), {"d": since}).all()
        return {r[0] for r in rows}
    except Exception:
        session.rollback()
        return set()


def existing_base_dates(session, dates: list[str]) -> set:
    if not dates:
        return set()
    try:
        rows = session.execute(text(
            "SELECT DISTINCT base_date FROM training_question WHERE base_date IN :ds").bindparams(
            bindparam('ds', expanding=True)), {"ds": dates}).all()
        return {str(r[0]) for r in rows}
    except Exception:
        session.rollback()
        return set()


def save_stats(session, patterns: list[dict], stats: dict) -> None:
    now = datetime.now().replace(microsecond=0)
    for p in patterns:
        if p["id"] is None:
            continue
        for w, (occ, up, down, flat) in stats[p["code"]].items():
            session.execute(text(
                "INSERT INTO pattern_stat (pattern_id, window_months, occurrences, up_count, down_count, flat_count, computed_at) "
                "VALUES (:pid, :w, :o, :u, :d, :f, :at) ON DUPLICATE KEY UPDATE "
                "occurrences = VALUES(occurrences), up_count = VALUES(up_count), down_count = VALUES(down_count), "
                "flat_count = VALUES(flat_count), computed_at = VALUES(computed_at)"),
                {"pid": p["id"], "w": w, "o": occ, "u": up, "d": down, "f": flat, "at": now})


def save_questions(session, picked: list[dict]) -> int:
    now = datetime.now().replace(microsecond=0)
    n = 0
    for c in picked:
        n += session.execute(text(
            "INSERT IGNORE INTO training_question (pattern_id, stock_code, base_date, level, snapshot_json, outcome_json, "
            "explanation, hint, created_at) VALUES (:pid, :code, :bd, :lv, :snap, :out, :ex, :hint, :at)"),
            {"pid": c["pattern"]["id"], "code": c["stock_code"], "bd": c["base_date"], "lv": c["level"],
             "snap": json.dumps(c["snapshot"], ensure_ascii=False, separators=(',', ':')),
             "out": json.dumps(c["outcome"], ensure_ascii=False, separators=(',', ':')),
             "ex": c["explanation"], "hint": c["hint"], "at": now}).rowcount
    return n


# ── 한 번 실행 ───────────────────────────────────────────────────────────
def run(session, backfill_days: int = 1, per_day: int = DEFAULT_PER_DAY, dry_run: bool = False, stats: bool = True) -> dict:
    """
    backfill_days: 데이터 마지막 날에서 20거래일 전 기준일부터 거슬러 몇 거래일치를 만들지(이미 문제가 있는 기준일은 건너뛴다).
    dry_run: DB 에 쓰지 않고 결과 요약만 돌려준다.
    """
    patterns = pat.load_patterns(session)
    universe = load_universe(session)
    last = session.execute(text("SELECT MAX(trade_date) FROM stock_ohlcv_daily")).scalar()
    # 통계 60개월 + 지표 준비 구간(MIN_INDEX 봉 ≈ 9개월) 을 덮도록
    since = (pd.Timestamp(last) - pd.DateOffset(months=max(STAT_WINDOWS) + 10)).date()
    series = load_series(session, since, universe)
    session.commit()   # 긴 조회 뒤 트랜잭션을 끝내 둔다
    tds = trading_dates(series)
    log.info(f"종목 {len(series):,}개, 거래일 {len(tds)}일, 마지막 {last}")

    result = {"lastDate": str(last), "patterns": len(patterns), "stocks": len(series)}
    stat = compute_stats(series, patterns, tds[-1])   # 문제 생성에도 필요하다(통계 0 패턴 제외)
    stat_ok = {code for code, w in stat.items() if w[12][0] > 0}
    result["stats"] = {code: {w: tuple(v) for w, v in ws.items()} for code, ws in stat.items()}

    # ① 기준일: 마지막 날에서 FUTURE 거래일 전부터 거슬러 backfill_days 개
    base_idx_end = len(tds) - 1 - FUTURE
    bases = [str(tds[k]) for k in range(max(0, base_idx_end - backfill_days + 1), base_idx_end + 1)]
    done = set() if dry_run else existing_base_dates(session, bases)
    todo = [d for d in bases if d not in done]
    result["baseDates"] = todo
    if not todo:
        if not dry_run and stats:
            save_stats(session, patterns, stat)
            session.commit()
        result["saved"] = 0
        return result

    cands = find_candidates(series, patterns, set(todo))
    first = date.fromisoformat(min(todo))
    recent = recent_question_codes(session, first - timedelta(days=REPEAT_DAYS)) if not dry_run else set()
    picked = pick_questions(cands, recent, stat_ok, per_day)
    result["candidates"] = len(cands)
    result["picked"] = len(picked)
    result["levels"] = {lv: sum(1 for c in picked if c["level"] == lv) for lv in (1, 2, 3, 4)}
    result["directions"] = {d: sum(1 for c in picked if c["outcome"]["direction"] == d) for d in ("UP", "FLAT", "DOWN")}
    result["sample"] = picked[:1]
    if dry_run:
        result["saved"] = 0
        return result
    if stats:
        save_stats(session, patterns, stat)
    result["saved"] = save_questions(session, picked)
    session.commit()
    return result
