"""
웹 공통 Flask 앱 생성(양봉상회·비밀상회 웹서버 공용, 2026-11-18 py-secret-api runner 에서 옮김).

    app = create_app(register_blueprints)

  · CORS: /api/* 전부 허용(Authorization 헤더 포함 — 빠지면 preflight 에서 막힌다)
  · 요청마다 DB 세션을 g.db 로 열고, 끝나면 예외가 있었으면 rollback 아니면 commit 후 remove()
    (scoped_session 은 close() 가 아니라 remove() 로 정리해야 다음 요청이 닫힌 세션을 재사용하지 않는다)
  · 블루프린트 등록은 서버마다 다르므로 register_blueprints(app) 로 받는다.
"""
import logging

from flask import Flask, g
from flask_cors import CORS

from stock_shared.db.database import dbConn


def create_app(register_blueprints, config_obj=None, import_name: str = __name__) -> Flask:
    app = Flask(import_name)
    CORS(
        app,
        resources={r"/api/*": {
            "origins": "*",
            # Authorization 헤더 누락 시 preflight 단계에서 차단되므로 명시
            "allow_headers": ["Content-Type", "Authorization", "maria-Authorization"],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        }}
    )
    if config_obj:
        app.config.from_object(config_obj)

    @app.before_request
    def before_request():
        g.db = dbConn.get_session()

    @app.teardown_appcontext
    def teardown_db(exception):
        db = g.pop('db', None)
        if db is not None:
            if exception:
                logging.exception(exception)
                db.rollback()
            else:
                db.commit()
            db.remove()

    register_blueprints(app)
    return app
