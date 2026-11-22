-- ============================================================================
-- yangbong/014_training_chart_quiz.sql  (2026-11-22)
--
-- 트레이닝 차트 퀴즈. 명세: meetings/설계_2026-11-22_트레이닝-화면.md
--   과거 차트(120봉, 종목·날짜 비공개, 기준일 종가 = 100)를 보고 "20일 뒤 상승 / 보합 / 하락"을 고른다.
--   결과는 판정이 아니라 대조다 — 열 이름도 match 계열을 쓴다(is_match).
--
--   pattern             : 문제 소재가 되는 패턴 정의. 화면(아카이브)·문제 생성 워커가 함께 쓴다.
--                         condition_json.type 을 워커(app/services/training/patterns.py)가 읽어 판정한다.
--                         tier='ADVANCED' 는 is_public=0 — 문제로 내지 않는다.
--   pattern_stat        : 패턴별 과거 집계(최근 12·36·60개월). 워커가 매일 다시 계산해 덮어쓴다.
--   training_question   : 출제 문제. 차트·지표를 출제 시점 값으로 동결(snapshot_json)한다.
--                         stock_code·base_date 는 내부 전용 — 어떤 API 응답에도 넣지 않는다.
--   training_attempt    : 사용자 응답. 같은 문제는 1번만 기록된다(uk_ua).
--   training_hint_log   : 힌트를 연 기록. 답을 낼 때 화면이 보낸 값과 상관없이 이 기록이 있으면 힌트 사용으로 친다.
--   training_daily_set  : 사용자별 그날 출제 세트(무료 3문제). 처음 연 순간 정하고 그날은 바꾸지 않는다.
--   사용자 행(training_attempt · training_hint_log · training_daily_set)은 탈퇴하면 지운다(router_account._ACCOUNT_DELETE_TABLES).
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포(training-worker 포함) → 워커로 문제 선적재 → 화면 배포.
--   선적재: docker compose -f py-yangbong-api/docker-compose.yml run --rm training-worker \
--             poetry run python -m app.workers.training_worker --backfill 40
-- 관리자 계정으로 실행. CREATE TABLE·GRANT 는 여러 번 실행해도 된다.
-- 패턴 INSERT 는 INSERT IGNORE 라 다시 실행해도 같은 code 는 그대로 둔다(문구를 고치려면 UPDATE 로).
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.pattern (
    id              BIGINT        NOT NULL AUTO_INCREMENT,
    code            VARCHAR(64)   NOT NULL COMMENT '예: MA20_BREAK_VOL2',
    name            VARCHAR(128)  NOT NULL COMMENT '화면 이름. 예: 20일선 돌파 + 거래량 2배',
    description     TEXT          NULL,
    condition_json  JSON          NOT NULL COMMENT '판정 조건. type 을 워커가 읽는다',
    tier            VARCHAR(16)   NOT NULL COMMENT 'BASIC / ADVANCED',
    is_public       TINYINT(1)    NOT NULL DEFAULT 1 COMMENT 'ADVANCED 는 0 — 문제로 내지 않는다',
    created_at      DATETIME      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_pattern_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='차트 패턴 정의(아카이브·트레이닝)';

CREATE TABLE IF NOT EXISTS yangbong.pattern_stat (
    pattern_id      BIGINT    NOT NULL,
    window_months   INT       NOT NULL COMMENT '12, 36, 60',
    occurrences     INT       NOT NULL,
    up_count        INT       NOT NULL COMMENT '20거래일 뒤 +5% 이상',
    down_count      INT       NOT NULL COMMENT '20거래일 뒤 -5% 이하',
    flat_count      INT       NOT NULL,
    computed_at     DATETIME  NOT NULL,
    PRIMARY KEY (pattern_id, window_months)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='패턴별 과거 집계(워커가 매일 갱신)';

CREATE TABLE IF NOT EXISTS yangbong.training_question (
    id              BIGINT        NOT NULL AUTO_INCREMENT,
    pattern_id      BIGINT        NOT NULL,
    stock_code      VARCHAR(12)   NOT NULL COMMENT '내부 전용. 응답에 절대 포함 금지',
    base_date       DATE          NOT NULL COMMENT '내부 전용. 마지막으로 보여 주는 봉의 날짜(D)',
    level           TINYINT       NOT NULL COMMENT '1~4',
    snapshot_json   JSON          NOT NULL COMMENT '과거 120봉 + 미래 20봉 + 지표(정규화, 출제 시점 동결)',
    outcome_json    JSON          NOT NULL COMMENT '{ret, direction, maxDrawdown, maxGain, ...}',
    explanation     TEXT          NOT NULL,
    hint            VARCHAR(255)  NOT NULL,
    created_at      DATETIME      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_q (stock_code, base_date, pattern_id),
    KEY idx_q_level (level, id),
    KEY idx_q_base_date (base_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='트레이닝 차트 퀴즈 문제';

CREATE TABLE IF NOT EXISTS yangbong.training_attempt (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    user_id         INT          NOT NULL,
    question_id     BIGINT       NOT NULL,
    answer          VARCHAR(8)   NOT NULL COMMENT 'UP / FLAT / DOWN',
    used_hint       TINYINT(1)   NOT NULL,
    is_match        TINYINT(1)   NOT NULL,
    score           INT          NOT NULL,
    answered_at     DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_ua (user_id, question_id),
    KEY idx_attempt_user_time (user_id, answered_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='트레이닝 차트 퀴즈 응답. 탈퇴 시 삭제';

CREATE TABLE IF NOT EXISTS yangbong.training_hint_log (
    user_id         INT          NOT NULL,
    question_id     BIGINT       NOT NULL,
    used_at         DATETIME     NOT NULL,
    PRIMARY KEY (user_id, question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='트레이닝 힌트 사용 기록. 탈퇴 시 삭제';

CREATE TABLE IF NOT EXISTS yangbong.training_daily_set (
    user_id         INT          NOT NULL,
    set_date        DATE         NOT NULL,
    question_ids    JSON         NOT NULL COMMENT '[문제 id, ...] 출제 순서대로',
    PRIMARY KEY (user_id, set_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='트레이닝 일일 출제 세트. 탈퇴 시 삭제';

-- 워커가 pattern_stat·training_question 을 쓰고, API 가 사용자 행을 쓴다(둘 다 yangbong 계정).
GRANT SELECT ON yangbong.pattern TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.pattern_stat TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE ON yangbong.training_question TO 'yangbong'@'%';
GRANT SELECT, INSERT, DELETE ON yangbong.training_attempt TO 'yangbong'@'%';
GRANT SELECT, INSERT, DELETE ON yangbong.training_hint_log TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.training_daily_set TO 'yangbong'@'%';

-- 연결 한도: API 최대 12 + AI 워커 최대 3 = 15 였다. 트레이닝 워커(최대 1)를 더해 16.
ALTER USER 'yangbong'@'%' WITH MAX_USER_CONNECTIONS 16;

-- ── 패턴(기본 tier 11개 + 고급 1개) ──────────────────────────────────────
--   condition_json.type 별 판정은 py-yangbong-api/app/services/training/patterns.py.
--   volMult: 그날 거래량 ÷ 직전 20일 평균 거래량.
INSERT IGNORE INTO yangbong.pattern (code, name, description, condition_json, tier, is_public, created_at) VALUES
('MA20_BREAK_VOL2',     '20일선 돌파 + 거래량 2배',   '전날까지 20일 이동평균선 아래에 있던 종가가 위로 올라섰고, 거래량이 직전 20일 평균의 2배 이상인 날.',
    '{"type":"MA_CROSS_UP","ma":20,"volMult":2}', 'BASIC', 1, NOW()),
('MA20_BREAKDOWN_VOL2', '20일선 이탈 + 거래량 2배',   '전날까지 20일 이동평균선 위에 있던 종가가 아래로 내려갔고, 거래량이 직전 20일 평균의 2배 이상인 날.',
    '{"type":"MA_CROSS_DOWN","ma":20,"volMult":2}', 'BASIC', 1, NOW()),
('MA5_20_GOLDEN',       '5일선이 20일선 위로',        '5일 이동평균선이 20일 이동평균선을 아래에서 위로 넘은 날.',
    '{"type":"MA_GOLDEN","fast":5,"slow":20}', 'BASIC', 1, NOW()),
('MA5_20_DEAD',         '5일선이 20일선 아래로',      '5일 이동평균선이 20일 이동평균선을 위에서 아래로 넘은 날.',
    '{"type":"MA_DEAD","fast":5,"slow":20}', 'BASIC', 1, NOW()),
('HIGH60_BREAK_VOL2',   '60일 최고가 돌파 + 거래량 2배', '종가가 직전 60일 동안의 가장 높은 종가를 넘었고, 거래량이 직전 20일 평균의 2배 이상인 날.',
    '{"type":"HIGH_BREAK","days":60,"volMult":2}', 'BASIC', 1, NOW()),
('VOL3_LONG_UP',        '거래량 3배 + 큰 양봉',       '하루에 5% 이상 오른 양봉이고, 거래량이 직전 20일 평균의 3배 이상인 날.',
    '{"type":"LONG_CANDLE_UP","minChange":5,"volMult":3}', 'BASIC', 1, NOW()),
('RSI30_REBOUND',       'RSI 30 위로 회복',           'RSI(14)가 30 아래에 있다가 다시 30 위로 올라온 날.',
    '{"type":"RSI_CROSS_UP","period":14,"level":30}', 'BASIC', 1, NOW()),
('RSI70_DROP',          'RSI 70 아래로',              'RSI(14)가 70 위에 있다가 70 아래로 내려온 날.',
    '{"type":"RSI_CROSS_DOWN","period":14,"level":70}', 'BASIC', 1, NOW()),
('MACD_GOLDEN_BELOW0',  'MACD 시그널 위로(0 아래)',    'MACD 선이 0 아래에서 시그널 선을 아래에서 위로 넘은 날.',
    '{"type":"MACD_CROSS_UP","below0":true}', 'BASIC', 1, NOW()),
('BB_UPPER_BREAK',      '볼린저밴드 상단 돌파',       '종가가 볼린저밴드(20일, 표준편차 2배) 위쪽 선을 넘어선 날.',
    '{"type":"BB_BREAK_UP","period":20,"k":2}', 'BASIC', 1, NOW()),
('BB_LOWER_BREAK',      '볼린저밴드 하단 이탈',       '종가가 볼린저밴드(20일, 표준편차 2배) 아래쪽 선 밑으로 내려간 날.',
    '{"type":"BB_BREAK_DOWN","period":20,"k":2}', 'BASIC', 1, NOW()),
('WAVE2_BREAK',         '2파 하락추세선 돌파',        '고급 조건. 문제로 내지 않는다.',
    '{"type":"ADVANCED"}', 'ADVANCED', 0, NOW());

-- 확인
--   SELECT id, code, tier, is_public FROM yangbong.pattern ORDER BY id;
--   SELECT p.code, s.* FROM yangbong.pattern_stat s JOIN yangbong.pattern p ON p.id = s.pattern_id ORDER BY p.id, s.window_months;
--   SELECT level, COUNT(*) FROM yangbong.training_question GROUP BY level;
--   SELECT MAX_USER_CONNECTIONS FROM mysql.user WHERE user = 'yangbong';
-- 되돌리기: DROP TABLE yangbong.training_daily_set, yangbong.training_hint_log, yangbong.training_attempt,
--           yangbong.training_question, yangbong.pattern_stat, yangbong.pattern;
