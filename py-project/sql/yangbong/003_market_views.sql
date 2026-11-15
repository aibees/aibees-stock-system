-- ============================================================================
-- yangbong/003_market_views.sql  (2026-11-15)
--
-- 시장 데이터를 `yangbong` 에서 같은 이름으로 읽게 하는 읽기 전용 뷰.
--   - 원본은 `stock` 에 하나만 있고 배치가 매일 쓴다(복사하지 않는다). 양봉상회 API 코드는 테이블 이름 그대로 읽는다.
--   - SQL SECURITY DEFINER: yangbong_api 는 `stock` 권한 없이 뷰 권한(SELECT)만으로 읽는다.
--     DEFINER 는 이 파일을 실행한 관리자 계정이 된다 — 그 계정을 지우면 뷰가 깨진다.
--   - ALGORITHM=MERGE: 조회 조건이 원본 테이블 인덱스를 그대로 탄다(일봉 320만 행).
--   - yangbong_api 에게는 SELECT 만 있으므로 뷰를 통해 원본을 고칠 수 없다(001 의 권한 설계 참고).
--
-- ⚠ SELECT * 는 뷰를 만든 시점의 컬럼으로 고정된다. 원본(`stock`) 테이블에 컬럼을 추가하면
--   여기 해당 줄을 다시 실행해야 양봉상회에서 새 컬럼이 보인다.
--
-- 대상: 양봉상회가 읽는 시장 데이터만. 화면(트레이닝 등)이 늘면 여기에 추가한다.
--   매매 테이블(trade_worker_*, trade_log, user_wallet …)과 최우선 타겟(trade_buy_target_priority)은 넣지 않는다.
--   관리종목·거래정지 표시는 master_stock 의 admin_issue / trading_halt / market_stop 을 쓴다(매일 갱신).
--     stock_admin_status 는 2026-09-16 한 번 찍은 연구용 스냅샷(app/test/scan_admin_status.py)이라 넣지 않는다.
--   테마·관리종목은 양봉상회 화면에만 쓴다(2026-11-15 결정) — 원본은 시장 데이터라 `stock` 에 두고,
--     비밀상회는 화면에서 메뉴를 뺀다.
--
-- 확인: SELECT COUNT(*) FROM yangbong.trade_buy_target_stock;  (관리자 / yangbong_api 둘 다)
-- 되돌리기: DROP VIEW yangbong.<이름>;
-- ============================================================================

-- 종목 기본 정보(종목명·업종·상장주식 수 → 시가총액)
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.master_stock
    AS SELECT * FROM stock.master_stock;

-- 일봉(트레이닝 차트·변동 크기 계산)
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.stock_ohlcv_daily
    AS SELECT * FROM stock.stock_ohlcv_daily;

-- 투자자별 매매 동향(주목 종목에 붙는 수급 정보)
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.stock_investor_daily
    AS SELECT * FROM stock.stock_investor_daily;

-- 시장이 주목하는 종목(현재 홈 목록 = 2파 종합순위)
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.trade_buy_target_stock
    AS SELECT * FROM stock.trade_buy_target_stock;

-- 기본(BASIC) 단계 목록 — 기본·고급 단계 분리가 배포되면 무료 사용자 목록이 된다
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.trade_buy_target_basic
    AS SELECT * FROM stock.trade_buy_target_basic;

-- 주목 종목 간이 차트(최근 120영업일)
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.trade_buy_target_chart
    AS SELECT * FROM stock.trade_buy_target_chart;

-- 지난달 성과
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.trade_buy_target_perf_monthly
    AS SELECT * FROM stock.trade_buy_target_perf_monthly;

-- 테마(테마 그룹·테마별 종목)
--   ⚠ 2026-06-08 한 번 적재된 뒤 갱신하는 배치가 없다. 화면에 쓰기 전에 갱신 배치(원본 `stock` 에 쓰기)를 먼저 만든다.
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.master_themes_group
    AS SELECT * FROM stock.master_themes_group;
CREATE OR REPLACE ALGORITHM=MERGE SQL SECURITY DEFINER VIEW yangbong.master_themes_code
    AS SELECT * FROM stock.master_themes_code;
