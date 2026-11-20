-- ============================================================================
-- yangbong/009_login_id.sql  (2026-11-20, 2026-11-21 user_master.login_id 로 변경)
--
-- 이메일 로그인 → 아이디 로그인. user_master 에 login_id 열을 추가하고,
-- 기존 회원의 아이디 = 이메일 @ 앞부분(소문자)으로 채운다.
--
--   - login_id 는 UNIQUE — 중복을 DB 가 막는다. NULL 은 여러 개 가능(아이디 없는 회원).
--   - 이메일(email)은 연락·인증용으로 그대로 남는다. 아이디와 이메일은 따로 바뀔 수 있다.
--   - 아이디 로그인은 user_login_type 에 EMAIL(비밀번호 로그인) 행이 켜져 있는 회원만 된다.
--     소셜(네이버·구글·Apple)로만 가입한 회원도 아이디는 채워 두지만, 비밀번호가 없어 소셜로 로그인한다.
--   - 공용 모델(stock_shared UserMaster)에 login_id 가 생기므로 stock.user_master 에도 같은 열이 있어야 한다
--     → sql/stock/005_user_master_login_id.sql (비밀상회·배치는 쓰지 않는 빈 열).
--
-- 적용 순서: 이 SQL + stock/005 → 서버 배포(양봉상회 API·비밀상회 API·배치). 열 추가는 옛 코드에 영향이 없다.
--   서버를 먼저 배포하면 user_master 조회가 'Unknown column login_id' 로 실패하니 반드시 SQL 먼저.
-- 관리자 계정으로 실행. ①은 한 번만 실행한다(다시 실행하면 'Duplicate column' 오류 — 그 경우 ①만 빼고 실행).
-- ③은 여러 번 실행해도 된다(아이디가 이미 있는 회원은 건너뜀).
-- ============================================================================

-- ① 열 추가
ALTER TABLE yangbong.user_master
    ADD COLUMN login_id VARCHAR(20) NULL COMMENT '로그인 아이디(4~20자 영문 소문자·숫자·._-)' AFTER user_id,
    ADD UNIQUE KEY uq_user_master_login_id (login_id);

-- ② 채우기 전 확인 — 둘 다 0행이어야 한다(2026-11-21 기준 회원 9명 모두 0행)
--    겹치는 아이디: 있으면 ③이 UNIQUE 에서 실패한다 → 그 회원은 ④로 따로 정한다.
--    (별칭을 login_id 로 쓰면 ①에서 생긴 진짜 login_id 열로 묶여 1055 오류 — 표현식으로 묶는다)
SELECT LOWER(SUBSTRING_INDEX(email, '@', 1)) AS new_login_id, GROUP_CONCAT(user_id) AS user_ids
  FROM yangbong.user_master
 WHERE email LIKE '%@%'
 GROUP BY LOWER(SUBSTRING_INDEX(email, '@', 1))
HAVING COUNT(*) > 1;
--    아이디 규칙에 안 맞는 앞부분: 로그인은 되지만 새로 정하는 아이디는 규칙을 따르므로 ④로 바꿔 주는 편이 낫다.
SELECT user_id, email
  FROM yangbong.user_master
 WHERE email LIKE '%@%'
   AND LOWER(SUBSTRING_INDEX(email, '@', 1)) NOT REGEXP '^[a-z0-9][a-z0-9._-]{3,19}$';

-- ③ 기존 회원 전환: 이메일 @ 앞부분
UPDATE yangbong.user_master
   SET login_id = LOWER(SUBSTRING_INDEX(email, '@', 1))
 WHERE login_id IS NULL
   AND email LIKE '%@%'
   AND CHAR_LENGTH(SUBSTRING_INDEX(email, '@', 1)) <= 20;

-- ④ (필요할 때만) 한 회원의 아이디를 직접 정하기
-- UPDATE yangbong.user_master SET login_id = '새아이디' WHERE user_id = ?;

-- 확인: 9명 모두 아이디가 있어야 한다. email_login = 'Y' 인 회원만 아이디로 로그인할 수 있다(1~6번).
SELECT m.user_id, m.login_id, m.email,
       IF(t.user_id IS NULL, 'N', 'Y') AS email_login
  FROM yangbong.user_master m
  LEFT JOIN yangbong.user_login_type t
         ON t.user_id = m.user_id AND t.login_type = 'EMAIL' AND t.enabled_flag = 'Y'
 ORDER BY m.user_id;
-- ============================================================================
