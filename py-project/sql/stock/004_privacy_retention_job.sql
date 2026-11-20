-- ============================================================================
-- stock/004_privacy_retention_job.sql  (2026-11-21)
--
-- 개인정보 보관 기간 파기 배치 등록 — py-stock-batch app/batches/jobs/PrivacyRetentionJob.py
--   양봉상회(yangbong 스키마) 접속 기록 3개월(관리자 1년)·꺼진 푸시 토큰 30일.
--   배치 계정(stock)은 yangbong 스키마에 DELETE 권한이 있다.
--
-- 적용 순서: py-stock-batch 배포(잡 파일 포함) → 이 SQL → 배치 서버의 잡 다시 읽기(재시작 또는 잡 재적재).
--   잡 파일이 없는 서버가 이 행을 읽으면 그 시각에 import 오류로 실패만 남는다(다른 잡에는 영향 없음).
-- 여러 번 실행해도 된다.
--
-- 처음 한 번은 지우지 않고 대상 건수만 세어 볼 수 있다:
--   POST /api/v1/jobs/once/PRIVACY_RETENTION_JOB   body {"dry_run": true}
-- ============================================================================

INSERT INTO stock.batch_job_master
    (job_id, job_name, module_name, class_name, cron_minute, cron_hour, cron_day_of_week, enabled_flag)
VALUES
    ('PRIVACY_RETENTION_JOB', '개인정보 보관 기간 파기(양봉)', 'app.batches.jobs.PrivacyRetentionJob',
     'PrivacyRetentionJob', '30', '4', '*', 'Y')
ON DUPLICATE KEY UPDATE
    job_name = VALUES(job_name), module_name = VALUES(module_name), class_name = VALUES(class_name),
    cron_minute = VALUES(cron_minute), cron_hour = VALUES(cron_hour), cron_day_of_week = VALUES(cron_day_of_week);

-- 확인
--   SELECT * FROM stock.batch_job_master WHERE job_id = 'PRIVACY_RETENTION_JOB';
--   실행 후: SELECT * FROM stock.batch_log WHERE batch_code = 'PrivacyRetentionJob' ORDER BY batch_seq DESC LIMIT 5;
-- ============================================================================
