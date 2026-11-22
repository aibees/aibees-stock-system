-- ============================================================================
-- yangbong/012_honey.sql  (2026-11-22)
--
-- 꿀(포인트) 제도 1단계. 기획: yangbong-store-vue/docs/points-plan.md
--   활동(출석·시작하기·수업·오늘의 문제·광고)으로만 모으고, 프리미엄 하루 이용권에 쓴다. 돈으로 팔지 않는다.
--
--   honey_ledger : 꿀이 들고 난 기록 1건 1행. 지우지 않고 쌓는다(탈퇴 때만 지운다).
--     amount    : +모음 / -씀
--     kind      : ATTEND · STREAK · START · LESSON · QUIZ · AD · SPEND_DAY_PASS
--     ref       : 같은 보상을 두 번 받지 않게 하는 열쇠. ATTEND·QUIZ=YYYYMMDD, STREAK=YYYYMMDD(7일째 날),
--                 START='first', LESSON=단계 key, AD=AdMob transaction_id, SPEND_*=사용 시각 ms
--     ymd       : 기록한 날(KST, YYYYMMDD) — 오늘 모은 꿀·광고 횟수 계산용
--     remaining : 모은 꿀 중 아직 쓰지 않은 양(쓰면 만료가 빠른 것부터 줄인다). 쓴 행은 0
--     expires_at: 모은 날 + 1년. 쓴 행은 NULL
--   honey_pass   : 꿀로 연 이용권. 지금은 DAY(프리미엄 하루 이용권, 24시간)만.
--   탈퇴하면 함께 지운다(router_account._ACCOUNT_DELETE_TABLES).
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포 → 화면 배포. 관리자 계정으로 실행. 여러 번 실행해도 된다.
-- 표가 없으면 꿀 API 는 오류를 돌려주고, 화면은 꿀 영역을 숨긴다.
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.honey_ledger (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    user_id     INT          NOT NULL,
    amount      INT          NOT NULL COMMENT '+모음 / -씀',
    kind        VARCHAR(20)  NOT NULL COMMENT 'ATTEND STREAK START LESSON QUIZ AD SPEND_DAY_PASS',
    ref         VARCHAR(80)  NOT NULL COMMENT '중복 지급 방지 열쇠',
    ymd         CHAR(8)      NOT NULL COMMENT '기록한 날(KST)',
    remaining   INT          NOT NULL DEFAULT 0 COMMENT '모은 꿀 중 남은 양',
    expires_at  DATETIME     NULL COMMENT '모은 날 + 1년',
    created_at  DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_honey_once (user_id, kind, ref),
    KEY idx_honey_user_day (user_id, ymd),
    KEY idx_honey_user_exp (user_id, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='꿀 들고 난 기록. 탈퇴 시 삭제';

CREATE TABLE IF NOT EXISTS yangbong.honey_pass (
    user_id     INT          NOT NULL,
    kind        VARCHAR(20)  NOT NULL COMMENT 'DAY = 프리미엄 하루 이용권',
    expires_at  DATETIME     NOT NULL,
    created_at  DATETIME     NOT NULL,
    PRIMARY KEY (user_id, kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='꿀로 연 이용권. 탈퇴 시 삭제';

GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.honey_ledger TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.honey_pass TO 'yangbong'@'%';

-- 확인
-- SELECT user_id, SUM(remaining) FROM yangbong.honey_ledger WHERE expires_at > NOW() GROUP BY user_id;
