"""
월별 추천 성과(홈 '전월 추천 성과') 계산 + 저장. API(py-naver-stock-theme)와 배치(py-stock-batch)가 같이 쓴다.

정의 (2026-10-10 사용자 결정):
  - 대상   : 그 달 매수추천에 오른 종목, 종목당 **그 달 첫 추천 1건**.
  - 수익률 : 추천일 종가(trade_buy_target_stock.close) → 그 뒤 HOLD_DAYS 거래일 안의 **최고가**.
             = 기간 중 최대 상승폭. 실제로 그 가격에 팔았다는 뜻은 아니다(화면에도 "N일 내 최고"로 표기).
  - 상위 5%: 수익률 내림차순 상위 ceil(n × 5%) 개의 평균.

"추천일 종가"의 날짜: 추천 ymd 는 배치일이라 휴장일(예: 10/9 한글날)에는 직전 거래일 종가가 들어 있다.
그래서 가격 데이터에서 ymd 이하 마지막 거래일을 기준일로 잡고, 그 다음 거래일부터 HOLD_DAYS 개를 본다.

일봉은 DB 에 전 종목이 없어(trade_shape_train_daily 는 필터된 일부만) yfinance 에서 한 번에 받는다.
※ 야후는 이후에 있었던 액면병합/분할을 과거 가격에 소급 반영한다(auto_adjust=False 여도). DB 종가와 야후 고가를
  바로 나누면 1,000% 같은 가짜 수익률이 나온다(예: 중앙첨단소재 9/1 DB 1,008원 = 야후 10,080원).
  → 수익률은 야후 안에서만 계산(기준일 야후 종가 → 야후 최고가)하고, 최고가는 그 비율로 DB 가격 단위로 환산해 보여준다.

── 저장(trade_buy_target_perf_monthly, sql/30) ──
월말 추천 종목은 다음 달 초 HOLD_DAYS 거래일이 지나야 값이 정해진다. 그래서 계산 결과를 저장할 때 "확정" 여부를 같이 둔다.
  확정 = 계산된 모든 종목이 HOLD_DAYS 를 다 채웠고, 그 달 말일 + FINAL_AFTER_DAYS 가 지났다.
         (야후에 가격이 없는 종목은 계산 대상에서 빠지므로 확정을 막지 않는다)
확정된 달은 다시 계산하지 않는다. 배치(RecoPerformanceJob)가 미확정 달을 매일 다시 계산해 채우고,
API 는 저장된 값을 읽기만 한다(저장된 게 없거나 너무 오래됐을 때만 직접 계산해 저장).
계산 기준(HOLD_DAYS·TOP_PCT)을 바꾸면 해당 월 행을 지우면 된다(다음 조회/배치 때 새 기준으로 재계산).
"""
import json
import logging
import math
import time
from datetime import date, datetime, timedelta

from stock_shared.dao.tradeBuyTargetPerfMonthlyDao import TradeBuyTargetPerfMonthlyDao
from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao

HOLD_DAYS = 5           # 추천 다음 거래일부터 몇 거래일 안의 최고가를 볼지
TOP_PCT = 0.05          # 상위 5%
TOP_LIST = 5            # 목록 개수
FINAL_AFTER_DAYS = 14   # 말일 뒤 이만큼 지나야 확정(HOLD_DAYS 거래일 + 연휴 여유)

_buyTargetDao = TradeBuyTargetStockDao()
_perfDao = TradeBuyTargetPerfMonthlyDao()

# 테이블이 없을 때(sql/30 미적용)만 쓰는 프로세스 메모리 캐시 — 요청마다 야후를 다시 받지 않게.
_FALLBACK_TTL_SECONDS = 6 * 3600
_fallback_cache = {}   # {ym: (계산 시각, payload)}


def prev_month(today: date | None = None) -> str:
    first = (today or date.today()).replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y%m")


def month_range(ym: str) -> tuple[date, date]:
    start = datetime.strptime(ym + "01", "%Y%m%d").date()
    nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, nxt - timedelta(days=1)


# ── 계산 ──────────────────────────────────────────────────────────

def compute_monthly(session, ym: str) -> tuple[dict, bool]:
    """그 달 성과를 계산한다. 반환: (화면 응답 payload, 확정 여부). DB 에 쓰지 않는다."""
    start, end = month_range(ym)
    targets = _buyTargetDao.select_first_targets_in_range(
        session, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))

    results = _evaluate(targets, start, end)
    results.sort(key=lambda r: r["max_return"], reverse=True)

    n = len(results)
    top_n = max(1, math.ceil(n * TOP_PCT)) if n else 0
    top = results[:top_n]
    payload = {
        "ym": ym,
        "hold_days": HOLD_DAYS,
        "evaluated_count": n,                      # 성과를 계산한 종목 수
        "target_count": len(targets),              # 그 달 추천 종목 수(가격을 못 받은 종목 포함)
        "top_pct": int(TOP_PCT * 100),
        "top_count": top_n,
        "top_avg_return": round(sum(r["max_return"] for r in top) / top_n, 2) if top_n else None,
        "avg_return": round(sum(r["max_return"] for r in results) / n, 2) if n else None,
        "top_list": results[:TOP_LIST],
    }
    final = (
        n > 0
        and all(r["days_observed"] >= HOLD_DAYS for r in results)
        and date.today() >= end + timedelta(days=FINAL_AFTER_DAYS)
    )
    return payload, final


def _evaluate(targets: list, start: date, end: date) -> list:
    # yfinance 는 이 모듈을 쓰는 두 앱(API·배치)에만 의존성이 있다 → 지연 import
    import pandas as pd
    import yfinance as yf

    tickers = {}
    for t in targets:
        suffix = t.get("stock_type_yf")
        if suffix:
            tickers[t["stock_code"]] = f"{t['stock_code']}.{suffix}"
    if not tickers:
        return []

    # 월초 이전 며칠(기준일 찾기용) ~ 월말 이후 HOLD_DAYS 거래일이 들어갈 만큼(휴장 감안 넉넉히)
    prices = yf.download(
        list(tickers.values()),
        start=(start - timedelta(days=10)).isoformat(),
        end=(end + timedelta(days=HOLD_DAYS * 2 + 10)).isoformat(),
        group_by="ticker", auto_adjust=False, progress=False, threads=True,
    )

    results = []
    for t in targets:
        ticker = tickers.get(t["stock_code"])
        entry = float(t["close"]) if t.get("close") else None
        if not ticker or not entry:
            continue
        try:
            df = prices[ticker] if isinstance(prices.columns, pd.MultiIndex) else prices
            df = df[["High", "Close"]].dropna()
        except KeyError:
            continue
        if df.empty:
            continue

        rec_day = pd.Timestamp(datetime.strptime(t["ymd"], "%Y%m%d"))
        idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
        base_pos = idx.searchsorted(rec_day, side="right") - 1   # ymd 이하 마지막 거래일
        fwd = df.iloc[base_pos + 1: base_pos + 1 + HOLD_DAYS] if base_pos >= 0 else df.iloc[0:0]
        if fwd.empty:
            continue   # 추천 뒤 거래일이 아직 없다

        base_close = float(df["Close"].iloc[base_pos])
        if base_close <= 0:
            continue
        peak_i = int(fwd["High"].values.argmax())
        ratio = float(fwd["High"].iloc[peak_i]) / base_close
        peak_day = fwd.index[peak_i]
        results.append({
            "stock_code": t["stock_code"],
            "stock_name": t["stock_name"],
            "ymd": t["ymd"],
            "entry_price": entry,
            "peak_price": round(entry * ratio),          # DB(추천 당시) 가격 단위로 환산
            "peak_ymd": peak_day.strftime("%Y%m%d"),
            "max_return": round((ratio - 1) * 100, 2),
            "days_observed": len(fwd),                   # HOLD_DAYS 보다 작으면 아직 진행 중
        })
    logging.info(f"reco performance {start:%Y%m}: {len(results)}/{len(targets)} evaluated")
    return results


# ── 저장 조회 ─────────────────────────────────────────────────────

def get_or_compute(session, ym: str, max_age_hours: float | None) -> dict:
    """
    저장된 값이 쓸 만하면 그대로, 아니면 계산해 저장하고 돌려준다.
      - 확정 행            → 그대로
      - 미확정 행, max_age_hours 안에 계산됨 → 그대로 (배치가 매일 갱신)
      - 그 외(행 없음·오래됨, max_age_hours=0) → 계산 + 저장
    테이블이 없으면(sql/30 미적용) 계산만 해서 돌려준다 — 화면은 깨지지 않는다.
    commit 은 호출측(API 요청 종료 / 배치 Job)이 한다.
    """
    try:
        row = _perfDao.select_by_ym(session, ym)
    except Exception as e:
        logging.warning(f"[reco_performance] 저장값 조회 실패(테이블 미적용?) — 메모리 캐시로 동작: {e}")
        session.rollback()
        cached = _fallback_cache.get(ym)
        if cached and time.time() - cached[0] < _FALLBACK_TTL_SECONDS:
            return cached[1]
        payload = compute_monthly(session, ym)[0]
        _fallback_cache[ym] = (time.time(), payload)
        return payload

    if row:
        fresh = (max_age_hours is not None and max_age_hours > 0
                 and datetime.now() - row["calculated_at"] < timedelta(hours=max_age_hours))
        if row["final_flag"] == "Y" or fresh:
            return json.loads(row["payload"])

    payload, final = compute_monthly(session, ym)
    _perfDao.upsert(session, ym, json.dumps(payload, ensure_ascii=False), final)
    return payload


def refresh_month(session, ym: str, force: bool = False) -> dict:
    """배치용: 확정 전이면(또는 force) 다시 계산해 저장. 반환: {ym, final, skipped, evaluated_count}."""
    row = _perfDao.select_by_ym(session, ym)
    if row and row["final_flag"] == "Y" and not force:
        return {"ym": ym, "final": True, "skipped": True,
                "evaluated_count": json.loads(row["payload"]).get("evaluated_count")}
    payload, final = compute_monthly(session, ym)
    _perfDao.upsert(session, ym, json.dumps(payload, ensure_ascii=False), final)
    return {"ym": ym, "final": final, "skipped": False, "evaluated_count": payload["evaluated_count"]}
