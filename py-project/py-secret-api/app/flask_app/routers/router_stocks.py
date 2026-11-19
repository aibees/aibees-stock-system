"""
비밀상회 종목 라우트 — 공용 경로는 web_shared.routers.router_stocks, 여기는 비밀상회 전용만(2026-11-19).

    GET /api/v1/stocks/id/<stock_code>/finance   개별종목 재무지표 — KIS 현재가 + 재무비율(연간 확정 결산)
시세 출처는 KIS(장중 봉 포함, KIS_ENABLED=false·키 없음이면 DB 일봉) — KisBarSource.
최우선타겟(/buy-target/priority)은 router_priority_target.
"""
import logging
import traceback

from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse
from web_shared.routers.router_stocks import create_stocks_blueprint
from web_shared.services.stocks.StockService import StockService
from app.services.stocks.FinanceService import FinanceService
from app.services.stocks.kisBarSource import KisBarSource
from app.utils.service import KisDisabledError

stockServiceImpl = StockService(bar_source=KisBarSource())
financeServiceImpl = FinanceService()

stocks_bp = create_stocks_blueprint(stockServiceImpl)


# 개별종목 재무지표 (재무 탭 진입 시) — KIS 현재가 + 재무비율(연간 확정 결산)
#   GET /id/<code>/finance → {per, pbr, eps, bps, roe, peg, ntin_growth, sales_growth, op_growth, debt_ratio, settle_ym, price}
#   운영자 KIS 키로 조회하므로 로그인 사용자만(호출 한도 보호). 같은 종목은 서버가 10분 기억한다.
@stocks_bp.route("/id/<stock_code>/finance")
@require_auth
def select_stock_finance(stock_code):
    if not (len(stock_code) == 6 and stock_code.isalnum()):
        return ApiResponse.error("종목코드 형식이 아닙니다.")
    try:
        return ApiResponse.success(financeServiceImpl.get_fundamentals(stock_code))
    except KisDisabledError as e:
        return ApiResponse.error(str(e), status=404)
    except Exception as e:
        logging.error(f"[stocks/finance] {stock_code}: {e}")
        traceback.print_exc()
        return ApiResponse.error("재무 지표를 불러오지 못했습니다.")
