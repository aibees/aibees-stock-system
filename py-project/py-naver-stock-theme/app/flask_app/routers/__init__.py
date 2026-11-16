
from flask import Flask, request

from app.utils.service import IS_YANGBONG

# 두 서비스가 같이 쓰는 블루프린트 (import 경로, 변수명, url_prefix)
#   양봉상회(APP_SERVICE=yangbong)는 이 목록만 등록한다 — 매매·배치·전략·공통코드 관리는 비밀상회에만 있다.
_PUBLIC_BLUEPRINTS = [
    ("app.flask_app.routers.router_stocks",       "stocks_bp",       "/api/v1/stocks"),
    ("app.flask_app.routers.router_oauth",        "oauth_bp",        "/api/oauth"),
    ("app.flask_app.routers.router_master",       "master_bp",       "/api/v1/master"),
    ("app.flask_app.routers.router_chart",        "chart_bp",        "/api/v1/charts"),
    ("app.flask_app.routers.router_anthropic",    "anthropic_bp",    "/api/v1/anthropic"),
    ("app.flask_app.routers.router_user_options", "user_options_bp", "/api/v1"),
    ("app.flask_app.routers.router_indicators",   "indicators_bp",   "/api/v1/indicators"),
    ("app.flask_app.routers.router_access_log",   "access_log_bp",   "/api/v1/access-logs"),
    ("app.flask_app.routers.router_notice",       "notice_bp",       "/api/v1/notices"),
]

# 비밀상회에만 있는 블루프린트. 양봉상회 서버에서는 import 도 하지 않는다
# (import 시점에 서비스 객체를 만드는 모듈이 있어, 양봉상회 DB 에 없는 테이블·KIS 키를 건드리지 않게).
_SECRET_ONLY_BLUEPRINTS = [
    ("app.flask_app.routers.router_batches",       "batch_bp",          "/api/v1"),
    ("app.flask_app.routers.router_commoncode",    "common_bp",         "/api/v1/common-codes"),
    ("app.flask_app.routers.router_strategy",      "strategy_bp",       "/api/v1/strategy"),
    ("app.flask_app.routers.router_account_trade", "account_trade_bp",  "/api/v1/users"),
    ("app.flask_app.routers.router_profit",        "profit_bp",         "/api/v1/profit"),
    ("app.flask_app.routers.router_auto_trade",    "auto_trade_bp",     "/api/v1/auto-trade"),
    ("app.flask_app.routers.router_manual_buy",    "manual_buy_bp",     "/api/v1/auto-trade/manual-buy"),
    ("app.flask_app.routers.router_manual_sell",   "manual_sell_bp",    "/api/v1/auto-trade/manual-sell"),
    # ("app.flask_app.routers.router_upbit",       "upbit_bp",          "/api/v1/upbit"),
]


def _blueprints():
    import importlib
    entries = _PUBLIC_BLUEPRINTS if IS_YANGBONG else _PUBLIC_BLUEPRINTS + _SECRET_ONLY_BLUEPRINTS
    for module_path, attr, prefix in entries:
        yield getattr(importlib.import_module(module_path), attr), prefix


def register_blueprints(app: Flask):

    @app.route("/api/v1/**", methods=["GET", "OPTIONS"])
    def log_api():
        if request.method == "OPTIONS":
            return '', 200  # Preflight OK 응답
        return None

    for blueprint, prefix in _blueprints():
        app.register_blueprint(blueprint, url_prefix=prefix)
