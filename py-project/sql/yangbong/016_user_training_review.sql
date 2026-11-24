-- ============================================================================
-- yangbong/016_user_training_review.sql  (2026-11-24)
--
-- 트레이닝 '다시 보기'(오답노트 · 헷갈린 용어 · 복습하기)의 계정 저장.
--   화면(review-store.js)이 기기(localStorage)에 먼저 두고, 로그인하면 이 표와 맞춘다(항목마다 updatedAt 이 늦은 쪽).
--   사람마다 1행, items 에 항목 전체를 JSON 으로 둔다:
--     { "q:<문제 id>" | "t:<용어>": { kind, ref, label, desc, step, due(ms), addedAt, updatedAt, done, removed } }
--   항목은 화면 데이터(문제 id·용어)라 서버는 형식과 크기만 본다(256KB 이하).
--   탈퇴하면 함께 지운다(router_account._ACCOUNT_DELETE_TABLES).
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포 → 화면 배포. 여러 번 실행해도 된다.
-- 이 SQL 보다 API 가 먼저 배포돼도 화면은 기기 기록으로 동작한다(저장 API 만 실패).
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.user_training_review (
    user_id     INT         NOT NULL,
    items       MEDIUMTEXT  NOT NULL COMMENT '다시 보기 항목 JSON',
    updated_at  DATETIME    NOT NULL,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='트레이닝 다시 보기(오답노트·헷갈린 용어·복습). 탈퇴 시 삭제';

GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.user_training_review TO 'yangbong'@'%';
