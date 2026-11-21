-- ============================================================================
-- yangbong/011_user_training_progress.sql  (2026-11-22)
--
-- 트레이닝 학습 기록(계정 저장). 내 설정의 기본 보조지표는 트레이닝에서 그 지표 단계를 마치면 열린다 —
-- 기기(localStorage)에만 두면 앱 재설치·다른 기기·브라우저 데이터 삭제 때 기록이 사라져서 계정에 남긴다.
--
--   user_training_progress : 마친 단계 1개당 1행. 지우지 않고 쌓기만 한다(기기 값과 합칠 때 합집합).
--     stage_key : 트레이닝 단계 key "<장 slug>/<단계 id>" (yangbong-store-vue scripts/data/trainingToc.json).
--                 목차는 화면 데이터라 값 목록은 제약하지 않는다.
--     done_at   : 그 단계를 처음 마친 시각. 기기에서 먼저 마친 기록을 올릴 때도 올린 시각으로 넣는다.
--   탈퇴하면 함께 지운다(router_account._ACCOUNT_DELETE_TABLES).
--
-- 주식분석 유의사항 동의는 새 테이블 없이 기존 동의 표에 consent_type 'STOCK_NOTICE' 로 남긴다
-- (user_consent 현재 버전 1행 + user_consent_history 이력, 서버 socialLoginDao.save_consent).
-- 로그인 필수 동의(REQUIRED_CONSENTS)에는 넣지 않으므로 로그인 흐름에는 영향이 없다.
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포 → 화면 배포. 관리자 계정으로 실행. 여러 번 실행해도 된다.
-- 이 SQL 을 적용하기 전에 API 가 먼저 배포돼도 학습 기록 API 는 빈 값으로 응답한다(화면은 기기 기록으로 동작).
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.user_training_progress (
    user_id    INT          NOT NULL,
    stage_key  VARCHAR(80)  NOT NULL COMMENT '트레이닝 단계 key "<장 slug>/<단계 id>"',
    done_at    DATETIME     NOT NULL COMMENT '처음 마친 시각(API 서버가 기록)',
    PRIMARY KEY (user_id, stage_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='트레이닝 학습 기록(마친 단계). 탈퇴 시 삭제';

GRANT SELECT, INSERT, DELETE ON yangbong.user_training_progress TO 'yangbong'@'%';

-- 확인
--   SHOW CREATE TABLE yangbong.user_training_progress;
--   SHOW GRANTS FOR 'yangbong'@'%';
--   SELECT user_id, COUNT(*) FROM yangbong.user_training_progress GROUP BY user_id;
--   SELECT * FROM yangbong.user_consent WHERE consent_type = 'STOCK_NOTICE';
