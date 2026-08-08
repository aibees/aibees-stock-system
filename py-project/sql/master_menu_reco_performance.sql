-- ============================================================
-- 추천 성과 추적 화면 메뉴 등록
--
-- componentLoader 규칙: menu_parents + menu_component
--     /src/components/Trade/RecoPerformance.vue
-- 접근 URL: /trade/reco-performance
-- ============================================================

INSERT INTO master_menu
    (menu_code, menu_parents, menu_name, menu_path, menu_component, menu_title,
     sort, admin_only, enabled_flag, display_flag)
VALUES
    ('RecoPerformance', 'Trade', 'RECO PERFORMANCE', 'reco-performance', 'RecoPerformance', '추천 성과',
     706, NULL, 'Y', 'Y');


-- ============================================================
-- 확인
-- ============================================================
-- SELECT menu_code, menu_path, menu_component, menu_title, sort
--   FROM master_menu WHERE menu_parents = 'Trade' ORDER BY sort;
--
-- ※ 등록 후 재로그인(또는 sessionStorage 의 menuList 삭제) 필요.

-- ============================================================
-- 사전조건 — 추천 종목의 캔들이 있어야 한다
-- ============================================================
-- 캔들 없는 추천 건 확인:
--   SELECT COUNT(*) FROM trade_buy_target_stock t
--     LEFT JOIN (SELECT DISTINCT coin FROM trade_candle_data) c ON c.coin = t.stock_code
--    WHERE c.coin IS NULL;
--
-- 부족하면 백필 배치 실행:
--   POST /api/v1/jobs/once/STOCK_CANDLE_BACKFILL_JOB   body {"days": 180}
