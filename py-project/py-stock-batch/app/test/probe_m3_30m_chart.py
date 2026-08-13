"""
M3 사전검증: python-kis(pykis 2.1.6)로 30분봉 250개 이상 확보 가능한가?

대상: KODEX 코스피100(237350), KODEX 인버스(114800)

검증 항목
  A. pykis 당일 분봉(day_chart / FHKST03010200) 최대 건수 + period=30 의 실제 동작
  B. KIS 원시 API 주식일별분봉조회(FHKST03010230) 가용 여부 / 소급 가능 일수
  C. 1분봉 → 30분봉 resample 로 250개 누적 가능 여부

실행:
  poetry run python -m app.test.probe_m3_30m_chart
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd

from app.ext_services.kis.KisEngine import KisEngine

CODES = ["237350", "114800"]
TARGET_BARS = 250
BAR_MIN = 30


# ──────────────────────────────────────────────────────────────
# A. pykis 당일 분봉
# ──────────────────────────────────────────────────────────────
def probe_day_chart(engine: KisEngine, code: str):
    stock = engine.kis.stock(code)

    ch1 = stock.chart(period=1)  # 당일 1분봉 전체
    print(f"[A] {code} day_chart period=1 → {len(ch1.bars)} bars")
    if ch1.bars:
        print(f"     범위 {ch1.bars[0].time} ~ {ch1.bars[-1].time}")

    ch30 = stock.chart(period=30)  # 주의: 집계가 아니라 30개마다 1건 샘플링
    print(f"[A] {code} day_chart period=30 → {len(ch30.bars)} bars (샘플링임, OHLC 집계 아님)")
    for b in ch30.bars[:3]:
        print(f"     {b.time} O{b.open} H{b.high} L{b.low} C{b.close} V{b.volume}")

    return ch1


# ──────────────────────────────────────────────────────────────
# B. 원시 API: 주식일별분봉조회 (과거일자 분봉)
#    path : /uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice
#    tr_id: FHKST03010230, 1회 최대 120건 (해당 일자, 지정시각 이전 역순)
# ──────────────────────────────────────────────────────────────
def fetch_daily_minute(engine: KisEngine, code: str, ymd: str, hhmmss: str = "153000"):
    # KisEngine 에 구현된 것과 동일 경로를 쓴다.
    # (kis.fetch() 는 KisDynamicDict 를 반환해 .get() 이 없다 → request().json())
    return engine._fetch_day_minutes_page(code, ymd, hhmmss)


def probe_raw_backfill(engine: KisEngine, code: str, max_days: int = 40):
    """며칠까지 소급되는지 탐색."""
    ok_days, d, checked = [], date.today(), 0
    while checked < max_days and len(ok_days) < 25:
        if d.weekday() < 5:
            ymd = d.strftime("%Y%m%d")
            try:
                rows = fetch_daily_minute(engine, code, ymd)
                if rows:
                    ok_days.append((ymd, len(rows)))
            except Exception as e:
                print(f"[B] {code} {ymd} 실패: {type(e).__name__}: {e}")
                break
            checked += 1
        d -= timedelta(days=1)
    print(f"[B] {code} 소급 성공 영업일 {len(ok_days)}일 (1회 호출당 건수)")
    for ymd, n in ok_days[:5]:
        print(f"     {ymd}: {n}건")
    if ok_days:
        print(f"     최고(oldest) 확인일: {ok_days[-1][0]}")
    return ok_days


# ──────────────────────────────────────────────────────────────
# C. 1분봉 → 30분봉 resample
# ──────────────────────────────────────────────────────────────
def collect_1m_for_day(engine: KisEngine, code: str, ymd: str) -> pd.DataFrame:
    """하루치 1분봉을 커서(시각) 내려가며 전량 수집. 1회 120건 제한 대응."""
    seen: dict[str, dict] = {}
    cursor = "153000"
    for _ in range(6):  # 390분 / 120 ≈ 4회 + 여유
        rows = fetch_daily_minute(engine, code, ymd, cursor)
        if not rows:
            break
        new = 0
        for r in rows:
            k = r["stck_bsop_date"] + r["stck_cntg_hour"]
            if k not in seen:
                seen[k] = r
                new += 1
        if new == 0:
            break
        oldest = min(r["stck_cntg_hour"] for r in rows)
        t = datetime.strptime(oldest, "%H%M%S") - timedelta(minutes=1)
        cursor = t.strftime("%H%M%S")
        if cursor < "090000":
            break

    if not seen:
        return pd.DataFrame()
    recs = [seen[k] for k in sorted(seen)]
    return pd.DataFrame({
        "dt": [datetime.strptime(k, "%Y%m%d%H%M%S") for k in sorted(seen)],
        "open": [float(r["stck_oprc"]) for r in recs],
        "high": [float(r["stck_hgpr"]) for r in recs],
        "low": [float(r["stck_lwpr"]) for r in recs],
        "close": [float(r["stck_prpr"]) for r in recs],
        "volume": [int(r["cntg_vol"]) for r in recs],
    }).set_index("dt")


def resample_30m(df1m: pd.DataFrame) -> pd.DataFrame:
    if df1m.empty:
        return df1m
    out = df1m.resample(f"{BAR_MIN}min", origin="start_day", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return out


def probe_accumulate(engine: KisEngine, code: str, days: list[str]):
    frames = []
    total = 0
    for ymd in days:
        df1 = collect_1m_for_day(engine, code, ymd)
        df30 = resample_30m(df1)
        frames.append(df30)
        total += len(df30)
        print(f"[C] {code} {ymd}: 1m {len(df1)}건 → 30m {len(df30)}건 (누적 {total})")
        if total >= TARGET_BARS:
            break
    all30 = pd.concat(frames).sort_index() if frames else pd.DataFrame()
    print(f"[C] {code} 최종 30분봉 {len(all30)}개 / 목표 {TARGET_BARS} → "
          f"{'✅ 충족' if len(all30) >= TARGET_BARS else '❌ 미달'}")
    if not all30.empty:
        print(all30.head(3))
        print(all30.tail(3))
    return all30


def main():
    engine = KisEngine()
    for code in CODES:
        print("=" * 70)
        print(f"### {code}")
        print("=" * 70)
        try:
            probe_day_chart(engine, code)
        except Exception as e:
            print(f"[A] 실패: {type(e).__name__}: {e}")

        days = []
        try:
            days = [ymd for ymd, _ in probe_raw_backfill(engine, code)]
        except Exception as e:
            print(f"[B] 실패: {type(e).__name__}: {e}")

        if days:
            try:
                probe_accumulate(engine, code, days)
            except Exception as e:
                print(f"[C] 실패: {type(e).__name__}: {e}")
        else:
            print("[C] 건너뜀 — 과거 분봉 API 미가용")


if __name__ == "__main__":
    main()
