-- ============================================================
-- 트레이드 설정 화면 메뉴 등록
--
-- Vue 라우터는 master_menu 를 읽어 동적 생성된다(scripts/router.js).
-- componentLoader 규칙: menu_parents + menu_component → 파일 경로
--     /src/components/{menu_parents}/{menu_component}.vue
--   → Trade + BuySetting  = /src/components/Trade/BuySetting.vue
--   → Trade + TradeSetting = /src/components/Trade/TradeSetting.vue
--
-- 접근 URL: /trade/buy-setting , /trade/sell-setting
--
-- admin_only 는 NULL(=전체 공개) 로 둔다.
--   매수 후보 정렬은 유저별 개인화 값이라 모두가 들어가야 한다.
--   화면 안의 '후보 선정 조건' 카드만 관리자에게 열리고,
--   실제 차단은 서버(router_strategy._S1_ADMIN_ONLY_COLS)가 한다.
-- ============================================================

-- 매수조건 개인화 설정 (신규)
INSERT INTO master_menu
    (menu_code, menu_parents, menu_name, menu_path, menu_component, menu_title,
     sort, admin_only, enabled_flag, display_flag)
VALUES
    ('BuySetting', 'Trade', 'BUY SETTING', 'buy-setting', 'BuySetting', '매수 설정',
     703, NULL, 'Y', 'Y');

-- 매도조건 개인화 설정 (컴포넌트는 이미 있으나 메뉴 미등록 상태였음)
INSERT INTO master_menu
    (menu_code, menu_parents, menu_name, menu_path, menu_component, menu_title,
     sort, admin_only, enabled_flag, display_flag)
VALUES
    ('TradeSetting', 'Trade', 'SELL SETTING', 'sell-setting', 'TradeSetting', '매도 설정',
     704, NULL, 'Y', 'Y');


-- ============================================================
-- 확인
-- ============================================================
-- SELECT menu_code, menu_parents, menu_path, menu_component, menu_title, sort
--   FROM master_menu WHERE menu_parents = 'Trade' ORDER BY sort;
--
-- ※ 등록 후 브라우저에서 재로그인(또는 sessionStorage 의 menuList 삭제) 해야
--   메뉴가 갱신된다. router.js 가 로그인 시점에 /api/v1/master/menus 를 받아
--   sessionStorage 에 캐시하기 때문.
