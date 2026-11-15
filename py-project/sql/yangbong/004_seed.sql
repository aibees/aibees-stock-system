-- ============================================================================
-- yangbong/004_seed.sql  (2026-11-15)
--
-- 양봉상회 시작 데이터 — `stock` 에서 필요한 행만 복사한다. 여러 번 실행해도 같은 결과(INSERT IGNORE).
--
--   user_role    : 신규 가입 기본 권한 STOCK_USER(authService.DEFAULT_SIGNUP_ROLE), ADMIN, AD_FREE_USER(광고 제거).
--                  WORKER_USER(매매)·COIN_USER 는 넣지 않는다 — 양봉상회에는 매매 권한이 존재하지 않는다.
--   role_feature : AD_FREE_USER → AD_FREE 기능(광고 숨김).
--   master_menu  : 공개 화면만(홈·전체 메뉴·로그인·고객센터·공지). 주식정보·트레이드·관리 메뉴는 넣지 않는다
--                  → 양봉상회 화면에서는 그 경로가 라우트로 등록되지도 않는다. 트레이닝 탭은 화면을 만들 때 추가.
--   master_codes : 화면 설정값(stock/setting 의 ad·screen). 배치·워커 설정은 넣지 않는다.
--   master_infos : 로그인·메일 키(NAVER_AUTH / GOOGLE_AUTH / SMTP)만. KIS 키는 넣지 않는다.
--                  ⚠ 양봉상회를 다른 도메인·앱으로 내면 네이버·구글 개발자 콘솔에 그 콜백 주소를 등록해야 한다.
--   stock_ai_content : 지금까지 생성한 AI 분석(종목·섹션별 캐시)을 그대로 옮긴다(2026-11-15 기준 35행).
--
-- 확인: SELECT menu_code FROM yangbong.master_menu;  SELECT category, COUNT(*) FROM yangbong.master_infos GROUP BY category;
-- ============================================================================

INSERT IGNORE INTO yangbong.user_role
    SELECT * FROM stock.user_role WHERE auth_id IN ('STOCK_USER', 'ADMIN', 'AD_FREE_USER');

INSERT IGNORE INTO yangbong.role_feature
    SELECT * FROM stock.role_feature WHERE auth_id = 'AD_FREE_USER';

INSERT IGNORE INTO yangbong.master_menu
    SELECT * FROM stock.master_menu WHERE menu_code IN ('Home', 'Menu', 'Login', 'Board', 'Notice', 'NoticeDetail');

INSERT IGNORE INTO yangbong.master_codes
    SELECT * FROM stock.master_codes WHERE `system` = 'stock' AND source = 'setting' AND category IN ('ad', 'screen');

INSERT IGNORE INTO yangbong.master_infos
    SELECT * FROM stock.master_infos WHERE category IN ('NAVER_AUTH', 'GOOGLE_AUTH', 'SMTP');

INSERT IGNORE INTO yangbong.stock_ai_content
    SELECT * FROM stock.stock_ai_content;
