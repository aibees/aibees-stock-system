"""
trade_buy_target_stock(매수추천 누적)에 담긴 종목들의 과거 캔들을 일괄 백필.

정책:
  - 각 stock_code 의 '가장 첫 추천일'(MIN(ymd)) 을 구한 뒤,
    그 PRE_DAYS(기본 200일) 전부터 오늘까지 trade_candle_data 에 적재.
  - 적재는 app.main 의 'acc' 분기와 '동일한' 메커니즘을 사용:
      test_5.test_backtest_insert_one(stock_code, end_date)
        → KIS 로 end_date 기준 LOOKBACK(250)일 back OHLCV 조회
        → compute_indicator_df 로 지표 계산
        → trade_candle_data 에 upsert
  - KIS 일봉 API 는 1콜당 반환 봉수가 제한적이라, end_date 를 STEP_DAYS 씩
    뒤로 밀며 여러 번 호출해 '겹치며' 채운다. upsert 라 중복은 안전.

사용:
    poetry run python -m app.test.collect_buy_target_backfill            # 전체 종목
    poetry run python -m app.test.collect_buy_target_backfill 000660     # 특정 종목만
    poetry run python -m app.test.collect_buy_target_backfill 000660 2026-07-22  # end_date 지정
"""
import sys
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text

# test_5 는 KisEngine·DB 세션·upsert 로직을 모두 초기화해 들고 있음(= acc 분기가 쓰는 그 모듈)
from app.test import test_5

# ── 튜닝 파라미터 ────────────────────────────────────────────────────
PRE_DAYS  = 200    # 첫 추천일 기준 며칠 전부터 수집할지
LOOKBACK  = 250    # test_backtest_insert_one 의 1콜 조회 범위(고정값과 동일하게)
STEP_DAYS = 60     # end_date 를 뒤로 미는 간격(acc 분기 ~70일과 유사, 겹쳐서 공백 방지)
SLEEP_SEC = 1.5    # KIS rate limit 완충(콜 간 대기)
# ────────────────────────────────────────────────────────────────────


def _first_reco_rows(only_code: str = None):
    """stock_code 별 가장 첫(min) 추천일 조회. [(stock_code, first_ymd), ...]"""
    sql = "SELECT stock_code, MIN(ymd) AS first_ymd FROM trade_buy_target_stock"
    params = {}
    if only_code:
        sql += " WHERE stock_code = :c"
        params['c'] = only_code
    sql += " GROUP BY stock_code ORDER BY stock_code"
    return test_5.session.execute(text(sql), params).all()


def collect_one(stock_code: str, first_ymd: str, end_date: date = None) -> int:
    """단일 종목: (첫추천일 - PRE_DAYS) ~ end_date 범위를 창(window) 겹쳐가며 적재."""
    first_dt = datetime.strptime(first_ymd, '%Y%m%d').date()
    start_target = first_dt - timedelta(days=PRE_DAYS)
    end_dt = end_date or date.today()

    print(f'▶ {stock_code}: 첫추천 {first_dt} → 수집 {start_target} ~ {end_dt}', flush=True)
    windows = 0
    while True:
        test_5.test_backtest_insert_one(stock_code, end_dt.strftime('%Y-%m-%d'), lookback_days=LOOKBACK)
        windows += 1
        time.sleep(SLEEP_SEC)
        # 이번 창의 시작이 목표 시작일을 이미 덮었으면 종료
        if (end_dt - timedelta(days=LOOKBACK)) <= start_target:
            break
        end_dt = end_dt - timedelta(days=STEP_DAYS)
    print(f'  ✅ {stock_code} 완료 ({windows} windows)', flush=True)
    return windows


def run(only_code: str = None, end_date: str = None) -> None:
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    rows = _first_reco_rows(only_code)
    total = len(rows)
    print(f'대상 종목 {total}건 (PRE_DAYS={PRE_DAYS}, STEP_DAYS={STEP_DAYS}, LOOKBACK={LOOKBACK})', flush=True)

    ok = fail = 0
    for i, (code, first_ymd) in enumerate(rows, 1):
        print(f'[{i}/{total}]', end=' ', flush=True)
        try:
            collect_one(code, first_ymd, end_dt)
            ok += 1
        except Exception as e:
            fail += 1
            print(f'  ❌ {code} 실패: {type(e).__name__}: {e}', flush=True)
            try:
                test_5.session.rollback()
            except Exception:
                pass
    print(f'=== 백필 완료: 성공 {ok} / 실패 {fail} / 전체 {total} ===', flush=True)


if __name__ == '__main__':
    args = sys.argv[1:]
    code = args[0] if len(args) >= 1 else None
    edate = args[1] if len(args) >= 2 else None
    run(code, edate)
