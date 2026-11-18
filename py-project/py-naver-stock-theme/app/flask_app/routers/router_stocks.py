import json
import logging
import traceback, pprint
from flask import Blueprint, request, g

from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.routers.router_master import optional_auth
from app.domains.dao.roleMenuDao import RoleMenuDao
from app.services.stocks import RecoLevel
from app.domains.dao.masterCodesDao import MasterCodesDao
from stock_shared.reco_algo import algo_stage_map, MASTER_CODES_KEY
from app.flask_app.utils.apiResponse import ApiResponse
from app.utils.service import KisDisabledError, IS_YANGBONG
from app.services.stocks.StockService import StockService
from app.services.stocks.HomePickService import home_picks
from app.services.stocks.RecoPerformanceService import RecoPerformanceService
from app.services.stocks.FinanceService import FinanceService
from app.services.stocks.SectorService import SectorService, MARKETS
from app.utils.constants.Literal import Literal

stocks_bp = Blueprint("stocks", __name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

masterStockDaoImpl = MasterStockDao()
stockInvestorDaoImpl = StockInvestorDailyDao()
stockServiceImpl = StockService()
recoPerformanceServiceImpl = RecoPerformanceService()
financeServiceImpl = FinanceService()
sectorServiceImpl = SectorService()
roleMenuDaoImpl = RoleMenuDao()

# STOCKS ROUTE :: ROOT
# ===============================================================================
@stocks_bp.route("")
def stocks_index():
    return {
        'msg': 'aibees flask :: stocks home'
    }
    
 # STOCKS ROUTE :: SELECT SEARCH
# ===============================================================================   
@stocks_bp.route('/search')
def select_master_stock_search():
    search_params = {
        'stock_name': request.args.get('searchTxt'),
        'search_option': True
    }
    
    try:
        results = masterStockDaoImpl.select_master_stock(g.db, search_params)
        return ApiResponse.success(results)
    except Exception as e:
        print(str(e))
        return ApiResponse.error(str(e)[:255])
    

def _buy_target_for_request(ymd=None, lite=False):
    """매수추천 목록을 **요청한 사용자의 열람 단계에 맞춰** 가공해 돌려준다(/buy-target · /buy-target/home 공용)."""
    user_id = g.current_user_id
    auth_ids = roleMenuDaoImpl.select_user_auth_ids(g.db, user_id) if user_id is not None else []
    features = roleMenuDaoImpl.select_features_for_user(g.db, auth_ids)
    level = RecoLevel.user_level(auth_ids, features)

    results = stockServiceImpl.get_buy_target_stock_list(g.db, {Literal.YMD: ymd}, lite=lite)
    # 알고리즘→단계 대응은 공통코드(stock/setting/reco_algo). 못 읽으면 기본 대응(BASIC 1·PREMIUM 2·PRIVATE 3).
    try:
        algo_stage = algo_stage_map(MasterCodesDao().select_master_code(g.db, MASTER_CODES_KEY))
    except Exception as e:
        logging.warning(f"[buy-target] reco_algo 공통코드 조회 실패 → 기본 대응: {e}")
        algo_stage = None
    return RecoLevel.apply_levels(results, level, algo_stage)


@stocks_bp.route('/buy-target')
@optional_auth
def select_buy_target_stock():
    """매수추천 목록. 비로그인도 열리지만 **열람 단계에 맞춰** 응답을 가공한다(RecoLevel).
    기본(비로그인 포함)은 고급 정보(shape_proba·종합순위·수급)를 뺀 목록, 고급은 RECO_ADVANCED 기능,
    실전은 WORKER_USER 권한자에게만 단계가 열린다.
    ?lite=1 이면 chart_data 에서 이동평균을 뺀다(미니 차트를 그리지 않는 화면용)."""
    lite = request.args.get("lite") in ("1", "true", "Y")
    try:
        return ApiResponse.success(_buy_target_for_request(request.args.get(Literal.YMD), lite=lite))
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


# STOCKS ROUTE :: 홈 'AI 분석 종목' — 서버가 내 설정으로 판정·정렬해 몇 줄만 준다(2026-11-18)
#   GET /buy-target/home?settings=<JSON>&limit=3&watch=005930,000660
#     settings : 화면의 보조지표 설정(persona 의 currentType.settings). 없거나 깨졌으면 기본 설정.
#     limit    : 1~10, 기본 3
#     watch    : 관심 종목 코드(쉼표, 최대 50개). 오늘 후보에 있는 것만 watch_items 로 돌려준다.
#   응답: {ymd, candidate_count, matched_count, items:[{stock_code, stock_name, ymd, close, rate_pct, reason, reason_rest}],
#          watch_items:[후보 행 + match]}
#   판정 로직의 정본은 화면 JS(indicators.js 등) — HomePickService 머리말 참고.
# ===============================================================================
@stocks_bp.route('/buy-target/home')
@optional_auth
def select_buy_target_home():
    raw = request.args.get("settings")
    settings = None
    if raw:
        try:
            settings = json.loads(raw)
        except ValueError:
            logging.warning("[buy-target/home] settings JSON 을 읽지 못해 기본 설정을 쓴다")
    try:
        limit = min(10, max(1, int(request.args.get("limit", 3))))
    except ValueError:
        limit = 3
    watch = [c.strip() for c in (request.args.get("watch") or "").split(",") if c.strip().isalnum()][:50]
    try:
        items = _buy_target_for_request(lite=True)
        return ApiResponse.success(home_picks(items, settings, limit, watch))
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error("추천 종목을 불러오지 못했습니다.")


# STOCKS ROUTE :: 월간 추천 성과 (홈) — 종목당 첫 추천 기준, 추천일 종가 → 5거래일 내 최고가
#   GET /buy-target/performance?ym=YYYYMM  (ym 생략 시 전월). 로그인 없이 열린다(홈이 게스트에게도 열림).
# ===============================================================================
@stocks_bp.route('/buy-target/performance')
def select_buy_target_performance():
    ym = request.args.get('ym')
    if ym and not (len(ym) == 6 and ym.isdigit()):
        return ApiResponse.error("ym 은 YYYYMM 형식이어야 합니다.")
    try:
        return ApiResponse.success(recoPerformanceServiceImpl.get_monthly_performance(g.db, ym))
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


# ===============================================================================
# 최우선타겟 (Home.vue 매수추천 카드 select)
#   GET    /buy-target/priority  조회 — {stock_code, stock_name, set_ymd} 또는 전부 null
#   PUT    /buy-target/priority  지정 — body {ymd, stock_code}
#   DELETE /buy-target/priority  해제
# 본인 것만 다루므로 JWT 인증 필요(user_id 는 클라이언트가 보내지 않는다).
# ===============================================================================
@stocks_bp.route('/buy-target/priority', methods=['GET'])
@require_auth
def get_buy_target_priority():
    try:
        result = stockServiceImpl.get_priority_target(g.db, g.current_user_id)
        return ApiResponse.success(result)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


@stocks_bp.route('/buy-target/priority', methods=['PUT'])
@require_auth
def set_buy_target_priority():
    body = request.get_json(silent=True) or {}
    ymd = body.get(Literal.YMD)
    stock_code = body.get(Literal.STOCK_CODE)
    if not ymd or not stock_code:
        return ApiResponse.error("ymd, stock_code 는 필수입니다.", status=400)

    try:
        result = stockServiceImpl.set_priority_target(g.db, g.current_user_id, ymd, stock_code)
        return ApiResponse.success(result)
    except ValueError as e:
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


@stocks_bp.route('/buy-target/priority', methods=['DELETE'])
@require_auth
def clear_buy_target_priority():
    try:
        stockServiceImpl.clear_priority_target(g.db, g.current_user_id)
        return ApiResponse.success({'cleared': True})
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


"""
    StockInfo
    - 추천당시 종가
    - 현재 종가
    - 해당 기간 내 종가
"""
@stocks_bp.route('/rec-record')
def select_rec_recode_stock():
    search_params = {
        Literal.STOCK_CODE: request.args.get(Literal.STOCK_CODE)
    }

    try:
        results = stockServiceImpl.get_target_rec_record(g.db, search_params)

        return ApiResponse.success(results)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])

# STOCKS ROUTE :: 업종 (테마 화면 대체) — KRX 지수업종별 등락률·수급 (SectorService 참고)
#   GET /sectors?ymd=YYYYMMDD                  → {ymd, prev_ymd, base_ymd, days, markets:{KOSPI|KOSDAQ:{trend}},
#                                                  sectors:[{market, sector_cd, sector_name, parent_name,
#                                                  stock_count, chg_rate, up_count, down_count, flat_count,
#                                                  market_cap(억), frgn_amt, orgn_amt, prsn_amt(백만원),
#                                                  chg_rate_5d, frgn_amt_5d, orgn_amt_5d, prsn_amt_5d, trend, leaders}]}
#     trend = 최근 5영업일 [{ymd, chg_rate, cum_rate, frgn_amt, orgn_amt, prsn_amt}] (cum_rate 는 base_ymd 종가 대비)
#   GET /sectors/<KOSPI|KOSDAQ>/<sector_cd>?ymd= → {…, market_trend, sector:{…, stocks:[종목별 종가·등락률(1일·5일)·시총·순매수]}}
#   ymd 생략 시 수급이 적재된 가장 최근 영업일. 미분류 업종 코드는 '0000'.
# ===============================================================================
@stocks_bp.route('/sectors')
def select_sectors():
    try:
        return ApiResponse.success(sectorServiceImpl.get_sectors(g.db, request.args.get(Literal.YMD) or None))
    except Exception as e:
        logging.error(f"[stocks/sectors] {e}")
        traceback.print_exc()
        return ApiResponse.error("업종 정보를 불러오지 못했습니다.")


@stocks_bp.route('/sectors/<market>/<sector_cd>')
def select_sector_detail(market, sector_cd):
    market = market.upper()
    if market not in MARKETS or not (len(sector_cd) == 4 and sector_cd.isdigit()):
        return ApiResponse.error("업종 코드 형식이 아닙니다.")
    try:
        result = sectorServiceImpl.get_sector_detail(g.db, market, sector_cd, request.args.get(Literal.YMD) or None)
        if result is None:
            return ApiResponse.error("해당 업종이 없습니다.")
        return ApiResponse.success(result)
    except Exception as e:
        logging.error(f"[stocks/sectors] {market}/{sector_cd}: {e}")
        traceback.print_exc()
        return ApiResponse.error("업종 정보를 불러오지 못했습니다.")


# STOCKS ROUTE :: SELECT BY ID
# ===============================================================================
# STOCKS ROUTE :: 개별종목 재무지표 (재무 탭 진입 시) — KIS 현재가 + 재무비율(연간 확정 결산)
#   GET /id/<code>/finance → {per, pbr, eps, bps, roe, peg, ntin_growth, sales_growth, op_growth, debt_ratio, settle_ym, price}
#   운영자 KIS 키로 조회하므로 로그인 사용자만(호출 한도 보호). 같은 종목은 서버가 10분 기억한다.
# ===============================================================================
@stocks_bp.route("/id/<stock_code>/finance")
@require_auth
def select_stock_finance(stock_code):
    if not (len(stock_code) == 6 and stock_code.isalnum()):
        return ApiResponse.error("종목코드 형식이 아닙니다.")
    if IS_YANGBONG:
        # 양봉상회는 API 서버가 KIS 를 부르지 않는다. AI 워커가 채운 캐시(stock_finance_snapshot)를 읽고,
        # 없거나 10분 지났으면 finance 작업을 넣는다. data 는 예전 모양(없으면 null), 상태는 최상위에.
        from app.flask_app.routers.router_ai_job import aiJobServiceImpl
        try:
            res = aiJobServiceImpl.finance(g.db, stock_code)
            return ApiResponse.success(res["data"], extra={
                "fetched_at": res["fetched_at"], "stale": res["stale"], "finance_job": res["job"]})
        except Exception as e:  # noqa: BLE001
            logging.error(f"[stocks/finance] {stock_code}: {e}")
            return ApiResponse.error("재무 지표를 불러오지 못했습니다.")
    try:
        return ApiResponse.success(financeServiceImpl.get_fundamentals(stock_code))
    except KisDisabledError as e:
        return ApiResponse.error(str(e), status=404)
    except Exception as e:
        logging.error(f"[stocks/finance] {stock_code}: {e}")
        traceback.print_exc()
        return ApiResponse.error("재무 지표를 불러오지 못했습니다.")


@stocks_bp.route("/id/<stock_code>")
def select_stocks_by_id(stock_code):
    param = {
        'stock_code': stock_code
    }
    
    try:
        results = masterStockDaoImpl.select_master_stock_by_id(g.db, param);
        if results is not None:
            # 종목 화면 '전일 수급' — 가장 최근 영업일의 투자자별 순매수(StockInvestorJob 07:10 적재).
            # 수급 조회가 실패해도 종목 정보(차트 화면)는 그대로 내려준다.
            try:
                results['investor'] = stockInvestorDaoImpl.select_latest(g.db, stock_code)
            except Exception as e:
                logging.warning(f"[stocks/id] {stock_code} 투자자 수급 조회 실패: {e}")
                results['investor'] = None
            # 시가총액(억원) = 상장주식수 × 수급과 같은 날 종가. 둘 중 하나라도 없으면 None.
            inv = results['investor']
            shares = results.get('listed_shares')
            results['market_cap'] = (round(shares * inv['close_price'] / 100_000_000)
                                     if inv and inv.get('close_price') and shares else None)
        return ApiResponse.success(results)
    except Exception as e:
        print(str(e))
        return ApiResponse.error(str(e)[:255])
