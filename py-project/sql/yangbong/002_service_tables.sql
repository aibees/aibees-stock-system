-- ============================================================================
-- yangbong/002_service_tables.sql  (2026-11-15)
--
-- 양봉상회 회원·서비스 테이블. 데이터는 비어 있는 채로 시작한다(비밀상회 회원 9명은 옮기지 않는다 —
-- 2026-11-15 기준 전원 STOCK/WORKER/ADMIN 권한 = 비밀상회 고객).
--
-- 기존 테이블은 `stock` 과 같은 구조로 만든다(CREATE TABLE … LIKE): 로그인·가입·동의·공지·권한 코드를
-- 고치지 않고 DB_URL 만 바꿔 그대로 쓰기 위해서다. 구조가 같으므로 `stock` 쪽 테이블을 바꾸는 SQL 이
-- 생기면 여기에도 같은 변경을 넣어야 한다.
--   - user_detail 에는 로그인용 salt·비밀번호 해시만 쓴다. KIS·텔레그램 칸은 비워 둔다(매매 기능 없음).
--   - user_options 는 기존 개인설정 화면(/user-options) 호환용. 매매 관련 칸은 쓰지 않는다.
--
-- 쓰기 권한은 여기 테이블마다 준다(001: 스키마 전체는 SELECT 만). 테이블을 새로 만들면 GRANT 도 같이 넣는다.
--
-- 확인: SHOW TABLES FROM yangbong;  SHOW GRANTS FOR 'yangbong'@'%';
-- ============================================================================

-- ── 회원·인증 ──
CREATE TABLE IF NOT EXISTS yangbong.user_master        LIKE stock.user_master;
CREATE TABLE IF NOT EXISTS yangbong.user_detail        LIKE stock.user_detail;
CREATE TABLE IF NOT EXISTS yangbong.user_login_type    LIKE stock.user_login_type;
CREATE TABLE IF NOT EXISTS yangbong.user_auth          LIKE stock.user_auth;
CREATE TABLE IF NOT EXISTS yangbong.user_role          LIKE stock.user_role;
CREATE TABLE IF NOT EXISTS yangbong.user_consent       LIKE stock.user_consent;
CREATE TABLE IF NOT EXISTS yangbong.user_refresh_token LIKE stock.user_refresh_token;
CREATE TABLE IF NOT EXISTS yangbong.user_options       LIKE stock.user_options;

-- ── 기록·알림 ──
CREATE TABLE IF NOT EXISTS yangbong.user_login_log       LIKE stock.user_login_log;
CREATE TABLE IF NOT EXISTS yangbong.user_menu_access_log LIKE stock.user_menu_access_log;
CREATE TABLE IF NOT EXISTS yangbong.device_push_token    LIKE stock.device_push_token;

-- ── 화면 구성·설정 ──
--   master_menu/role_menu/role_feature : 양봉상회 화면 목록과 권한(004 에서 공개 메뉴만 넣는다)
--   master_codes : 양봉상회 설정값(광고·화면·성향 PERSONA_CONFIG). 배치 설정은 `stock` 에 남는다
--   master_infos : 로그인·메일 키(NAVER_AUTH / GOOGLE_AUTH / SMTP)만. KIS 키는 넣지 않는다
--   notice       : 양봉상회 공지(비밀상회 공지와 따로)
CREATE TABLE IF NOT EXISTS yangbong.master_menu  LIKE stock.master_menu;
CREATE TABLE IF NOT EXISTS yangbong.role_menu    LIKE stock.role_menu;
CREATE TABLE IF NOT EXISTS yangbong.role_feature LIKE stock.role_feature;
CREATE TABLE IF NOT EXISTS yangbong.master_codes LIKE stock.master_codes;
CREATE TABLE IF NOT EXISTS yangbong.master_infos LIKE stock.master_infos;
CREATE TABLE IF NOT EXISTS yangbong.notice       LIKE stock.notice;

-- ── 관심종목(양봉상회 '내 것' 탭) — 비밀상회 관심종목과 데이터는 따로 ──
CREATE TABLE IF NOT EXISTS yangbong.user_interest_groups LIKE stock.user_interest_groups;
CREATE TABLE IF NOT EXISTS yangbong.user_interest_stocks LIKE stock.user_interest_stocks;

-- ── 종목 AI 분석(기업개요·테마·뉴스) — 2026-11-15 결정: 양봉상회 기능, 비밀상회에서는 뺀다 ──
--   양봉상회 API 가 버튼으로 생성해 저장하고(종목·섹션당 1행, 1시간 재생성 제한) 조회는 캐시만 읽는다.
--   기존 생성분은 004 에서 복사한다. 비밀상회 화면·API 에서 기능을 걷어낸 뒤 stock.stock_ai_content 는 지운다.
CREATE TABLE IF NOT EXISTS yangbong.stock_ai_content LIKE stock.stock_ai_content;

-- ── 성향 테스트 결과(계정 저장) — 기획안 15장 #9 ──
--   persona_type : 성향 유형 key. 값 목록은 데이터(stock-vue personaConfig.json / 공통코드 PERSONA_CONFIG)라 제약하지 않는다.
--   updated_at   : 기기 값과 계정 값 중 최근 것을 고르는 기준이라 API 서버가 직접 넣는다.
CREATE TABLE IF NOT EXISTS yangbong.user_persona (
  user_id       INT          NOT NULL,
  persona_type  VARCHAR(30)  NULL COMMENT '성향 유형 key (stable / balanced / aggressive …)',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '마지막 변경 시각(API 서버가 기록)',
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='성향 테스트 결과(계정 저장)';

-- ── 쓰기 권한(서비스 테이블만) ──
GRANT INSERT, UPDATE, DELETE ON yangbong.user_master          TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_detail          TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_login_type      TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_auth            TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_role            TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_consent         TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_refresh_token   TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_options         TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_login_log       TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_menu_access_log TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.device_push_token    TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.master_menu          TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.role_menu            TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.role_feature         TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.master_codes         TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.master_infos         TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.notice               TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_interest_groups TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_interest_stocks TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.stock_ai_content     TO 'yangbong'@'%';
GRANT INSERT, UPDATE, DELETE ON yangbong.user_persona         TO 'yangbong'@'%';
