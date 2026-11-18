"""
web_shared — 양봉상회(py-yangbong-api)·비밀상회(py-secret-api) **웹서버** 공용 모듈(2026-11-18~19).

stock_shared 가 웹·배치·워커 공용 DB 계층이라면, 이것은 그 위의 웹(Flask) 계층 공용이다.
배치는 쓰지 않는다. Flask·PyJWT 같은 의존성은 쓰는 앱(py-secret-api)이 선언한다.

    app_factory   create_app — CORS · 요청별 DB 세션(g.db)
    http          ApiResponse — 응답 포맷
    auth          JWT 발급·검증(service), require_auth·optional_auth·require_admin·require_super(decorators)
    dao, models   두 서버가 같이 쓰는 표: 메뉴·권한·공통코드·마스터 정보·공지·접근 로그·개인설정·소셜 로그인·리프레시 토큰
    mailer        메일 발송(가입 인증 코드 등)
    exceptions    공용 예외(ResetRequiredException)
    routers       공용 블루프린트 — oauth(로그인·가입) · master(메뉴·권한·관리자) · notice · access_log ·
                  user_options(개인설정, persona 제외) · indicators(시황·세계 지표). 등록은 각 서버의 routers/__init__ 가 한다.
    services/indicators, ext_services/fred   indicators 라우터용 서비스(yfinance·FRED)
    routers/router_stocks·router_chart·router_anthropic
                  공용 경로만 담은 블루프린트를 만드는 함수(create_*). 서버마다 다른 경로는 받은 블루프린트에 각 서버가 덧붙인다.
    services/stocks     StockService(bar_source 주입 — 양봉 DB 일봉 / 비밀 KIS) · RecoLevel · 성과 · 업종 · 지표 계산
    services/anthropic  StockAiContentService(default_limits·news_kis_factory 주입) · Anthropic 클라이언트 · 프롬프트
    ext_services/kis    KisEngine(조회 전용 — 비밀 API·양봉 AI 워커) · constants/Literal · config/anthropicConfig

서버마다 다른 것은 플래그(APP_SERVICE)로 가르지 않고 **만드는 쪽이 넣는다**(시세 출처·생성 한도·뉴스용 KIS).

규칙: web_shared 는 각 서버의 app.* 를 import 하지 않는다(공통이 특정 서버에 기대면 분리가 깨진다).

분리 계획: (완료) 1단계 기반·인증 → (완료) 2단계 공통 라우터 → (완료) 3단계 py-yangbong-api 신설 → 4단계 비밀 쪽 IS_YANGBONG 제거 → 5단계 배포 분리.
"""
