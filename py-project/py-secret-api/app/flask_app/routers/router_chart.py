"""비밀상회 차트 라우트 — 공용 경로(web_shared.routers.router_chart)에 KIS 시세 출처를 넣어 만든다(2026-11-19)."""
from web_shared.routers.router_chart import create_chart_blueprint
from web_shared.services.stocks.StockService import StockService
from app.services.stocks.kisBarSource import KisBarSource

chart_bp = create_chart_blueprint(StockService(bar_source=KisBarSource()))
