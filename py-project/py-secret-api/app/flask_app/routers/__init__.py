
from flask import Flask, request

# 비밀상회 API 블루프린트 (import 경로, 변수명, url_prefix). 양봉상회 API 는 py-yangbong-api 로 분리했다(2026-11-19 3단계).
#   web_shared.routers    : 두 서버 공용 — 인증·메뉴/권한·공지·접근 로그·개인설정·시황 지표
#   app.flask_app.routers : 비밀상회 판 — 종목·차트·AI 분석은 공용 블루프린트(web_shared create_*)에 KIS·동기 생성을 넣어 만든다
_PUBLIC_BLUEPRINTS = [
    ("app.flask_app.routers.router_stocks",       "stocks_bp",       "/api/v1/stocks"),
    ("web_shared.routers.router_oauth",           "oauth_bp",        "/api/oauth"),
    ("web_shared.routers.router_master",          "master_bp",       "/api/v1/master"),
    ("app.flask_app.routers.router_chart",        "chart_bp",        "/api/v1/charts"),
    ("app.flask_app.routers.router_anthropic",    "anthropic_bp",    "/api/v1/anthropic"),
    ("web_shared.routers.router_user_options",    "user_options_bp", "/api/v1"),
    ("web_shared.routers.router_indicators",      "indicators_bp",   "/api/v1/indicators"),
    ("web_shared.routers.router_access_log",      "access_log_bp",   "/api/v1/access-logs"),
    ("web_shared.routers.router_notice",          "notice_bp",       "/api/v1/notices"),
]

# 비밀상회에만 있는 블루프린트 — 배치·공통코드 관리·전략·계좌·매매·최우선타겟.
_SECRET_ONLY_BLUEPRINTS = [
    ("app.flask_app.routers.router_batches",       "batch_bp",          "/api/v1"),
    ("app.flask_app.routers.router_commoncode",    "common_bp",         "/api/v1/common-codes"),
    ("app.flask_app.routers.router_strategy",      "strategy_bp",       "/api/v1/strategy"),
    ("app.flask_app.routers.router_account_trade", "account_trade_bp",  "/api/v1/users"),
    ("app.flask_app.routers.router_profit",        "profit_bp",         "/api/v1/profit"),
    ("app.flask_app.routers.router_auto_trade",    "auto_trade_bp",     "/api/v1/auto-trade"),
    ("app.flask_app.routers.router_manual_buy",    "manual_buy_bp",     "/api/v1/auto-trade/manual-buy"),
    ("app.flask_app.routers.router_manual_sell",   "manual_sell_bp",    "/api/v1/auto-trade/manual-sell"),
    # 최우선타겟 지정 — 매매 워커가 읽는다(2026-11-19 router_stocks 에서 분리, 경로는 그대로 /api/v1/stocks/buy-target/priority)
    ("app.flask_app.routers.router_priority_target", "priority_bp",     "/api/v1/stocks"),
    # ("app.flask_app.routers.router_upbit",       "upbit_bp",          "/api/v1/upbit"),
]


def _blueprints():
    import importlib
    entries = _PUBLIC_BLUEPRINTS + _SECRET_ONLY_BLUEPRINTS
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
