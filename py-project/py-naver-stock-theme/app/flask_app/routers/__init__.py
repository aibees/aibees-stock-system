
from flask import Flask, request
from app.flask_app.routers.router_batches import batch_bp
from app.flask_app.routers.router_stocks import stocks_bp
from app.flask_app.routers.router_oauth import oauth_bp
from app.flask_app.routers.router_master import master_bp
from app.flask_app.routers.router_chart import chart_bp
from app.flask_app.routers.router_commoncode import common_bp
from app.flask_app.routers.router_anthropic import anthropic_bp
from app.flask_app.routers.router_sell_request import sell_request_bp
from app.flask_app.routers.router_user_options import user_options_bp
from app.flask_app.routers.router_strategy import strategy_bp
# from app.flask_app.routers.router_upbit import upbit_bp
from app.flask_app.routers.router_account_trade import account_trade_bp

def register_blueprints(app: Flask):
    
    @app.route("/api/v1/**", methods=["GET", "OPTIONS"])
    def log_api():
        if request.method == "OPTIONS":
            return '', 200  # Preflight OK 응답
        return None

    app.register_blueprint(batch_bp, url_prefix="/api/v1")
    app.register_blueprint(stocks_bp, url_prefix="/api/v1/stocks")
    app.register_blueprint(oauth_bp, url_prefix="/api/oauth")
    app.register_blueprint(master_bp, url_prefix="/api/v1/master")
    app.register_blueprint(chart_bp, url_prefix="/api/v1/charts")
    app.register_blueprint(common_bp, url_prefix="/api/v1/common-codes")
    app.register_blueprint(anthropic_bp, url_prefix="/api/v1/anthropic")
    app.register_blueprint(sell_request_bp, url_prefix="/api/v1")
    app.register_blueprint(user_options_bp, url_prefix="/api/v1")
    app.register_blueprint(strategy_bp, url_prefix="/api/v1/strategy")
    # app.register_blueprint(upbit_bp, url_prefix="/api/v1/upbit")
    app.register_blueprint(account_trade_bp, url_prefix="/api/v1/users")
