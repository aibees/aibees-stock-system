"""
KIS 백테스트 러너.

사전조건: test_5.test_backtest_insert(end_date) 로 trade_candle_data 에 지표가 적재돼 있어야 함.
사용:
    from app.test.test_backtest import run, run_all
    run('005930')          # 단일 종목
    run_all()              # stock master 전체 (DB 적재된 종목만)
"""
import pprint

from app.config.database import dbConn
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from app.domain.dto.userOptionMeta import UserOptionMeta
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService
from app.ext_services.kis.component.KospiStrategy1 import KospiStrategy1
from app.ext_services.kis.component.KospiStrategy2 import KospiStrategy2
from app.ext_services.kis.component.KisBacktester import KisBacktester

session = dbConn.get_session()
daoImpl = TradeCandleDataDao()
stockServiceImpl = StockService()
userServiceImpl = UserService()


def _user_info() -> UserOptionMeta:
    try:
        return userServiceImpl.get_user_options(session)
    except Exception:
        # 옵션 조회 실패 시 최소 기본값
        ui = UserOptionMeta()
        ui.vol_limit = 0
        ui.vol_surge = 3.0
        ui.delay_date = 5
        ui.macd_recent_day = 20
        ui.bb_over_recent_day = 7
        return ui


def run(coin_code: str, start_date: str = None, end_date: str = None, fee_rate: float = 0.0015,
        init_cash: int = 1_000_000) -> dict:
    rows = daoImpl.select_candle_data(session, {
        'coin_code': coin_code, 'start_date': start_date, 'end_date': end_date,
    })
    if not rows:
        print(f'데이터 없음: {coin_code}')
        return {}

    bt = KisBacktester(strategy=KospiStrategy1(), fee_rate=fee_rate)
    result = bt.run_one(coin_code, rows, _user_info())

    summary = {k: v for k, v in result.items() if k != 'trade_list'}
    print('===== 단일 종목 백테스트 =====')
    pprint.pprint(summary)
    print(f'--- 매매 {len(result["trade_list"])}건 ---')

    # 가상 자금 시뮬레이션 (전량 매수/매도, 수수료 0.11% 편도, 정수 주 매수)
    BUY_FEE  = 0.0011
    SELL_FEE = 0.0011
    cash = init_cash
    for t in result['trade_list']:
        entry_p = t['entry_price']
        exit_p  = t['exit_price']
        shares  = int(cash / (entry_p * (1 + BUY_FEE)))   # 수수료 포함 살 수 있는 정수 주
        buy_cost  = shares * entry_p * (1 + BUY_FEE)
        sell_recv = shares * exit_p  * (1 - SELL_FEE)
        cash = cash - buy_cost + sell_recv                  # 잔여 현금 + 매도 수령액
        pnl = sell_recv - buy_cost
        print(f"{t['entry_dt']} {t['entry_action']} @{entry_p:.0f} x{shares}주 -> "
              f"{t['exit_dt']} {t['exit_reason']} @{exit_p:.0f} "
              f"| {t['bars_held']}bars | {t['ret_net'] * 100:+.2f}% "
              f"| 손익 {pnl:+,.0f}원 → 잔액 {cash:,.0f}원")

    profit = cash - init_cash
    profit_pct = (cash / init_cash - 1) * 100
    print(f'\n[가상 자금] 시작 {init_cash:,}원 → 최종 {cash:,.0f}원 '
          f'({profit:+,.0f}원 / {profit_pct:+.2f}%)')
    return result


def run_all(start_date: str = None, end_date: str = None, fee_rate: float = 0.0015) -> dict:
    bt = KisBacktester(strategy=KospiStrategy1(), fee_rate=fee_rate)
    user_info = _user_info()
    stock_list = stockServiceImpl.get_stock_master_list(session, 'batches')

    results = []
    for stock in stock_list:
        code = stock.get('stock_code')
        rows = daoImpl.select_candle_data(session, {
            'coin_code': code, 'start_date': start_date, 'end_date': end_date,
        })
        if not rows:
            continue
        results.append(bt.run_one(code, rows, user_info))

    overall = bt.aggregate(results)

    print('===== 전체 백테스트 요약 =====')
    pprint.pprint({k: v for k, v in overall.items() if k != 'trade_list'})

    # 종목별 수익률 상/하위
    ranked = sorted([r for r in results if r['trades'] > 0],
                    key=lambda r: r['total_return'], reverse=True)
    print('\n--- 종목별 총수익 상위 10 ---')
    for r in ranked[:10]:
        print(f"{r['coin']}: {r['total_return']:+.2f}% / {r['trades']}건 / 승률 {r['win_rate']}% / PF {r['profit_factor']}")
    print('\n--- 종목별 총수익 하위 10 ---')
    for r in ranked[-10:]:
        print(f"{r['coin']}: {r['total_return']:+.2f}% / {r['trades']}건 / 승률 {r['win_rate']}% / PF {r['profit_factor']}")

    return overall
