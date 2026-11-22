"""
양봉상회 종목 라우트 — 공용 경로는 web_shared.routers.router_stocks, 여기는 양봉상회 판만(2026-11-19 분리).

    GET /api/v1/stocks/id/<stock_code>/finance   재무지표 — API 는 KIS 를 부르지 않는다. AI 워커가 채운 캐시
                                                  (stock_finance_snapshot)를 읽고, 없거나 10분 지났으면 finance 작업을 넣는다.
    GET /api/v1/stocks/buy-target/home           홈 '시장이 주목하는 종목' — 서버가 내 설정으로 판정·정렬해 몇 줄만 준다.
    GET /api/v1/stocks/weekly-chart              홈 '이번 주의 차트' — 전 주 선정 종목 중 신호가 가장 선명한 1개(2026-11-22).
시세 출처는 DB 일봉(StockService 기본값). 최우선타겟(매매)은 없다.
"""
import json
import logging
import traceback

from flask import request, g

from web_shared.auth.decorators import require_auth, optional_auth
from web_shared.http.response import ApiResponse
from web_shared.routers.router_stocks import create_stocks_blueprint, buy_target_for_request
from web_shared.services.stocks.StockService import StockService
from app.flask_app.routers.router_ai_job import aiJobServiceImpl
from app.services.stocks.HomePickService import home_picks
from app.services.stocks.WeeklyChartService import weekly_chart

stockServiceImpl = StockService()

stocks_bp = create_stocks_blueprint(stockServiceImpl)


# 개별종목 재무지표 (재무 탭) — data 는 예전 모양(없으면 null), 캐시 상태는 최상위 fetched_at·stale·finance_job.
@stocks_bp.route("/id/<stock_code>/finance")
@require_auth
def select_stock_finance(stock_code):
    if not (len(stock_code) == 6 and stock_code.isalnum()):
        return ApiResponse.error("종목코드 형식이 아닙니다.")
    try:
        res = aiJobServiceImpl.finance(g.db, stock_code)
        return ApiResponse.success(res["data"], extra={
            "fetched_at": res["fetched_at"], "stale": res["stale"], "finance_job": res["job"]})
    except Exception as e:  # noqa: BLE001
        logging.error(f"[stocks/finance] {stock_code}: {e}")
        return ApiResponse.error("재무 지표를 불러오지 못했습니다.")


# 홈 'AI 분석 종목' — 서버가 내 설정으로 판정·정렬해 몇 줄만 준다(2026-11-18)
#   GET /buy-target/home?settings=<JSON>&limit=3&watch=005930,000660
#     settings : 화면의 보조지표 설정(persona 의 currentType.settings). 없거나 깨졌으면 기본 설정.
#     limit    : 1~10, 기본 3
#     watch    : 관심 종목 코드(쉼표, 최대 50개). 오늘 후보에 있는 것만 watch_items 로 돌려준다.
#   응답: {ymd, candidate_count, matched_count, items:[{stock_code, stock_name, ymd, close, rate_pct, reason, reason_rest}],
#          watch_items:[후보 행 + match]}
#   판정 로직의 정본은 화면 JS(indicators.js 등) — HomePickService 머리말 참고.
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
        items = buy_target_for_request(stockServiceImpl, lite=True)
        return ApiResponse.success(home_picks(items, settings, limit, watch))
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error("추천 종목을 불러오지 못했습니다.")


# 홈 '이번 주의 차트' — 전 주에 양봉상회가 실제로 고른 종목 중 신호가 가장 선명한 1개와 봉(선정 이후 봉 포함).
#   GET /weekly-chart   로그인 없이 열린다. 응답: {ymd, stock_code, stock_name, close, lines[≤3], bars[], marker_date} 또는 null
#   수익률 등 성과 숫자는 내리지 않는다. 선정 규칙·사후 각색 금지는 WeeklyChartService 머리말 참고.
@stocks_bp.route('/weekly-chart')
@optional_auth
def select_weekly_chart():
    try:
        return ApiResponse.success(weekly_chart(
            stockServiceImpl, g.db, lambda ymd: buy_target_for_request(stockServiceImpl, ymd=ymd, lite=True)))
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error("이번 주의 차트를 불러오지 못했습니다.")
