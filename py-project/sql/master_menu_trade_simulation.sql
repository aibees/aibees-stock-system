-- ============================================================
-- 시뮬레이션 화면 메뉴 등록
--
-- componentLoader 규칙: menu_parents + menu_component → 파일 경로
--     /src/components/Trade/TradeSimulation.vue
-- 접근 URL: /trade/simulation
--
-- admin_only = NULL (전체 공개) — 개인 설정 기반 시뮬이라 모두가 쓴다.
-- ============================================================

INSERT INTO master_menu
    (menu_code, menu_parents, menu_name, menu_path, menu_component, menu_title,
     sort, admin_only, enabled_flag, display_flag)
VALUES
    ('TradeSimulation', 'Trade', 'SIMULATION', 'simulation', 'TradeSimulation', '시뮬레이션',
     705, NULL, 'Y', 'Y');


-- ============================================================
-- 확인
-- ============================================================
-- SELECT menu_code, menu_path, menu_component, menu_title, sort
--   FROM master_menu WHERE menu_parents = 'Trade' ORDER BY sort;
--
-- ※ 등록 후 재로그인(또는 sessionStorage 의 menuList 삭제) 해야 메뉴가 갱신된다.
--   router.js 가 로그인 시점에 /api/v1/master/menus 를 받아 캐시하기 때문.

-- ============================================================
-- 사전조건
-- ============================================================
-- 시뮬은 trade_candle_data 의 캔들을 읽는다. 비어 있으면 결과가 나오지 않는다.
--   SELECT COUNT(DISTINCT coin), COUNT(*), MIN(datetime), MAX(datetime)
--     FROM trade_candle_data;
--
-- 부족하면 차트 백필 배치를 먼저 실행:
--   POST /api/v1/jobs/once/STOCK_CANDLE_BACKFILL_JOB   body {"days": 120}
