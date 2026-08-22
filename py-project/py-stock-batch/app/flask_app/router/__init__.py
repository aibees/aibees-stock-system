from flask import Flask

from app.flask_app.router.router_job import job_bp
from app.flask_app.router.router_auto_trade import auto_trade_bp
from app.flask_app.router.router_notify import notify_bp

def register_blueprints(app: Flask):
    app.register_blueprint(job_bp, url_prefix="/api/v1/jobs")
    app.register_blueprint(auto_trade_bp, url_prefix="/api/v1/auto-trade")
    app.register_blueprint(notify_bp, url_prefix="/api/v1/notify")
