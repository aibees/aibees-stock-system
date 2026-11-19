from flask import Flask, request

# 양봉상회 API 블루프린트 (import 경로, 변수명, url_prefix). 2026-11-19 py-secret-api 에서 분리.
#   web_shared.routers    : 비밀상회와 공용 — 인증·메뉴/권한·공지·접근 로그·개인설정·시황 지표
#   app.flask_app.routers : 양봉상회 판 — 종목·차트·AI 분석(공용 블루프린트에 DB 시세·작업 큐를 넣어 만든다)과 양봉 전용
#   매매·배치·전략·공통코드 관리·최우선타겟은 없다(비밀상회 전용).
_BLUEPRINTS = [
    ("app.flask_app.routers.router_stocks",       "stocks_bp",       "/api/v1/stocks"),
    ("web_shared.routers.router_oauth",           "oauth_bp",        "/api/oauth"),
    # 계정 삭제(회원 탈퇴) — 양봉상회 전용. DELETE /api/oauth/account
    ("app.flask_app.routers.router_account",     "account_bp",      "/api/oauth"),
    ("web_shared.routers.router_master",          "master_bp",       "/api/v1/master"),
    ("app.flask_app.routers.router_chart",        "chart_bp",        "/api/v1/charts"),
    ("app.flask_app.routers.router_anthropic",    "anthropic_bp",    "/api/v1/anthropic"),
    ("web_shared.routers.router_user_options",    "user_options_bp", "/api/v1"),
    ("web_shared.routers.router_indicators",      "indicators_bp",   "/api/v1/indicators"),
    ("web_shared.routers.router_access_log",      "access_log_bp",   "/api/v1/access-logs"),
    ("web_shared.routers.router_notice",          "notice_bp",       "/api/v1/notices"),
    # AI 분석 비동기화(meetings/설계_2026-11-18_AI분석-비동기화.md) — sql/yangbong/008 의 표(작업 큐·알림함·푸시 토큰)
    ("app.flask_app.routers.router_ai_job",       "ai_job_bp",       "/api/v1/anthropic/stock-analysis"),
    ("app.flask_app.routers.router_notification", "notification_bp", "/api/v1/notifications"),
    ("app.flask_app.routers.router_notification", "notify_bp",       "/api/v1/notify"),
    # 성향 테스트 결과(user_persona — yangbong 스키마에만 있다)
    ("app.flask_app.routers.router_persona",      "persona_bp",      "/api/v1"),
]


def _blueprints():
    import importlib
    for module_path, attr, prefix in _BLUEPRINTS:
        yield getattr(importlib.import_module(module_path), attr), prefix


def register_blueprints(app: Flask):

    @app.route("/api/v1/**", methods=["GET", "OPTIONS"])
    def log_api():
        if request.method == "OPTIONS":
            return '', 200  # Preflight OK 응답
        return None

    for blueprint, prefix in _blueprints():
        app.register_blueprint(blueprint, url_prefix=prefix)
