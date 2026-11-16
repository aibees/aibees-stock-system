-- ============================================================================
-- yangbong/007_stock_ai_gen_log.sql  (2026-11-16)
--
-- AI 분석 생성 기록 + 하루 생성 한도 공통코드. 같은 변경: stock/002_stock_ai_gen_log.sql
--
-- 왜: AI 분석 새로 만들기(POST /anthropic/stock-analysis/overview·theme, 뉴스 자동 생성)는 로그인만 하면
--     누구나 부를 수 있었다. 양봉상회는 누구나 가입하므로 Anthropic 비용(웹 검색 포함)이 그대로 열린다.
--     API(StockAiContentService)가 AI 를 부르기 전에 이 표에 한 줄을 남기고, 오늘 건수로 한도를 센다.
--     ⚠ 이 표가 없으면 관리자(user_id=1) 외에는 생성이 막힌다(fail closed) — API 배포 전에 적용한다.
--
--   stock_ai_gen_log : 생성 1건 = 1행. created_at 은 API 서버(KST) 시각.
--   master_codes     : stock/setting/ai — GEN_PER_USER_DAY(사용자별 하루, 관리자 제외), GEN_TOTAL_DAY(서버 전체 하루).
--                      행이 없으면 환경변수 AI_GEN_PER_USER_DAY·AI_GEN_TOTAL_DAY → 코드 기본값(양봉상회 5·100).
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포
-- 확인:
--   SHOW CREATE TABLE yangbong.stock_ai_gen_log;
--   SHOW GRANTS FOR 'yangbong'@'%';         -- stock_ai_gen_log 에 INSERT, DELETE
--   SELECT code, `desc` FROM yangbong.master_codes WHERE category = 'ai';
--   -- 오늘 생성 건수: SELECT user_id, COUNT(*) FROM yangbong.stock_ai_gen_log WHERE created_at >= CURDATE() GROUP BY user_id;
-- 되돌리기:
--   DROP TABLE yangbong.stock_ai_gen_log;
--   DELETE FROM yangbong.master_codes WHERE `system` = 'stock' AND source = 'setting' AND category = 'ai';
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.stock_ai_gen_log (
    log_id      BIGINT      NOT NULL AUTO_INCREMENT,
    user_id     INT         NOT NULL,
    stock_code  VARCHAR(20) NOT NULL,
    section     VARCHAR(20) NOT NULL COMMENT 'overview | theme | news',
    created_at  DATETIME    NOT NULL COMMENT 'API 서버(KST) 시각',
    PRIMARY KEY (log_id),
    KEY idx_stock_ai_gen_log_created (created_at),
    KEY idx_stock_ai_gen_log_user (user_id, created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AI 분석 생성 기록(하루 생성 한도 계산)';

-- 계정 이름은 001 의 CREATE USER 를 따른다('yangbong'). ⚠ 002 의 GRANT 는 아직 'yangbong_api' 로 적혀 있다.
GRANT INSERT, DELETE ON yangbong.stock_ai_gen_log TO 'yangbong'@'%';

INSERT IGNORE INTO yangbong.master_codes (`system`, source, category, code, `desc`) VALUES
    ('stock', 'setting', 'ai', 'GEN_PER_USER_DAY', '5'),
    ('stock', 'setting', 'ai', 'GEN_TOTAL_DAY',    '100');
