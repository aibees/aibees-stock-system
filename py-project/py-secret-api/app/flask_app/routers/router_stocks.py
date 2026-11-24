"""
비밀상회 종목 라우트 — 공용 경로는 web_shared.routers.router_stocks, 여기는 비밀상회 전용만(2026-11-19).

    GET /api/v1/stocks/id/<stock_code>/finance   개별종목 재무지표 — KIS 현재가 + 재무비율(연간 확정 결산)
    GET /api/v1/stocks/buy-target/table?source=basic|premium&ymd=   매수추천을 테이블 하나에서만(베이직·프리미엄 탭)
시세 출처는 KIS(장중 봉 포함, KIS_ENABLED=false·키 없음이면 DB 일봉) — KisBarSource.
최우선타겟(/buy-target/priority)은 router_priority_target.
"""
import logging
import traceback

from flask import g, request

from web_shared.auth.decorators import require_auth
from web_shared.auth.features import with_extra_features
from web_shared.constants.Literal import Literal
from web_shared.dao.roleMenuDao import RoleMenuDao
from web_shared.services.stocks import RecoLevel
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


# 매수추천 — 테이블 하나에서만(비밀상회 매수추천 화면의 베이직·프리미엄 탭, 2026-11-25)
#   GET /buy-target/table?source=basic|premium&ymd=YYYYMMDD
#     basic   → trade_buy_target_basic(기본 알고리즘)
#     premium → trade_buy_target_stock(2파 종합순위 — 워커가 사는 목록. 테이블 그대로, 고급 단계의 shape 하한은 걸지 않는다)
#   공용 /buy-target 과 같은 열람 규칙: 프리미엄은 고급 단계(RECO_ADVANCED·WORKER_USER) 이상만,
#   기본 단계 사용자에게는 고급 전용 필드(RecoLevel.ADVANCED_ONLY_FIELDS)를 지운다.
_roleMenuDao = RoleMenuDao()


@stocks_bp.route('/buy-target/table')
@require_auth
def select_buy_target_by_table():
    source = request.args.get('source')
    if source not in ('basic', 'premium'):
        return ApiResponse.error("source 는 basic 또는 premium 이어야 합니다.", status=400)
    lite = request.args.get("lite") in ("1", "true", "Y")
    try:
        auth_ids = _roleMenuDao.select_user_auth_ids(g.db, g.current_user_id)
        features = with_extra_features(g.db, g.current_user_id, _roleMenuDao.select_features_for_user(g.db, auth_ids))
        level = RecoLevel.user_level(auth_ids, features)
        if source == 'premium' and level < RecoLevel.LEVEL_ADVANCED:
            return ApiResponse.error("프리미엄 추천을 볼 권한이 없습니다.", status=403)

        rows = stockServiceImpl.get_buy_target_stock_list(
            g.db, {Literal.YMD: request.args.get(Literal.YMD)}, lite=lite, source=source)
        if level < RecoLevel.LEVEL_ADVANCED:
            for it in rows:
                for k in RecoLevel.ADVANCED_ONLY_FIELDS:
                    it.pop(k, None)
        return ApiResponse.success(rows)
    except Exception as e:
        logging.error(f"[stocks/buy-target/table] {source}: {e}")
        traceback.print_exc()
        return ApiResponse.error("매수추천을 불러오지 못했습니다.")
