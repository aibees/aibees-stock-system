"""양봉상회 차트 라우트 — 공용 경로(web_shared.routers.router_chart)에 DB 일봉 시세(StockService 기본값)를 넣어 만든다."""
from web_shared.routers.router_chart import create_chart_blueprint
from web_shared.services.stocks.StockService import StockService

chart_bp = create_chart_blueprint(StockService())
