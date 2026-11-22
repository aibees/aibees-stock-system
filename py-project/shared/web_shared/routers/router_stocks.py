"""
종목·매수추천 공용 라우트(양봉상회·비밀상회 웹서버 공용, 2026-11-19 py-secret-api router_stocks 에서 옮김).

    stocks_bp = create_stocks_blueprint(stock_service)   # url_prefix /api/v1/stocks
    @stocks_bp.route(...)                                # 서버 전용 경로는 받은 블루프린트에 덧붙인다

공용 경로
    GET ""                         인덱스
    GET /search?searchTxt=         종목 검색
    GET /buy-target?ymd=&lite=1    매수추천 목록(열람 단계별 가공 — RecoLevel)
    GET /buy-target/performance    월간 추천 성과(홈)
    GET /rec-record?stock_code=    추천 당시·최고·현재 종가
    GET /sectors · /sectors/<market>/<sector_cd>   업종
    GET /id/<stock_code>           종목 단건 + 전일 수급·시가총액
서버마다 다른 경로(각 서버가 덧붙인다)
    GET /id/<stock_code>/finance   비밀상회: KIS 로 바로 조회 / 양봉상회: AI 워커가 채운 캐시 + 작업 접수
    GET /buy-target/home           양봉상회 홈 TOP 3
    /buy-target/priority           비밀상회 최우선타겟(router_priority_target)
"""
import logging
import traceback

from flask import Blueprint, request, g

from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao
from stock_shared.reco_algo import algo_stage_map, MASTER_CODES_KEY
from web_shared.auth.decorators import optional_auth
from web_shared.constants.Literal import Literal
from web_shared.dao.masterCodesDao import MasterCodesDao
from web_shared.dao.roleMenuDao import RoleMenuDao
from web_shared.auth.features import with_extra_features
from web_shared.http.response import ApiResponse
from web_shared.services.stocks import RecoLevel
from web_shared.services.stocks.RecoPerformanceService import RecoPerformanceService
from web_shared.services.stocks.SectorService import SectorService, MARKETS

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

masterStockDaoImpl = MasterStockDao()
stockInvestorDaoImpl = StockInvestorDailyDao()
recoPerformanceServiceImpl = RecoPerformanceService()
sectorServiceImpl = SectorService()
roleMenuDaoImpl = RoleMenuDao()


def buy_target_for_request(stock_service, ymd=None, lite=False):
    """매수추천 목록을 **요청한 사용자의 열람 단계에 맞춰** 가공해 돌려준다(/buy-target · 양봉 /buy-target/home 공용).
    @optional_auth 아래에서 부른다(g.current_user_id 가 있어야 한다)."""
    user_id = g.current_user_id
    auth_ids = roleMenuDaoImpl.select_user_auth_ids(g.db, user_id) if user_id is not None else []
    features = with_extra_features(g.db, user_id, roleMenuDaoImpl.select_features_for_user(g.db, auth_ids))
    level = RecoLevel.user_level(auth_ids, features)

    results = stock_service.get_buy_target_stock_list(g.db, {Literal.YMD: ymd}, lite=lite)
    # 알고리즘→단계 대응은 공통코드(stock/setting/reco_algo). 못 읽으면 기본 대응(BASIC 1·PREMIUM 2·PRIVATE 3).
    try:
        algo_stage = algo_stage_map(MasterCodesDao().select_master_code(g.db, MASTER_CODES_KEY))
    except Exception as e:
        logging.warning(f"[buy-target] reco_algo 공통코드 조회 실패 → 기본 대응: {e}")
        algo_stage = None
    return RecoLevel.apply_levels(results, level, algo_stage)


def create_stocks_blueprint(stock_service) -> Blueprint:
    stocks_bp = Blueprint("stocks", __name__)

    @stocks_bp.route("")
    def stocks_index():
        return {'msg': 'aibees flask :: stocks home'}

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

    @stocks_bp.route('/buy-target')
    @optional_auth
    def select_buy_target_stock():
        """매수추천 목록. 비로그인도 열리지만 **열람 단계에 맞춰** 응답을 가공한다(RecoLevel).
        기본(비로그인 포함)은 고급 정보(shape_proba·종합순위·수급)를 뺀 목록, 고급은 RECO_ADVANCED 기능,
        실전은 WORKER_USER 권한자에게만 단계가 열린다.
        ?lite=1 이면 chart_data 에서 이동평균을 뺀다(미니 차트를 그리지 않는 화면용)."""
        lite = request.args.get("lite") in ("1", "true", "Y")
        try:
            return ApiResponse.success(buy_target_for_request(stock_service, request.args.get(Literal.YMD), lite=lite))
        except Exception as e:
            logging.error(str(e))
            traceback.print_exc()
            return ApiResponse.error(str(e)[:255])

    # 월간 추천 성과 (홈) — 종목당 첫 추천 기준, 추천일 종가 → 5거래일 내 최고가
    #   GET /buy-target/performance?ym=YYYYMM  (ym 생략 시 전월). 로그인 없이 열린다(홈이 게스트에게도 열림).
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

    # StockInfo — 추천당시 종가 · 현재 종가 · 해당 기간 내 최고 종가
    @stocks_bp.route('/rec-record')
    def select_rec_recode_stock():
        search_params = {Literal.STOCK_CODE: request.args.get(Literal.STOCK_CODE)}
        try:
            results = stock_service.get_target_rec_record(g.db, search_params)
            return ApiResponse.success(results)
        except Exception as e:
            logging.error(str(e))
            traceback.print_exc()
            return ApiResponse.error(str(e)[:255])

    # 업종 (테마 화면 대체) — KRX 지수업종별 등락률·수급 (SectorService 참고)
    #   GET /sectors?ymd=YYYYMMDD · GET /sectors/<KOSPI|KOSDAQ>/<sector_cd>?ymd=
    #   ymd 생략 시 수급이 적재된 가장 최근 영업일. 미분류 업종 코드는 '0000'.
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

    @stocks_bp.route("/id/<stock_code>")
    def select_stocks_by_id(stock_code):
        param = {'stock_code': stock_code}
        try:
            results = masterStockDaoImpl.select_master_stock_by_id(g.db, param)
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

    return stocks_bp
