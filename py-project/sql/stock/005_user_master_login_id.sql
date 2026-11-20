-- ============================================================================
-- stock/005_user_master_login_id.sql  (2026-11-21)
--
-- stock.user_master 에 login_id 열(빈 값)을 추가한다.
--   양봉상회가 아이디 로그인으로 바뀌며 공용 모델(stock_shared UserMaster)에 login_id 가 생겼다
--   (sql/yangbong/009_login_id.sql). 비밀상회 API·배치도 같은 모델로 stock.user_master 를 읽으므로
--   열이 없으면 'Unknown column login_id' 로 실패한다. 비밀상회는 이 값을 쓰지 않는다(전부 NULL).
--   비밀상회 로그인은 지금처럼 이메일로 된다(서버가 '@' 가 있는 값은 이메일로 찾는다).
--
-- 적용 순서: 이 SQL → 서버 배포. 열 추가만 하므로 지금 돌고 있는 옛 코드에는 영향이 없다.
-- 한 번만 실행한다(다시 실행하면 'Duplicate column' 오류).
-- ============================================================================

ALTER TABLE stock.user_master
    ADD COLUMN login_id VARCHAR(20) NULL COMMENT '로그인 아이디(양봉상회용, 비밀상회는 미사용)' AFTER user_id,
    ADD UNIQUE KEY uq_user_master_login_id (login_id);

-- 확인
--   SHOW COLUMNS FROM stock.user_master LIKE 'login_id';
-- ============================================================================
