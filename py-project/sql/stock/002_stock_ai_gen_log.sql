-- ============================================================================
-- stock/002_stock_ai_gen_log.sql  (2026-11-16)
--
-- AI 분석 생성 기록 + 하루 생성 한도 공통코드(비밀상회). 같은 변경: yangbong/007_stock_ai_gen_log.sql
--
-- 왜: AI 분석 새로 만들기는 로그인만 하면 누구나 부를 수 있었다. API(StockAiContentService)가 AI 를 부르기 전에
--     이 표에 한 줄을 남기고, 오늘 건수로 한도를 센다.
--     ⚠ 이 표가 없으면 관리자(user_id=1) 외에는 생성이 막힌다(fail closed) — API 배포 전에 적용한다.
--
--   stock_ai_gen_log : 생성 1건 = 1행. created_at 은 API 서버(KST) 시각.
--   master_codes     : stock/setting/ai — GEN_PER_USER_DAY(사용자별 하루, 관리자 제외), GEN_TOTAL_DAY(서버 전체 하루).
--                      행이 없으면 환경변수 → 코드 기본값(비밀상회 30·300).
--
-- 적용 순서: 이 SQL → 비밀상회 API 배포
-- 확인:
--   SHOW CREATE TABLE stock.stock_ai_gen_log;
--   SELECT code, `desc` FROM stock.master_codes WHERE category = 'ai';
-- 되돌리기:
--   DROP TABLE stock.stock_ai_gen_log;
--   DELETE FROM stock.master_codes WHERE `system` = 'stock' AND source = 'setting' AND category = 'ai';
-- ============================================================================

CREATE TABLE IF NOT EXISTS stock.stock_ai_gen_log (
    log_id      BIGINT      NOT NULL AUTO_INCREMENT,
    user_id     INT         NOT NULL,
    stock_code  VARCHAR(20) NOT NULL,
    section     VARCHAR(20) NOT NULL COMMENT 'overview | theme | news',
    created_at  DATETIME    NOT NULL COMMENT 'API 서버(KST) 시각',
    PRIMARY KEY (log_id),
    KEY idx_stock_ai_gen_log_created (created_at),
    KEY idx_stock_ai_gen_log_user (user_id, created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AI 분석 생성 기록(하루 생성 한도 계산)';

INSERT IGNORE INTO stock.master_codes (`system`, source, category, code, `desc`) VALUES
    ('stock', 'setting', 'ai', 'GEN_PER_USER_DAY', '30'),
    ('stock', 'setting', 'ai', 'GEN_TOTAL_DAY',    '300');
