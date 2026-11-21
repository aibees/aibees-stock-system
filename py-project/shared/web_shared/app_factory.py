"""
웹 공통 Flask 앱 생성(양봉상회·비밀상회 웹서버 공용, 2026-11-18 py-secret-api runner 에서 옮김).

    app = create_app(register_blueprints)

  · CORS: /api/* 전부 허용(Authorization 헤더 포함 — 빠지면 preflight 에서 막힌다)
  · 요청마다 DB 세션을 g.db 로 열고, 끝나면 예외가 있었으면 rollback 아니면 commit 후 remove()
    (scoped_session 은 close() 가 아니라 remove() 로 정리해야 다음 요청이 닫힌 세션을 재사용하지 않는다)
  · 블루프린트 등록은 서버마다 다르므로 register_blueprints(app) 로 받는다.
  · JSON 응답은 클라이언트가 gzip 을 받으면 압축해 보낸다(_gzip_response, 2026-11-21).
"""
import gzip
import logging

from flask import Flask, g, request
from flask_cors import CORS

from stock_shared.db.database import dbConn


#: 이보다 작은 응답은 압축하지 않는다(헤더·CPU 가 더 든다).
_GZIP_MIN_BYTES = 1024
#: 속도 우선. 6 이상은 크기가 거의 안 줄고 CPU 만 는다.
_GZIP_LEVEL = 5


def _gzip_response(response):
    """JSON 응답을 gzip 으로 줄인다(2026-11-21 응답 속도 점검).

    홈 서버 → 클라우드 nginx → Cloudflare 로 가는 구간이 비압축이라 차트(/charts/stock) 응답이 98KB 그대로 나갔다
    (gzip 이면 약 17KB). nginx·Cloudflare 는 이미 Content-Encoding 이 붙은 응답을 다시 압축하지 않고 그대로 넘긴다.
    스트리밍·이미 인코딩된 응답·작은 응답·JSON 이 아닌 응답은 건드리지 않는다.
    """
    if (response.direct_passthrough or response.is_streamed
            or response.status_code < 200 or response.status_code >= 300
            or 'Content-Encoding' in response.headers
            or 'gzip' not in request.headers.get('Accept-Encoding', '').lower()
            or not (response.mimetype or '').endswith('json')):
        return response
    body = response.get_data()
    if len(body) < _GZIP_MIN_BYTES:
        return response
    response.set_data(gzip.compress(body, compresslevel=_GZIP_LEVEL))
    response.headers['Content-Encoding'] = 'gzip'
    response.vary.add('Accept-Encoding')
    return response


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

    app.after_request(_gzip_response)

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
