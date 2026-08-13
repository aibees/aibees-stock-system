"""
새 매수추천 알고리즘(kospi1.py, 2026-08-08 대조군 분석 반영) 오프라인 재현 테스트.

라이브 KIS API를 호출하지 않고, 이미 DB(trade_candle_data)에 적재된 종목만 대상으로
지정한 과거 날짜(또는 날짜 구간) 기준 매수 판정을 재현해 trade_buy_target_stock_test
테이블에 저장한다. 운영 테이블(trade_buy_target_stock)은 절대 건드리지 않는다.

⚠ 범위 한계:
    trade_candle_data 에는 '과거에 한 번이라도 매수추천에 등장했던' 종목만 적재돼
    있다(TradeCandleBackfillJob 이 채움). 즉 전체 시장 스캔이 아니라 "이미 알고
    있는 종목 풀"에서 새 알고리즘이 그 날짜에 어떻게 판단했을지 재현하는 용도다.
    전체 시장 스캔이 필요하면 StockBuyCheckJob.run_batch(end_date=...)를 라이브
    KIS API로 직접 실행해야 한다(이 스크립트보다 느리고 API 호출량이 크다).

사전조건:
    trade_buy_target_stock_test 테이블이 이미 생성돼 있어야 함.
    (py-project/sql/trade_buy_target_stock_test.sql 을 DB 관리 클라이언트로 직접 실행)

사용법(py-stock-batch 프로젝트 루트에서):
    # 단일 날짜
    python -m app.test.run_test_buy_check --date 2026-06-15
    python -m app.test.run_test_buy_check --date 20260615 --quiet

    # 날짜 구간 연속 수행 (거래일마다 반복 — trade_candle_data 에 존재하는 날짜만)
    python -m app.test.run_test_buy_check --start-date 20260401 --end-date 20260722
    python -m app.test.run_test_buy_check --start-date 20260401 --end-date 20260722 --quiet

    python -m app.test.run_test_buy_check            # 실행 중 날짜 입력 프롬프트(단일)
"""
import argparse
import pprint
from datetime import datetime

from sqlalchemy import select, text

from app.config.database import dbConn
from app.batches.services.userService import UserService
from app.batches.services.stockService import StockService
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from stock_shared.dao.tradeBuyTargetStockTestDao import TradeBuyTargetStockTestDao
from stock_shared.models.tradeBuyTargetStock import TradeBuyTargetStock
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.kospi1 import KospiStrategy1

MIN_ROWS_FOR_REGIME = 30   # 이보다 히스토리가 적으면 regime/vol_avg 신뢰도 낮음(경고만, 차단 안 함)
# 최근 N일 내 재추천 종목 rank_no 페널티(제외 아님). StockBuyCheckJob.py의
# REPEAT_PENALTY_DAYS와 같은 값으로 맞춰둘 것(테스트가 운영 로직을 그대로 재현하도록).
REPEAT_PENALTY_DAYS = 5


def _normalize_ymd(raw: str) -> str:
    raw = raw.strip().replace('-', '')
    if len(raw) != 8 or not raw.isdigit():
        raise ValueError(f"날짜 형식 오류: '{raw}' (예: 20260615 또는 2026-06-15)")
    datetime.strptime(raw, '%Y%m%d')  # 유효성 검증(존재하는 날짜인지)
    return raw


def _stock_universe(session) -> list[dict]:
    """추천 이력에 한 번이라도 등장한 종목(= trade_candle_data 적재 대상과 사실상 동일)."""
    return TradeBuyTargetStockDao().select_target_codes_since(session, '20000101')


def _trading_days(session, start_ymd: str, end_ymd: str) -> list[str]:
    """trade_candle_data 에 실제 존재하는 거래일(YYYYMMDD) 오름차순.
    (전 종목 교집합이 아니라, 최소 1종목이라도 그 날짜 캔들이 있으면 포함)"""
    start_dt = f"{start_ymd[:4]}-{start_ymd[4:6]}-{start_ymd[6:]} 00:00:00"
    end_dt = f"{end_ymd[:4]}-{end_ymd[4:6]}-{end_ymd[6:]} 23:59:59"
    stmt = text(
        "SELECT DISTINCT SUBSTRING(datetime, 1, 10) AS d FROM trade_candle_data "
        "WHERE datetime >= :s AND datetime <= :e ORDER BY d"
    )
    rows = session.execute(stmt, {'s': start_dt, 'e': end_dt}).fetchall()
    return [r[0].replace('-', '') for r in rows]


def _latest_fin(session, stock_code: str, target_ymd: str) -> dict:
    """target_ymd 이전 가장 최근 매수추천 스냅샷에서 재무 지표를 끌어온다(오프라인 근사치).
    실시간 KIS 재무 API를 안 쓰므로 당일 최신값이 아닐 수 있음 — 스코어의 fund 부분은 참고용."""
    stmt = (
        select(TradeBuyTargetStock)
        .where(TradeBuyTargetStock.stock_code == stock_code,
               TradeBuyTargetStock.ymd <= target_ymd)
        .order_by(TradeBuyTargetStock.ymd.desc())
        .limit(1)
    )
    row = session.execute(stmt).scalars().first()
    if not row:
        return {'eps': None, 'per': None, 'pbr': None, 'roe': None, 'peg': None}
    return {'eps': row.eps, 'per': row.per, 'pbr': row.pbr, 'roe': row.roe, 'peg': row.peg}


def _inject_vol_avg_and_regime(rows: list[dict], strategy: KospiStrategy1) -> None:
    """DB candle 에는 vol_avg/downtrend_ratio 컬럼이 없으므로 즉석 계산해 주입한다.
    (backtester.py KisBacktester.run_one 과 동일 로직 — 라이브 경로는 compute_indicator_df 가 채움)"""
    w = getattr(strategy, 'vol_ma_window', 20)
    vols = [float(r.get('volume') or 0) for r in rows]
    for i in range(len(rows)):
        rows[i]['vol_avg'] = (sum(vols[i + 1 - w:i + 1]) / w) if i + 1 >= w else 0.0

    rw = int(getattr(strategy, 'regime_window', 90))
    for i in range(len(rows)):
        lo = max(0, i + 1 - rw)
        below = total = 0
        for j in range(lo, i + 1):
            e60 = rows[j].get('ema60')
            if e60 in (None, 0, '0') or float(e60) == 0.0:
                continue
            total += 1
            if float(rows[j].get('close') or 0) < float(e60):
                below += 1
        rows[i]['downtrend_ratio'] = (below / total) if total > 0 else 0.0


def _default_user_info() -> UserOptionMeta:
    ui = UserOptionMeta()
    ui.vol_limit = 0
    ui.vol_surge = 3.0
    ui.delay_date = 5
    ui.macd_recent_day = 20
    ui.bb_over_recent_day = 7
    return ui


def _run_one_date(session, target_ymd: str, universe: list[dict], user_info: UserOptionMeta,
                   candleDao: TradeCandleDataDao, testDao: TradeBuyTargetStockTestDao,
                   verbose: bool) -> list[dict]:
    """target_ymd 하루치 매수판정을 재현해 테스트 테이블에 upsert. 저장된 결과 리스트 반환."""
    target_dt_prefix = f"{target_ymd[:4]}-{target_ymd[4:6]}-{target_ymd[6:]}"

    result_list = []
    skipped_no_data = skipped_hold = 0

    for stock in universe:
        stock_code = stock['stock_code']
        stock_name = stock.get('stock_name', '')

        rows = candleDao.select_candle_data(session, {
            'coin_code': stock_code, 'end_date': target_dt_prefix,
        })
        if len(rows) < 2 or rows[-1]['datetime'][:10] != target_dt_prefix:
            skipped_no_data += 1
            continue  # 그 날짜에 데이터가 없거나(비영업일 등) 직전봉이 없음

        strategy = KospiStrategy1()  # 종목별 독립 인스턴스(상태 공유 방지)
        _inject_vol_avg_and_regime(rows, strategy)
        if len(rows) < MIN_ROWS_FOR_REGIME and verbose:
            print(f"  [주의] {stock_name}({stock_code}) 히스토리 {len(rows)}봉 — regime/vol_avg 신뢰도 낮음")

        prev_info = UserCoinInfo.from_dict(rows[-2])
        coin_info = UserCoinInfo.from_dict(rows[-1])

        res = strategy.get_action_with_prev('watch', prev_info, coin_info, user_info)
        if not res or res.get('action_type') == 'HOLD':
            skipped_hold += 1
            continue

        res['stock_code'] = stock_code
        res['stock_name'] = stock_name
        res['ymd'] = target_ymd
        res['fin'] = _latest_fin(session, stock_code, target_ymd)
        result_list.append(res)
        if verbose:
            print(f"  → BUY 후보: {stock_name}({stock_code}) action={res['action_type']}")

    if result_list:
        try:
            from datetime import timedelta
            dt = datetime.strptime(target_ymd, '%Y%m%d')
            penalty_from = (dt - timedelta(days=REPEAT_PENALTY_DAYS)).strftime('%Y%m%d')
            penalty_to = (dt - timedelta(days=1)).strftime('%Y%m%d')
            recent_codes = testDao.select_recent_codes(session, penalty_from, penalty_to) \
                if penalty_to >= penalty_from else set()
        except Exception as e:
            print(f"  [주의] 최근 추천 이력 조회 실패(재추천 페널티 미적용): {e}")
            recent_codes = set()
        result_list = StockService().assign_ranks(result_list, recent_codes=recent_codes)
        if verbose:
            for r in sorted(result_list, key=lambda x: x.get('rank_no', 10 ** 9)):
                pprint.pprint({k: r.get(k) for k in
                               ('stock_code', 'stock_name', 'action_type', 'score', 'rank_no')})

    deleted = testDao.delete_by_ymd(session, target_ymd)
    testDao.upsert_trade_buy_target_stock(session, result_list)
    print(f"[{target_ymd}] 저장 완료: 기존 {deleted}건 삭제 → 신규 {len(result_list)}건 저장 "
          f"(데이터없음-스킵 {skipped_no_data} / HOLD {skipped_hold})")
    return result_list


def run_range(start_date: str, end_date: str, verbose: bool = True) -> dict:
    """start_date ~ end_date(포함) 구간의 모든 거래일을 순회하며 매수판정을 재현/저장한다.
    단일 날짜만 필요하면 start_date == end_date 로 호출(= run() 과 동일).
    반환: {ymd: [result, ...]}. 날짜 하나가 실패해도 나머지 날짜는 계속 진행한다."""
    start_ymd = _normalize_ymd(start_date)
    end_ymd = _normalize_ymd(end_date)
    if start_ymd > end_ymd:
        raise ValueError(f"start_date({start_ymd}) 가 end_date({end_ymd}) 보다 늦습니다.")

    session = dbConn.get_session()
    candleDao = TradeCandleDataDao()
    testDao = TradeBuyTargetStockTestDao()
    userServiceImpl = UserService()

    all_results = {}
    trading_days = []
    try:
        try:
            user_info = userServiceImpl.get_user_options(session)
        except Exception as e:
            print(f"[경고] user_options 조회 실패, 기본값 사용: {e}")
            user_info = _default_user_info()

        universe = _stock_universe(session)
        trading_days = _trading_days(session, start_ymd, end_ymd)
        print(f"[{start_ymd}~{end_ymd}] 거래일 {len(trading_days)}개 × 대상 종목 {len(universe)}개")
        if not trading_days:
            print("  해당 구간에 trade_candle_data 가 없습니다. 백필(TradeCandleBackfillJob) 여부를 확인하세요.")

        for idx, target_ymd in enumerate(trading_days, start=1):
            print(f"\n--- ({idx}/{len(trading_days)}) {target_ymd} ---")
            try:
                results = _run_one_date(session, target_ymd, universe, user_info,
                                        candleDao, testDao, verbose)
                session.commit()
                all_results[target_ymd] = results
            except Exception as e:
                session.rollback()
                print(f"  [실패] {target_ymd}: {e}")
                continue  # 한 날짜 실패해도 나머지 날짜는 계속 진행
    finally:
        session.remove()

    total = sum(len(v) for v in all_results.values())
    print(f"\n===== 완료: {len(all_results)}/{len(trading_days)}개 날짜 처리, 총 추천 {total}건 저장 =====")
    return all_results


def run(target_date: str, verbose: bool = True) -> list[dict]:
    """단일 날짜 실행(하위호환용 wrapper). run_range 의 특수 케이스."""
    target_ymd = _normalize_ymd(target_date)
    results = run_range(target_ymd, target_ymd, verbose=verbose)
    return results.get(target_ymd, [])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="새 매수추천 알고리즘 오프라인 재현 테스트")
    parser.add_argument('--date', help='단일 기준일(YYYYMMDD 또는 YYYY-MM-DD).')
    parser.add_argument('--start-date', help='구간 시작일. --end-date 와 함께 쓰면 거래일마다 연속 수행.')
    parser.add_argument('--end-date', help='구간 종료일(포함). --start-date 만 주면 그 하루만 실행.')
    parser.add_argument('--quiet', action='store_true', help='종목별 상세 로그 생략')
    args = parser.parse_args()

    if args.start_date:
        end = args.end_date or args.start_date
        run_range(args.start_date, end, verbose=not args.quiet)
    else:
        date_input = args.date or input(
            "기준 날짜 입력 (예: 20260615, 구간 실행은 --start-date/--end-date 옵션 사용): "
        )
        run(date_input, verbose=not args.quiet)
