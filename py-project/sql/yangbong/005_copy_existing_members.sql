-- ============================================================================
-- yangbong/005_copy_existing_members.sql  (2026-11-15)
--
-- 기존 회원을 양봉상회에도 가입된 상태로 둔다(2026-11-15 결정 — 기존 스토어 앱은 양봉상회가 이어받는다).
--   2026-11-15 기준 `stock` 회원 9명 전원. user_id 는 그대로 쓴다(양봉상회 신규 가입은 그 다음 번호부터).
--   두 스키마의 user_id 가 같은 숫자여도 JWT 비밀값이 서로 달라 토큰이 섞이지 않는다(001 머리말).
--
-- 옮기는 것
--   user_master          : 이름·이메일 등 그대로
--   user_detail          : 로그인용 salt·비밀번호 해시·오류 횟수·재설정 여부만.
--                          ⚠ KIS·업비트·텔레그램 키는 옮기지 않는다(NULL) — 양봉상회에는 매매 연동이 없다.
--   user_login_type      : 이메일·네이버·구글·카카오 연결 그대로(같은 소셜 계정으로 로그인)
--   user_consent         : 동의 기록 그대로. 양봉상회 약관 버전이 바뀌면 그때 다시 동의를 받는다.
--   user_auth            : STOCK_USER·ADMIN·AD_FREE_USER 만. 매매(WORKER_USER)·코인(COIN_USER)은 옮기지 않는다.
--                          모든 회원에게 STOCK_USER(일반 회원)를 보장한다.
--   user_interest_*      : 관심종목 그룹·종목. 보유 수량(curr_balance)은 옮기지 않는다.
-- 옮기지 않는 것: 리프레시 토큰(전환 후 한 번 다시 로그인), 푸시 토큰(앱이 다시 등록), user_options(매매 알림 설정), 매매 데이터 전부.
--
-- 실행 시점: 양봉상회 API 로 전환하기 직전에 한 번. 여러 번 실행해도 이미 있는 행은 건너뛴다(INSERT IGNORE)
--   — 다만 그 사이 `stock` 에 새로 생긴 회원(비밀상회 가입자)도 함께 복사되니, 전환 뒤에는 다시 실행하지 않는다.
-- 관리자 계정으로 실행(001~004 다음).
--
-- 확인:
--   SELECT COUNT(*) FROM yangbong.user_master;                                        -- 9
--   SELECT COUNT(*) FROM yangbong.user_detail WHERE kis_app_key IS NOT NULL OR kis_access_key IS NOT NULL
--       OR upbit_access_key IS NOT NULL OR tele_bot_id IS NOT NULL;                    -- 0 이어야 한다
--   SELECT auth_id, COUNT(*) FROM yangbong.user_auth GROUP BY auth_id;
-- 되돌리기: 해당 user_id 행을 위 테이블들에서 지운다(양봉상회 신규 가입자가 생기기 전이면 TRUNCATE 해도 된다).
-- ============================================================================

INSERT IGNORE INTO yangbong.user_master (user_id, user_name, user_phone, email, gender, age)
    SELECT user_id, user_name, user_phone, email, gender, age FROM stock.user_master;

INSERT IGNORE INTO yangbong.user_detail (user_id, salt, pswd, err_cnt, reset_flag, created_date, updated_date)
    SELECT user_id, salt, pswd, err_cnt, reset_flag, created_date, updated_date FROM stock.user_detail;

INSERT IGNORE INTO yangbong.user_login_type (user_id, login_type, enabled_flag, provider_uid, linked_date)
    SELECT user_id, login_type, enabled_flag, provider_uid, linked_date FROM stock.user_login_type;

INSERT IGNORE INTO yangbong.user_consent (user_id, consent_type, version, agreed_date)
    SELECT user_id, consent_type, version, agreed_date FROM stock.user_consent;

INSERT IGNORE INTO yangbong.user_auth (user_id, auth_id, enabled_flag, created_date, updated_date)
    SELECT user_id, auth_id, enabled_flag, created_date, updated_date FROM stock.user_auth
    WHERE auth_id IN ('STOCK_USER', 'ADMIN', 'AD_FREE_USER');

-- 모든 회원에게 일반 회원 권한(STOCK_USER 가 원래 없던 매매 전용 회원 포함)
INSERT IGNORE INTO yangbong.user_auth (user_id, auth_id, enabled_flag, created_date, updated_date)
    SELECT user_id, 'STOCK_USER', 'Y', NOW(), NOW() FROM stock.user_master;

INSERT IGNORE INTO yangbong.user_interest_groups (division, group_id, user_id, group_name)
    SELECT division, group_id, user_id, group_name FROM stock.user_interest_groups;

INSERT IGNORE INTO yangbong.user_interest_stocks (group_id, stock_code, status, added_at, enabled_flag, curr_balance)
    SELECT group_id, stock_code, status, added_at, enabled_flag, NULL FROM stock.user_interest_stocks;
