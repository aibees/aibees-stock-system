-- ============================================================================
-- yangbong/001_schema_account.sql  (2026-11-15)
--
-- 양봉상회(대중용) 전용 스키마와 DB 계정.
--   2026-11-15 결정: 기존 앱은 private 고객 전용 '비밀상회'(트레이딩 유지, 스키마 `stock`),
--   새 '양봉상회'는 트레이딩 없이(트레이닝 탭 예정) 새 스키마 `yangbong` + 별도 계정으로 분리한다.
--
-- 구성
--   `stock`    : 그대로. 시장 데이터(배치가 씀) + 비밀상회 회원·매매 데이터. 워커·배치·비밀상회 API 가 쓴다.
--   `yangbong` : 양봉상회 회원·서비스 데이터(실제 테이블, 002) + 시장 데이터 읽기 전용 뷰(003).
--   계정 yangbong_api 는 `stock` 에 아무 권한이 없다. 시장 데이터는 뷰(SQL SECURITY DEFINER)로만 읽고,
--   매매 테이블·KIS 키(user_detail, master_infos 의 KIS 항목)·비밀상회 회원에는 닿지 못한다.
--
-- 적용 순서(모두 관리자 계정으로 — 뷰의 DEFINER 가 되므로 `stock` SELECT 권한이 있어야 한다):
--   001_schema_account.sql → 002_service_tables.sql → 003_market_views.sql → 004_seed.sql
--   ⚠ 아래 '<비밀번호>' 를 실제 값으로 바꿔 실행하고, 바꾼 파일은 커밋하지 않는다.
--
-- 양봉상회 API 프로세스 환경변수(비밀상회 API 와 반드시 달라야 하는 것):
--   DB_URL          = mysql+pymysql://yangbong_api:<비밀번호>@<호스트>:<포트>/yangbong
--   JWT_SECRET_KEY  = 비밀상회와 다른 값. 같으면 양봉상회 user_id=1 토큰이 비밀상회에서 user_id=1(관리자)로 통한다.
--                     (두 스키마의 user_id 는 각자 1 부터 매겨진다)
--   DB_POOL_SIZE=2, DB_MAX_OVERFLOW=3  → gunicorn 워커 수 × 5 가 아래 MAX_USER_CONNECTIONS 를 넘지 않게.
--
-- 연결 수 상한: DB 서버 max_connections 50(2026-11-12 실측). 양봉상회 계정을 15 로 묶어
--   대중 트래픽이 몰려도 워커·배치·비밀상회 연결(나머지 35)은 남는다. 넘치면 양봉상회만 실패한다.
--
-- 확인: SHOW GRANTS FOR 'yangbong_api'@'%';
-- 되돌리기: DROP USER 'yangbong_api'@'%'; DROP DATABASE yangbong;   -- 양봉상회 회원 데이터가 모두 사라진다
-- ============================================================================

CREATE DATABASE IF NOT EXISTS yangbong DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

-- 접속 호스트는 API 가 붙는 위치로 좁힐 수 있으면 좁힌다('%' = 어디서나).
CREATE USER IF NOT EXISTS 'yangbong'@'%' IDENTIFIED BY '<비밀번호>';
ALTER USER 'yangbong'@'%' WITH MAX_USER_CONNECTIONS 15;

-- 읽기는 스키마 전체(서비스 테이블 + 시장 데이터 뷰). 쓰기 권한은 002 에서 서비스 테이블마다 따로 준다
-- — 스키마 단위로 주면 단일 테이블 뷰가 '갱신 가능한 뷰'라서 뷰를 통해 `stock` 시장 데이터를 고칠 수 있게 된다.
GRANT SELECT ON yangbong.* TO 'yangbong'@'%';
