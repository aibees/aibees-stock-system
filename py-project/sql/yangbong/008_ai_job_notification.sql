-- ============================================================================
-- yangbong/008_ai_job_notification.sql  (2026-11-18)
--
-- AI 분석 생성 비동기화 + 앱 내 알림함 + 재무 지표 캐시.
-- 설계: meetings/설계_2026-11-18_AI분석-비동기화.md
--
-- 왜: AI 생성(웹 검색 포함)을 HTTP 요청 안에서 수십 초씩 기다리면 gunicorn 워커가 묶이고,
--     같은 종목을 여럿이 누르면 같은 생성이 중복으로 돈다. 또 API 프로세스 여럿이 KIS 토큰을
--     각자 발급하다가 1분 1회 제한(EGW00133)에 걸렸다. 그래서 요청은 이 표에 쌓기만 하고,
--     양봉 AI 워커(프로세스 1개, KIS 토큰 1개)가 꺼내 처리한 뒤 알림을 남긴다.
--
--   stock_ai_job            : 생성 작업 1건. 같은 종목·섹션의 진행 중(QUEUED·RUNNING) 작업은 1건만(active_key UNIQUE).
--   stock_ai_job_subscriber : 그 작업을 기다리는 사람들. 완료되면 이 사람들에게 알림을 보낸다.
--   user_notification       : 앱 내 알림함.
--   stock_finance_snapshot  : 재무 지표(KIS) 캐시. API 서버는 KIS 를 부르지 않고 이 표만 읽는다.
--   master_codes            : stock/setting/ai 의 AI_WORKER_CONCURRENCY(워커 동시 실행 수).
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포 → AI 워커 기동
-- 확인:
--   SHOW TABLES FROM yangbong LIKE 'stock_ai_job%';
--   SHOW TABLES FROM yangbong LIKE 'user_notification';
--   SHOW TABLES FROM yangbong LIKE 'stock_finance_snapshot';
--   SHOW GRANTS FOR 'yangbong'@'%';
--   -- 진행 중 작업: SELECT job_id, stock_code, section, status, created_at FROM yangbong.stock_ai_job WHERE active_key IS NOT NULL;
-- 되돌리기:
--   DROP TABLE yangbong.stock_ai_job_subscriber, yangbong.stock_ai_job, yangbong.user_notification, yangbong.stock_finance_snapshot;
--   DELETE FROM yangbong.master_codes WHERE `system`='stock' AND source='setting' AND category='ai' AND code='AI_WORKER_CONCURRENCY';
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.stock_ai_job (
    job_id        BIGINT       NOT NULL AUTO_INCREMENT,
    stock_code    VARCHAR(20)  NOT NULL,
    section       VARCHAR(20)  NOT NULL COMMENT 'overview | theme | news | finance',
    status        VARCHAR(10)  NOT NULL DEFAULT 'QUEUED' COMMENT 'QUEUED | RUNNING | DONE | FAILED',
    priority      TINYINT      NOT NULL DEFAULT 5 COMMENT '작을수록 먼저. 사용자 요청 1, 재무 3, 뉴스 자동 5',
    created_by    INT          NULL     COMMENT '작업을 만든 user_id. 뉴스·재무 자동 작업은 NULL',
    force_flag    CHAR(1)      NOT NULL DEFAULT 'N' COMMENT '관리자 쿨다운 우회',
    gen_log_id    BIGINT       NULL     COMMENT '차감한 stock_ai_gen_log.log_id — 실패하면 지워서 환불',
    attempts      TINYINT      NOT NULL DEFAULT 0,
    error_user    VARCHAR(255) NULL     COMMENT '사용자에게 보여 줄 문구',
    error_detail  TEXT         NULL     COMMENT '원문(로그용, API 로 내보내지 않음)',
    created_at    DATETIME     NOT NULL COMMENT 'API 서버(KST) 시각',
    started_at    DATETIME     NULL,
    finished_at   DATETIME     NULL,
    -- 진행 중일 때만 값이 있고 끝나면 NULL → UNIQUE 가 "진행 중 작업은 종목·섹션당 1건"만 막는다(NULL 은 중복 허용).
    active_key    VARCHAR(40)  AS (IF(status IN ('QUEUED', 'RUNNING'), CONCAT(stock_code, ':', section), NULL)) STORED,
    PRIMARY KEY (job_id),
    UNIQUE KEY uk_stock_ai_job_active (active_key),
    KEY idx_stock_ai_job_queue (status, priority, created_at),
    KEY idx_stock_ai_job_stock (stock_code, section, created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AI 분석 생성 작업 큐';

CREATE TABLE IF NOT EXISTS yangbong.stock_ai_job_subscriber (
    job_id      BIGINT   NOT NULL,
    user_id     INT      NOT NULL,
    created_at  DATETIME NOT NULL,
    PRIMARY KEY (job_id, user_id),
    KEY idx_stock_ai_job_subscriber_user (user_id, created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AI 분석 작업을 기다리는 사용자';

CREATE TABLE IF NOT EXISTS yangbong.user_notification (
    notification_id  BIGINT       NOT NULL AUTO_INCREMENT,
    user_id          INT          NOT NULL,
    type             VARCHAR(20)  NOT NULL COMMENT 'AI_DONE | AI_FAILED',
    title            VARCHAR(100) NOT NULL,
    body             VARCHAR(255) NULL,
    link             VARCHAR(255) NULL     COMMENT '앱 안 경로. 예: /stock/info?stock_code=005930&tab=basis',
    ref_id           BIGINT       NULL     COMMENT 'AI_* 는 stock_ai_job.job_id',
    created_at       DATETIME     NOT NULL,
    read_at          DATETIME     NULL,
    PRIMARY KEY (notification_id),
    KEY idx_user_notification_user (user_id, created_at),
    KEY idx_user_notification_unread (user_id, read_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '앱 내 알림함';

CREATE TABLE IF NOT EXISTS yangbong.stock_finance_snapshot (
    stock_code  VARCHAR(20) NOT NULL,
    data        JSON        NOT NULL COMMENT 'FinanceService.get_fundamentals 결과',
    fetched_at  DATETIME    NOT NULL,
    PRIMARY KEY (stock_code)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '재무 지표 캐시(AI 워커가 KIS 로 채움)';

-- 계정 이름은 001 의 CREATE USER 를 따른다('yangbong'). 007 과 같다.
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.stock_ai_job            TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.stock_ai_job_subscriber TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.user_notification       TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.stock_finance_snapshot  TO 'yangbong'@'%';
-- 푸시 토큰 등록을 배치 서버에서 양봉 API 로 옮긴다(2026-11-20 전까지 002 의 GRANT 가 옛 이름 'yangbong_api' 로 적혀 있어 여기서 다시 준다).
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.device_push_token       TO 'yangbong'@'%';

INSERT IGNORE INTO yangbong.master_codes (`system`, source, category, code, `desc`) VALUES
    ('stock', 'setting', 'ai', 'AI_WORKER_CONCURRENCY', '3');
