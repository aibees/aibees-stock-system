-- ============================================================
-- 매수조건 개인화 — user_options 컬럼 추가
--
-- 두 부류가 섞여 있으니 구분해서 볼 것.
--
--  [A] 매수 전략 파라미터 (관리자 전용)
--      KospiStrategy1.configure() 가 읽어 StockBuyCheckJob(매수타겟 생성)에 적용된다.
--      StockBuyCheckJob 은 get_user_options(session) 를 user_id 없이 호출 → user_id=1.
--      결과물 trade_buy_target_stock 은 **전 유저 공용 추천 테이블**이다.
--      → 개인이 바꿔도 반영되지 않고, 바꾸면 전원에게 영향. 그래서 admin 전용.
--      아래 8개는 DTO(userOptionMeta)·configure() 에는 이미 있었으나
--      **컬럼이 없어서 항상 NULL → 전략 클래스 기본값** 이었다. 그 구멍을 메운다.
--
--  [B] worker 개인화 (전 유저)
--      s1_buy_order 는 trade_worker/BuyExecutor 가 후보 정렬에 쓴다.
--      유저별로 달라도 서로 간섭하지 않는다.
-- ============================================================


-- ── [A] 매수 필터 on/off 스위치 (NULL = 전략 기본값 True) ──────────────
ALTER TABLE user_options
    ADD COLUMN s1_enable_macd_filter     TINYINT(1) NULL COMMENT '매수필터: MACD 조건(macd_ok) 사용' AFTER s1_obv_dead_min_bars,
    ADD COLUMN s1_enable_rsi_filter      TINYINT(1) NULL COMMENT '매수필터: RSI 과매수 진입차단 사용' AFTER s1_enable_macd_filter,
    ADD COLUMN s1_enable_bb_upper_filter TINYINT(1) NULL COMMENT '매수필터: BB 상단 추격금지 사용'   AFTER s1_enable_rsi_filter,
    ADD COLUMN s1_enable_vol_avg_filter  TINYINT(1) NULL COMMENT '매수필터: 20일 평균거래량 하한 사용' AFTER s1_enable_bb_upper_filter,
    ADD COLUMN s1_enable_regime_gate     TINYINT(1) NULL COMMENT '매수필터: 적응형 추세국면 게이트 사용' AFTER s1_enable_vol_avg_filter;

-- ── [A] core 진입 신호 mode (NULL = 전략 기본값) ─────────────────────
--   'off' 사용안함 / 'golden' 골든크로스 / 'slope' 기울기 상승
--   전략 기본값: macd='slope', obv='golden'
ALTER TABLE user_options
    ADD COLUMN s1_macd_signal_mode VARCHAR(10) NULL COMMENT 'core 신호 MACD: off|golden|slope' AFTER s1_enable_regime_gate,
    ADD COLUMN s1_obv_signal_mode  VARCHAR(10) NULL COMMENT 'core 신호 OBV: off|golden|slope'  AFTER s1_macd_signal_mode;

-- ── [A] 누락됐던 매도 트레일 giveback 라인 ────────────────────────────
--   DTO·configure·전략 코드에는 이미 있으나 컬럼만 없어 동작하지 않던 항목.
--   (TradeSetting.vue 의 giveback 입력도 이 컬럼이 없어 저장되지 않는다)
ALTER TABLE user_options
    ADD COLUMN s1_trail_giveback_pct DECIMAL(6,4) NULL
    COMMENT '평가이익 중 x% 반납 시 청산 (0.38=38%). NULL=미사용'
    AFTER s1_trail_drawdown_pct;


-- ── [B] worker 매수타겟 정렬 순서 (개인화) ────────────────────────────
-- 형식: "필드[:방향],필드[:방향],..."  (앞 키 동률일 때만 다음 키로 tie-break)
--   방향 생략 시 필드별 기본방향 사용.
--   허용 필드/기본방향의 유일한 정의는 app/trade_worker/repository.py _ORDER_FIELDS:
--     score(desc) · volume(desc) · rate(desc) · rank_no(asc) · close(desc)
--
--   예) 'score:desc,rank_no:asc'           기존 동작(= NULL 일 때 기본값)
--       'score:desc,volume:desc,rate:desc'  score 동률이면 거래량, 그것도 같으면 등락률
--       'volume,rate'                       거래량 우선, 동률이면 등락률
--
-- NULL = 기본값(score:desc,rank_no:asc) 따름.
-- 오타·미지원 필드는 worker 가 조용히 걸러내고 기본값으로 되돌린다(매수 중단 없음).
ALTER TABLE user_options
    ADD COLUMN s1_buy_order VARCHAR(255) NULL
    COMMENT 'worker 매수타겟 정렬 (예 score:desc,volume:desc). NULL=score:desc,rank_no:asc'
    AFTER s1_obv_signal_mode;


-- ============================================================
-- 확인
-- ============================================================
-- SHOW COLUMNS FROM user_options LIKE 's1_%';
-- SELECT user_id, s1_buy_order, s1_macd_signal_mode, s1_obv_signal_mode FROM user_options;

-- 예시 적용
-- UPDATE user_options SET s1_buy_order = 'score:desc,volume:desc,rate:desc' WHERE user_id = 1;
-- UPDATE user_options SET s1_buy_order = NULL WHERE user_id = 1;   -- 기본값으로 되돌림
