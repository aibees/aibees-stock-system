-- ============================================================================
-- yangbong/010_consent_history_retention.sql  (2026-11-21)
--
-- 개인정보 처리방침 심사 대비 두 가지.
--
-- ① user_consent_history — 동의 이력(입증용).
--    user_consent 는 (user_id, consent_type) 1행이라 재동의하면 이전 버전·시각을 덮어쓴다.
--    "언제 어떤 버전에 동의했는지"를 남기려고 동의할 때마다 1행씩 쌓는다(서버 socialLoginDao.save_consent).
--    탈퇴하면 함께 지운다(router_account._ACCOUNT_DELETE_TABLES).
--    이 테이블이 없는 스키마(비밀상회 stock)에서는 서버가 이력 저장을 건너뛴다.
--
-- ② 보관 기간 파기 — 실제 삭제는 배치 서버가 매일 04:30 에 한다(stock 계정, yangbong 에 DELETE 권한 있음).
--    py-stock-batch app/batches/jobs/PrivacyRetentionJob.py · 등록 sql/stock/004_privacy_retention_job.sql
--    처리방침 3항과 같은 기간:
--      user_login_log · user_menu_access_log : 3개월. 단 관리자(ADMIN) 기록은 1년
--                                               (개인정보 안전성 확보조치 기준 — 개인정보취급자 접속기록 1년 이상)
--      device_push_token                     : 꺼진(enabled_flag='N') 뒤 30일
--
-- 적용 순서: 이 SQL → 양봉상회 API 배포. 관리자 계정으로 실행. 여러 번 실행해도 된다.
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.user_consent_history (
    history_id   BIGINT       NOT NULL AUTO_INCREMENT,
    user_id      INT          NOT NULL,
    consent_type VARCHAR(30)  NOT NULL COMMENT 'TERMS / PRIVACY / AGE14 (user_consent 와 같은 값)',
    version      VARCHAR(20)  NOT NULL COMMENT '동의한 문서 버전(시행일)',
    agreed_date  DATETIME     NOT NULL,
    PRIMARY KEY (history_id),
    KEY idx_user_consent_history_user (user_id, consent_type, agreed_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='동의 이력(재동의해도 지우지 않음). 탈퇴 시 삭제';
-- ※ COLLATE 는 user_consent 와 같아야 한다(utf8mb4_general_ci). 빼면 서버 기본값(utf8mb4_0900_ai_ci)이 되어
--   아래 INSERT 의 비교에서 1267(Illegal mix of collations) 오류가 난다.
--   COLLATE 없이 이미 만들었다면 이것만 한 번 실행한다:
--   ALTER TABLE yangbong.user_consent_history CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- 지금까지의 동의(현재 버전 1건씩)를 이력의 첫 행으로 옮긴다. 이미 옮긴 행은 건너뛴다.
INSERT INTO yangbong.user_consent_history (user_id, consent_type, version, agreed_date)
SELECT c.user_id, c.consent_type, c.version, COALESCE(c.agreed_date, NOW())
  FROM yangbong.user_consent c
 WHERE NOT EXISTS (
       SELECT 1 FROM yangbong.user_consent_history h
        WHERE h.user_id = c.user_id AND h.consent_type = c.consent_type AND h.version = c.version);

GRANT INSERT, DELETE ON yangbong.user_consent_history TO 'yangbong'@'%';

-- 확인
--   SELECT COUNT(*) FROM yangbong.user_consent_history;                 -- user_consent 행 수와 같다(현재 21)
--   SHOW GRANTS FOR 'yangbong'@'%';
--   지금 파기 대상이 몇 건인지(배치가 지울 것):
--   SELECT COUNT(*) FROM yangbong.user_login_log WHERE created_date < NOW() - INTERVAL 3 MONTH;
--   SELECT COUNT(*) FROM yangbong.device_push_token WHERE enabled_flag = 'N' AND updated_at < NOW() - INTERVAL 30 DAY;
-- ============================================================================
