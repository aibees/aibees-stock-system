-- ============================================================================
-- yangbong/006_seed_stock_menus.sql  (2026-11-16)
--
-- 주식분석 화면(매수추천·AI 분석·차트 확인) 메뉴 행과 추천 단계 공통코드를 넣는다. 여러 번 실행해도 같은 결과(INSERT IGNORE).
--
-- 왜: 양봉상회 화면 라우트는 GET /api/v1/master/menus 의 행으로 만든다. 004 에는 공개 메뉴 6개뿐이라
--     /stock/buy-target·/stock/info·/stock/chart 가 NotFound 였고, 하단 '주식분석' 탭도 숨었다.
--     (내 설정 /stock/preset 과 트레이닝 /training 은 프런트 정적 라우트라 행이 필요 없다)
--
--   master_menu  : Stocks(/stock) 아래 StockBuyTarget·StockInfo·ChartStock. 공개 메뉴(public_flag='Y')라
--                  role_menu 매핑은 필요 없다 — 비로그인·일반 회원 모두 보인다.
--                  제목은 양봉상회 화면 문구로 바꿔 넣는다(비밀상회 원본: 주식정보·개별주식·개별차트).
--                  업종(StockSector)·국채금리(WorldIndicators)·테마는 넣지 않는다(양봉상회 화면 미정).
--   master_codes : stock/setting/reco_algo(BASIC·PREMIUM·PRIVATE → 추천 단계 번호). 없어도 코드 기본값으로
--                  동작하지만 비밀상회와 같은 값으로 맞춘다.
--
-- 적용 순서: 이 SQL → 앱 새로고침(메뉴는 요청마다 읽으므로 API 재시작 필요 없음)
-- 확인:
--   SELECT menu_code, menu_parents, menu_path, menu_title, public_flag FROM yangbong.master_menu
--    WHERE menu_code IN ('Stocks', 'StockBuyTarget', 'StockInfo', 'ChartStock');          -- 4행
--   SELECT code, `desc` FROM yangbong.master_codes WHERE category = 'reco_algo';         -- 3행
-- 되돌리기:
--   DELETE FROM yangbong.master_menu WHERE menu_code IN ('Stocks', 'StockBuyTarget', 'StockInfo', 'ChartStock');
--   DELETE FROM yangbong.master_codes WHERE `system` = 'stock' AND source = 'setting' AND category = 'reco_algo';
-- ============================================================================

INSERT IGNORE INTO yangbong.master_menu
    (menu_code, menu_parents, menu_name, menu_path, enabled_flag, display_flag, menu_component,
     menu_title, sort, admin_only, common_flag, public_flag)
SELECT menu_code, menu_parents, menu_name, menu_path, 'Y', 'Y', menu_component,
       CASE menu_code
           WHEN 'Stocks'         THEN '주식분석'
           WHEN 'StockBuyTarget' THEN '매수추천'
           WHEN 'StockInfo'      THEN 'AI 분석'
           WHEN 'ChartStock'     THEN '차트 확인'
       END,
       sort, admin_only, 'N', 'Y'
  FROM stock.master_menu
 WHERE menu_code IN ('Stocks', 'StockBuyTarget', 'StockInfo', 'ChartStock');

INSERT IGNORE INTO yangbong.master_codes
    SELECT * FROM stock.master_codes WHERE `system` = 'stock' AND source = 'setting' AND category = 'reco_algo';
