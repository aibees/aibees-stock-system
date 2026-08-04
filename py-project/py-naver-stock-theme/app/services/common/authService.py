"""
AuthService — 이메일 로그인 / 토큰 재발급 / 로그아웃 비즈니스 로직

변경 이력:
    - [수정] emailProcess : 하드코딩 토큰 → 실제 JWT + refreshToken 발급
    - [수정] emailProcess : role 필드를 문자열 리스트로 변환 (명세 포맷 준수)
    - [신규] _issue_token_pair : accessToken / refreshToken 쌍 생성 공통 메서드
    - [신규] refreshProcess    : refreshToken 검증 후 토큰 쌍 재발급 (Rotation 포함)
    - [신규] logoutProcess     : refreshToken 단건 서버 측 폐기
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT 패키지 (pyproject.toml에 PyJWT = "^2.8.0" 추가됨)

from stock_shared.dao.userMasterDao import UserMasterDao
from app.domains.dao.userRefreshTokenDao import UserRefreshTokenDao  # [신규] refreshToken DAO
from app.exceptions import ResetRequiredException  # 단일 출처 임포트 — 이 파일에서 직접 정의하지 않음


# ── JWT 서명 시크릿 ──────────────────────────────────────────────────
# 환경변수 JWT_SECRET_KEY 에서 읽어옴.
# ⚠️ 프로덕션에서는 반드시 충분한 엔트로피의 실제 시크릿으로 교체해야 함.
#    예: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'CHANGE_THIS_TO_A_STRONG_SECRET_IN_PRODUCTION')
JWT_ALGORITHM = 'HS256'  # 명세 허용 알고리즘: HS256 또는 RS256

# ── 만료 시간 설정 ───────────────────────────────────────────────────
# 명세: accessToken 30분 이내 / refreshToken 7~30일
ACCESS_TOKEN_EXPIRE_MINUTES = 30   # accessToken 유효기간 (분)
REFRESH_TOKEN_EXPIRE_DAYS   = 1   # refreshToken 유효기간 (일) — 7~30일 범위 내


class AuthService:
    def __init__(self):
        self.name = 'AuthService'
        self.userMasterDaoImpl    = UserMasterDao()
        self.refreshTokenDaoImpl  = UserRefreshTokenDao()

    # ────────────────────────────────────────────────────────────────
    # oAuth 로그인 (카카오 등) — 기존 로직 유지
    # ────────────────────────────────────────────────────────────────
    def oAuthProcess(self, session, data):
        user_param = data['data']
        param = {
            'type': data['type'],
            'user_phone': user_param['mobile']
        }
        user_data = self.userMasterDaoImpl.select_user_by_phone(session, param)
        if user_data is None:
            return dict()
        return user_data

    # ────────────────────────────────────────────────────────────────
    # [수정] 이메일 로그인
    # ────────────────────────────────────────────────────────────────
    def emailProcess(self, session, data):
        """
        이메일 + 비밀번호 검증 후 accessToken / refreshToken 쌍을 발급.

        변경사항:
            1. accessToken을 실제 JWT(HS256, exp 포함)로 교체
               → 기존 하드코딩 더미 문자열 제거
            2. refreshToken을 DB에 저장해 서버 측 폐기 가능하도록 변경
            3. role 필드를 ['USER', 'ADMIN'] 형태의 문자열 리스트로 변환
               → 프론트엔드 명세가 요구하는 포맷과 일치
        """
        # ── 1. 사용자 존재 여부 확인 ──────────────────────────────────
        user_email = data['email']
        param = {
            'type': 'EMAIL',
            'email': user_email
        }
        user_data = self.userMasterDaoImpl.select_user_authinfo(session, param)

        if len(user_data) != 1:
            raise Exception("사용자를 찾을 수 없습니다.")

        user_info = user_data[0]

        # ── 1.5. 비밀번호 초기화 대상 여부 확인 ──────────────────────────
        # reset_flag == 'Y' 이면 인증 프로세스를 중단하고 전용 예외를 발생시킴.
        # 라우터가 이를 catch해 프론트엔드에 RESET_REQUIRED 응답을 반환함.
        if user_info.get('reset_flag') == 'Y':
            print(f'{user_email}은 비밀번호 초기화 대상', flush=True)

            raise ResetRequiredException()


        # ── 2. 비밀번호 일치 여부 확인 ────────────────────────────────
        # salt + pswd 를 SHA-256 해싱해 저장된 해시와 비교
        hashed = hashlib.sha256(
            bytes(user_info['salt'], 'utf-8') + data['pswd'].encode()
        ).hexdigest()

        if hashed != user_info['pswd']:
            raise Exception("사용자 정보가 불일치합니다.")

        # ── 3. 권한 목록 조회 ──────────────────────────────────────────
        param['user_id'] = user_info['user_id']
        user_role_rows = self.userMasterDaoImpl.select_user_roleinfo(session, param)

        # [수정] role을 문자열 리스트로 변환
        # 기존: [{'auth_id': ..., 'auth_nm': 'USER'}, ...]
        # 변경: ['USER', 'ADMIN', ...]  ← 명세 포맷
        # auth_nm 컬럼 값이 'USER', 'ADMIN' 등 단순 문자열임을 전제로 함.
        # DB 값이 다를 경우 아래 키를 auth_id 등으로 교체할 것.
        role_list = [row['auth_nm'] for row in user_role_rows]

        login_info = {
            'user_id': str(user_info['user_id']),  # 명세가 문자열("1") 형태로 정의
            'user_name': user_info['user_name'],
            'role': role_list
        }

        # ── 4. 토큰 쌍 발급 ────────────────────────────────────────────
        # [신규] 공통 토큰 발급 메서드 호출
        token_pair = self._issue_token_pair(session, user_info['user_id'])

        return {
            'accessToken':  token_pair['accessToken'],
            'refreshToken': token_pair['refreshToken'],
            'loginInfo':    login_info
        }

    # ────────────────────────────────────────────────────────────────
    # [신규] 토큰 재발급 (Silent Refresh)
    # ────────────────────────────────────────────────────────────────
    def refreshProcess(self, session, data):
        """
        기존 refreshToken을 검증하고 새 accessToken + refreshToken 쌍을 반환.

        Rotation 전략:
            ① 기존 토큰 조회 → 없으면 401
            ② is_revoked == True (이미 폐기됨) → 재사용 감지!
               → 해당 user_id 의 모든 세션 강제 폐기 후 401
            ③ 만료(expires_at < now) → 401
            ④ 검증 통과 → 기존 토큰 폐기 + 새 토큰 쌍 발급

        Raises:
            Exception: 검증 실패 시 (호출자가 401 응답으로 변환)
        """
        incoming_token = data.get('refreshToken')
        if not incoming_token:
            raise Exception("refreshToken이 없습니다.")

        # ── ① DB에서 토큰 조회 ────────────────────────────────────────
        token_row = self.refreshTokenDaoImpl.find_by_token(session, incoming_token)
        if token_row is None:
            # DB에 존재하지 않는 토큰 → 위조 또는 이미 삭제된 토큰
            raise Exception("유효하지 않은 refreshToken입니다.")

        # ── ② 재사용 감지 (Rotation Detection) ───────────────────────
        # 이미 폐기된 토큰으로 /refresh 를 시도하는 경우:
        # 정상적인 클라이언트라면 폐기된 토큰을 보내지 않으므로
        # 토큰 탈취 후 재사용 시도로 간주, 해당 사용자 전체 세션 강제 만료
        if token_row.is_revoked:
            self.refreshTokenDaoImpl.revoke_all_by_user(session, token_row.user_id)
            raise Exception("이미 사용된 refreshToken입니다. 보안을 위해 모든 세션이 종료되었습니다.")

        # ── ③ 만료 확인 ───────────────────────────────────────────────
        # DB 저장 시각은 UTC datetime이므로 UTC 기준으로 비교
        if token_row.expires_at < datetime.utcnow():
            raise Exception("refreshToken이 만료되었습니다.")

        # ── ④ 기존 토큰 폐기 + 새 토큰 쌍 발급 ─────────────────────────
        # Rotation: 사용된 토큰을 즉시 무효화해 재사용을 원천 차단
        self.refreshTokenDaoImpl.revoke_token(session, incoming_token)
        new_token_pair = self._issue_token_pair(session, token_row.user_id)

        return {
            'accessToken':  new_token_pair['accessToken'],
            'refreshToken': new_token_pair['refreshToken']
        }

    # ────────────────────────────────────────────────────────────────
    # [신규] 로그아웃 — 서버 측 refreshToken 폐기
    # ────────────────────────────────────────────────────────────────
    def logoutProcess(self, session, data):
        """
        클라이언트가 보낸 refreshToken을 DB에서 폐기(is_revoked = True)해
        서버 측에서도 세션을 종료함.

        클라이언트가 이후 동일 refreshToken으로 /refresh 를 시도하면
        재사용 감지 로직이 작동해 모든 세션이 강제 만료됨.
        → 토큰 탈취 후 로그아웃을 우회하려는 시도를 차단
        """
        refresh_token = data.get('refreshToken')
        if refresh_token:
            # 토큰이 DB에 없어도 에러를 반환하지 않음
            # (이미 만료·폐기된 토큰으로 로그아웃 요청해도 정상 처리)
            self.refreshTokenDaoImpl.revoke_token(session, refresh_token)
        return None  # 명세: Response { "success": true, "data": null }

    # ────────────────────────────────────────────────────────────────
    # [신규] 비밀번호 재설정
    # ────────────────────────────────────────────────────────────────
    def resetPasswordProcess(self, session, data):
        """
        reset_flag == 'Y' 인 계정의 비밀번호를 새 값으로 교체.

        처리 순서:
            1. 이메일로 user_id 조회 → 없으면 예외
            2. user_detail 조회 → reset_flag != 'Y' 이면 재설정 대상이 아님으로 예외
            3. 새 salt(16자) 생성 + 새 비밀번호 SHA-256 해싱
            4. user_detail 업데이트 (salt, pswd, reset_flag='N', err_cnt=0, updated_date)
            5. 해당 사용자의 모든 refreshToken 폐기 (기존 세션 무효화)

        Args:
            session: SQLAlchemy 세션
            data   : { "email": str, "new_password": str }

        Returns:
            None  →  라우터에서 { "success": true, "data": null } 로 응답
        """
        email        = data.get('email', '').strip()
        new_password = data.get('new_password', '')

        if not email or not new_password:
            raise Exception("email 과 new_password 는 필수 항목입니다.")

        # ── 1. 이메일로 user_id 조회 ──────────────────────────────────
        user_id = self.userMasterDaoImpl.select_user_id_by_email(session, email)
        if user_id is None:
            raise Exception("존재하지 않는 사용자입니다.")

        # ── 2. reset_flag 확인 ────────────────────────────────────────
        # select_user_authinfo 를 재활용해 user_detail 까지 한 번에 조회
        param = {'type': 'EMAIL', 'email': email}
        user_data = self.userMasterDaoImpl.select_user_authinfo(session, param)

        if not user_data:
            raise Exception("인증 정보를 찾을 수 없습니다.")

        userInfo = user_data[0]
        if userInfo.get('reset_flag') != 'Y':
            raise Exception("비밀번호 재설정 대상 계정이 아닙니다.")

        # ── 3. 새 salt + 해시 생성 ────────────────────────────────────
        # salt: 16자 hex 문자열 (user_detail.salt VARCHAR(16) 에 맞춤)
        new_salt = secrets.token_hex(8)          # 8 bytes → 16 hex chars
        new_pswd_hash = hashlib.sha256(
            new_salt.encode() + new_password.encode()
        ).hexdigest()

        # ── 4. DB 업데이트 ────────────────────────────────────────────
        self.userMasterDaoImpl.update_user_password(
            session,
            user_id=user_id,
            new_salt=new_salt,
            new_pswd=new_pswd_hash
        )

        # ── 5. 기존 refreshToken 전체 폐기 ───────────────────────────
        # 비밀번호 변경 후에도 이전 토큰으로 세션이 유지되지 않도록 강제 만료
        self.refreshTokenDaoImpl.revoke_all_by_user(session, user_id)

        return None  # 명세: Response { "success": true, "data": null }

    # ────────────────────────────────────────────────────────────────
    # [신규] 공통 토큰 쌍 발급 내부 메서드
    # ────────────────────────────────────────────────────────────────
    def _issue_token_pair(self, session, user_id: int) -> dict:
        """
        accessToken(JWT) + refreshToken(불투명 토큰) 쌍을 생성하고
        refreshToken을 DB에 저장한 후 두 값을 딕셔너리로 반환.

        accessToken 설계:
            - 표준 JWT 형식 (header.payload.signature)
            - payload에 sub(사용자 ID), exp(만료 Unix 타임스탬프) 포함
            - HS256 서명 / 환경변수 JWT_SECRET_KEY 사용
            - 프론트엔드가 exp를 base64 디코딩해 만료 시각 계산

        refreshToken 설계:
            - secrets.token_urlsafe(64) 로 생성한 불투명 문자열
            - DB에 저장해 서버 측 폐기(revoke) 가능
            - REFRESH_TOKEN_EXPIRE_DAYS(14일) 후 만료
        """
        now = datetime.now(tz=timezone.utc)

        # ── accessToken 생성 ─────────────────────────────────────────
        access_exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_payload = {
            'sub': str(user_id),   # 토큰 주체 (Subject) — 사용자 식별자
            'exp': access_exp,     # 만료 시각 (PyJWT가 Unix 타임스탬프로 자동 변환)
            'iat': now,            # 발급 시각 (Issued At)
        }
        access_token = jwt.encode(
            access_payload,
            JWT_SECRET,
            algorithm=JWT_ALGORITHM
        )
        # PyJWT >= 2.x 는 encode() 가 str 을 반환하므로 별도 decode 불필요

        # ── refreshToken 생성 ────────────────────────────────────────
        # token_urlsafe(64) → 512 비트 엔트로피의 URL-safe Base64 문자열
        # 불투명 토큰이므로 JWT가 아닌 순수 랜덤값 사용
        refresh_token_str  = secrets.token_urlsafe(64)
        refresh_expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        # DB에 저장 — 이후 /refresh 에서 조회·검증·폐기에 활용됨
        self.refreshTokenDaoImpl.insert_token(
            session,
            user_id=user_id,
            token=refresh_token_str,
            expires_at=refresh_expires_at
        )

        return {
            'accessToken':  access_token,
            'refreshToken': refresh_token_str
        }
