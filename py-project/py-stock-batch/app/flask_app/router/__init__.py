from flask import Flask

from app.flask_app.router.router_job import job_bp
from app.flask_app.router.router_manual_sell import manual_sell_bp
from app.flask_app.router.router_notify import notify_bp

def register_blueprints(app: Flask):
    app.register_blueprint(job_bp, url_prefix="/api/v1/jobs")
    app.register_blueprint(manual_sell_bp, url_prefix="/api/v1/manual-sell")
    app.register_blueprint(notify_bp, url_prefix="/api/v1/notify")

    # deprecated: 구 prefix. ROOT 서버(py-naver-stock-theme)도 `/api/v1/auto-trade` 에
    # blueprint 를 등록하므로 **이 prefix 는 두 앱이 겹친다** — nginx 가 이 앱으로
    # 보내면 ROOT 의 /modes·/state·/history 가 404 가 되어 운용방식 설정·운용 현황
    # 화면이 통째로 죽는다(2026-10-11). 그래서 프록시는 위의 /api/v1/manual-sell 만
    # 이 앱으로 보내고, /api/v1/auto-trade 는 ROOT 로 보낸다.
    #   이 legacy 등록은 `/batches/...` 를 타고 들어오는 **구 앱 번들**만을 위한 것이다
    #   (Capacitor 설치본은 스토어 업데이트 전까지 구 번들을 쓴다). 전체 사용자가 새
    #   번들을 받으면 이 줄과 router_manual_sell.py 의 alias 데코레이터를 함께 지운다.
    app.register_blueprint(manual_sell_bp, url_prefix="/api/v1/auto-trade",
                           name="manual_sell_legacy")
