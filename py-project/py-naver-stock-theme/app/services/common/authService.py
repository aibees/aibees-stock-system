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
import re
import hmac
import time
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT 패키지 (pyproject.toml에 PyJWT = "^2.8.0" 추가됨)

from stock_shared.dao.userMasterDao import UserMasterDao
from app.domains.dao.userRefreshTokenDao import UserRefreshTokenDao  # [신규] refreshToken DAO
from app.exceptions import ResetRequiredException  # 단일 출처 임포트 — 이 파일에서 직접 정의하지 않음
from app.domains.dao.masterInfoDao import MasterInfosDao
from app.domains.dao.socialLoginDao import SocialLoginDao
from app.utils import mailer

import requests


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

# ── 네이버 로그인 ─────────────────────────────────────────────────────
NAVER = 'NAVER'                                   # user_login_type.login_type 값
DEFAULT_SIGNUP_ROLE = 'STOCK_USER'                # 네이버로 신규 가입한 사용자의 기본 권한
NAVER_TOKEN_URL = 'https://nid.naver.com/oauth2.0/token'
NAVER_PROFILE_URL = 'https://openapi.naver.com/v1/nid/me'

# ── 가입 동의 (이용약관 / 개인정보 수집·이용 / 만 14세 이상) — 항목별로 따로 받아 따로 기록한다 ──
# 버전은 프런트(stock-vue src/scripts/termsOfService.js, privacyPolicy.js)와 같아야 한다.
# 문구를 고치면 양쪽 버전을 함께 올린다 → 다음 네이버 로그인 때 재동의를 받는다.
CONSENT_PRIVACY = 'PRIVACY'                        # user_consent.consent_type 값
CONSENT_TERMS = 'TERMS'
CONSENT_AGE14 = 'AGE14'
PRIVACY_POLICY_VERSION = '2026-10-10.2'   # .2: 휴대전화번호 수집 항목 삭제 (프런트 privacyPolicy.js 와 같아야 함)
TERMS_VERSION = '2026-10-10'              # 프런트 termsOfService.js 와 같아야 함
AGE14_VERSION = '1'
# 로그인에 필요한 동의 {consent_type: 현재 버전}
REQUIRED_CONSENTS = {CONSENT_TERMS: TERMS_VERSION, CONSENT_PRIVACY: PRIVACY_POLICY_VERSION, CONSENT_AGE14: AGE14_VERSION}
# 동의 화면용 임시 토큰. accessToken 과 다른 키로 서명해 require_auth 를 통과하지 못하게 한다.
CONSENT_TOKEN_SECRET = JWT_SECRET + ':naver-consent'
CONSENT_TOKEN_EXPIRE_MINUTES = 10


# ── 이메일 회원가입 (인증코드) ─────────────────────────────────────────
EMAIL = 'EMAIL'
# 인증코드 토큰: DB 테이블 없이 서명 토큰에 "이메일 + 코드의 HMAC" 을 담아 돌려준다(코드 자체는 메일로만 간다).
SIGNUP_TOKEN_SECRET = JWT_SECRET + ':email-signup'
SIGNUP_CODE_EXPIRE_MINUTES = 10
SIGNUP_CODE_MAX_ATTEMPTS = 5        # 토큰 1개당 틀릴 수 있는 횟수
SIGNUP_CODE_RESEND_SECONDS = 60     # 같은 이메일로 다시 보내기까지 대기
EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# 비밀번호 규칙: 비밀번호 재설정 화면(Login.vue PASSWORD_REGEX)과 같다 — 8자 이상, 대/소문자·숫자·특수문자 각 1자 이상
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')
# 시도 횟수·재발송 시각·사용 완료 토큰은 프로세스 메모리에 둔다(워커가 여럿이면 워커별 — 코드 공간 10^6 대비 무시 가능).
_signup_attempts = {}   # {jti: (틀린 횟수, 기록 시각)}
_signup_sent_at = {}    # {email: 보낸 시각}
_signup_used = {}       # {jti: 사용 시각}


def _prune_signup_state(now: float) -> None:
    ttl = SIGNUP_CODE_EXPIRE_MINUTES * 60 + 60
    for d in (_signup_sent_at, _signup_used):
        for k in [k for k, t in d.items() if now - t > ttl]:
            d.pop(k, None)
    for k in [k for k, (_, t) in _signup_attempts.items() if now - t > ttl]:
        _signup_attempts.pop(k, None)


def _code_mac(jti: str, code: str) -> str:
    return hmac.new(SIGNUP_TOKEN_SECRET.encode(), f'{jti}:{code}'.encode(), hashlib.sha256).hexdigest()


class NaverLoginError(Exception):
    """사용자에게 그대로 보여줄 수 있는 네이버 로그인 실패 사유."""


class SignupError(Exception):
    """사용자에게 그대로 보여줄 수 있는 회원가입 실패 사유."""


def _check_consents(data: dict, error_cls) -> None:
    """가입 동의 3항목이 모두 체크됐고, 화면이 보여준 문구가 현재 버전인지 확인."""
    if data.get('agreeAge14') is not True:
        raise error_cls("만 14세 이상만 가입할 수 있어요.")
    if data.get('agreeTerms') is not True:
        raise error_cls("이용약관에 동의해야 가입할 수 있어요.")
    if data.get('agreePrivacy') is not True:
        raise error_cls("개인정보 수집·이용에 동의해야 가입할 수 있어요.")
    if data.get('termsVersion') != TERMS_VERSION or data.get('policyVersion') != PRIVACY_POLICY_VERSION:
        # 화면이 오래된 문구를 보여준 경우 — 새로 받은 문구로 다시 동의받는다
        raise error_cls("약관 또는 개인정보 처리방침이 변경됐어요. 화면을 새로고침한 뒤 다시 시도해 주세요.")


class AuthService:
    def __init__(self):
        self.name = 'AuthService'
        self.userMasterDaoImpl    = UserMasterDao()
        self.refreshTokenDaoImpl  = UserRefreshTokenDao()
        self.socialLoginDaoImpl   = SocialLoginDao()
        self.masterInfosDaoImpl   = MasterInfosDao()

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
        print(param)
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
        # ── 4. 권한 + 토큰 쌍 발급 (네이버 로그인과 공통) ────────────────
        return self._login_result(session, user_info['user_id'], user_info['user_name'])

    def _login_result(self, session, user_id, user_name):
        """로그인 성공 응답: 권한 목록 + accessToken/refreshToken. 이메일·네이버 로그인 공통."""
        user_role_rows = self.userMasterDaoImpl.select_user_roleinfo(session, {'user_id': user_id})

        # role 은 문자열 리스트(명세 포맷). auth_nm 값을 쓴다.
        role_list = [row['auth_nm'] for row in user_role_rows]

        login_info = {
            'user_id': str(user_id),  # 명세가 문자열("1") 형태로 정의
            'user_name': user_name,
            'role': role_list
        }

        token_pair = self._issue_token_pair(session, user_id)

        return {
            'accessToken':  token_pair['accessToken'],
            'refreshToken': token_pair['refreshToken'],
            'loginInfo':    login_info
        }

    # ────────────────────────────────────────────────────────────────
    # 네이버 로그인 (최초 로그인 시 이메일로 기존 계정 자동 연결 / 없으면 신규 가입)
    # ────────────────────────────────────────────────────────────────
    def naverProcess(self, session, data):
        """
        프런트는 네이버 인가 후 받은 code/state 만 보낸다. 사용자 정보는 서버가 네이버에서 직접 받는다
        (클라이언트가 보낸 이메일·전화번호를 믿지 않는다).

        계정 결정 순서:
            ① 이 네이버 고유 ID 가 이미 연결된 사용자 → 그 사용자로 로그인
            ② 네이버가 준 이메일과 user_master.email 이 정확히 1명 일치 → 그 사용자에 연결 후 로그인
            ③ 일치하는 사용자가 없음 → 신규 가입(기본 권한 STOCK_USER) 후 로그인
        반환: 이메일 로그인과 같은 형식 + 'naverResult': 'login' | 'linked' | 'created'
              단, 현재 처리방침 동의가 없으면 토큰 대신 consentRequired/consentToken (→ _naver_result)
        Raises: NaverLoginError(사용자에게 보여줄 메시지)
        """
        code, state = (data or {}).get('code'), (data or {}).get('state')
        if not code or not state:
            raise NaverLoginError("네이버 인증 정보가 없습니다. 다시 시도해 주세요.")

        profile = self._naver_profile(session, code, state)
        naver_id = profile.get('id')
        email = (profile.get('email') or '').strip()
        if not naver_id:
            raise NaverLoginError("네이버 사용자 정보를 받지 못했습니다.")

        dao = self.socialLoginDaoImpl

        # ① 이미 연결된 네이버 계정
        row = dao.select_by_provider_uid(session, NAVER, naver_id)
        if row is not None:
            if row.enabled_flag != 'Y':
                raise NaverLoginError("네이버 로그인이 비활성화된 계정입니다. 관리자에게 문의해 주세요.")
            user = dao.select_user(session, row.user_id)
            return self._naver_result(session, user.user_id, user.user_name, 'login')

        if not email:
            raise NaverLoginError("네이버 이메일 제공에 동의해야 로그인할 수 있어요.")

        # ② 이메일이 같은 기존 사용자에 자동 연결
        matches = dao.select_users_by_email(session, email)
        if len(matches) > 1:
            raise NaverLoginError("같은 이메일의 계정이 여러 개라 자동 연결할 수 없습니다. 관리자에게 문의해 주세요.")
        if len(matches) == 1:
            user = matches[0]
            existing = dao.select_login_type(session, user.user_id, NAVER)
            if existing is not None and existing.enabled_flag != 'Y':
                raise NaverLoginError("네이버 로그인이 비활성화된 계정입니다. 관리자에게 문의해 주세요.")
            if existing is not None and existing.provider_uid and existing.provider_uid != naver_id:
                raise NaverLoginError("이 계정에는 다른 네이버 계정이 이미 연결돼 있습니다.")
            dao.link(session, user.user_id, NAVER, naver_id)
            return self._naver_result(session, user.user_id, user.user_name, 'linked')

        # ③ 신규 가입 — 회원정보를 저장한 뒤 개인정보 처리방침 동의 화면으로 보낸다
        name = (profile.get('name') or profile.get('nickname') or email.split('@')[0])[:45]
        # 휴대전화번호는 받지 않는다(2026-10-10 처리방침에서 수집 항목 삭제) — 네이버가 mobile 을 줘도 저장하지 않는다.
        new_id = dao.create_user(session, user_name=name, email=email, phone=None,
                                 login_type=NAVER, provider_uid=naver_id, auth_id=DEFAULT_SIGNUP_ROLE)
        return self._naver_result(session, new_id, name, 'created')

    def _naver_result(self, session, user_id, user_name, naver_result):
        """
        네이버 로그인 응답. 현재 버전의 개인정보 처리방침 동의가 있으면 바로 로그인(토큰 발급),
        없으면 토큰 대신 동의 화면용 consentToken 을 준다(→ POST /api/oauth/naver/consent).
        가입 직후뿐 아니라 동의 화면에서 이탈한 사용자·처리방침 개정 후 첫 로그인도 여기서 걸린다.
        """
        if self._has_required_consents(session, user_id):
            return {**self._login_result(session, user_id, user_name), 'naverResult': naver_result}

        now = datetime.now(tz=timezone.utc)
        consent_token = jwt.encode({
            'sub': str(user_id),
            'nres': naver_result,
            'iat': now,
            'exp': now + timedelta(minutes=CONSENT_TOKEN_EXPIRE_MINUTES),
        }, CONSENT_TOKEN_SECRET, algorithm=JWT_ALGORITHM)
        user = self.socialLoginDaoImpl.select_user(session, user_id)
        return {
            'consentRequired': True,
            'consentToken': consent_token,
            'policyVersion': PRIVACY_POLICY_VERSION,
            'termsVersion': TERMS_VERSION,
            'naverResult': naver_result,
            'profile': {'user_name': user_name, 'email': user.email if user else None},
        }

    def naverConsentProcess(self, session, data):
        """
        개인정보 처리방침 동의 → 동의 기록 저장 → 로그인(토큰 발급).

        Request : { "consentToken": "...", "termsVersion": "...", "policyVersion": "...",
                    "agreeAge14": true, "agreeTerms": true, "agreePrivacy": true }
        반환: 이메일 로그인과 같은 형식 + 'naverResult'(네이버 로그인 때 결정된 값)
        Raises: NaverLoginError(사용자에게 보여줄 메시지)
        """
        data = data or {}
        _check_consents(data, NaverLoginError)
        try:
            payload = jwt.decode(data.get('consentToken') or '', CONSENT_TOKEN_SECRET,
                                 algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise NaverLoginError("동의 시간이 지났어요. 네이버로 다시 로그인해 주세요.")
        except jwt.InvalidTokenError:
            raise NaverLoginError("가입 정보가 올바르지 않아요. 네이버로 다시 로그인해 주세요.")

        user_id = int(payload['sub'])
        dao = self.socialLoginDaoImpl
        user = dao.select_user(session, user_id)
        login_type = dao.select_login_type(session, user_id, NAVER)
        if user is None or login_type is None or login_type.enabled_flag != 'Y':
            raise NaverLoginError("가입 정보를 찾을 수 없어요. 네이버로 다시 로그인해 주세요.")

        self._save_required_consents(session, user_id)
        return {**self._login_result(session, user_id, user.user_name),
                'naverResult': payload.get('nres', 'login')}

    def _has_required_consents(self, session, user_id) -> bool:
        dao = self.socialLoginDaoImpl
        for consent_type, version in REQUIRED_CONSENTS.items():
            row = dao.select_consent(session, user_id, consent_type)
            if row is None or row.version != version:
                return False
        return True

    def _save_required_consents(self, session, user_id) -> None:
        for consent_type, version in REQUIRED_CONSENTS.items():
            self.socialLoginDaoImpl.save_consent(session, user_id, consent_type, version)

    # ────────────────────────────────────────────────────────────────
    # 이메일 회원가입: ① 인증코드 메일 발송 → ② 코드 확인 + 가입 + 동의 기록 + 로그인
    # ────────────────────────────────────────────────────────────────
    def signupSendCode(self, session, data):
        """
        Request : { "email": "..." }
        반환    : { "verifyToken": "...", "expiresIn": 600 }
        이미 어떤 방식으로든 가입된 이메일이면 거절한다(네이버 가입자도 포함 — 이메일이 같으면
        네이버 자동 연결 대상이 둘이 되기 때문). 코드는 메일로만 보내고 응답에는 넣지 않는다.
        """
        email = ((data or {}).get('email') or '').strip().lower()
        if not EMAIL_REGEX.match(email) or len(email) > 200:
            raise SignupError("이메일 주소를 확인해 주세요.")
        if self.socialLoginDaoImpl.select_users_by_email(session, email):
            raise SignupError("이미 가입된 이메일이에요. 로그인해 주세요.")

        now = time.time()
        _prune_signup_state(now)
        last = _signup_sent_at.get(email)
        if last and now - last < SIGNUP_CODE_RESEND_SECONDS:
            raise SignupError(f"인증코드는 {SIGNUP_CODE_RESEND_SECONDS}초 뒤에 다시 받을 수 있어요.")

        code = f'{secrets.randbelow(10 ** 6):06d}'
        jti = secrets.token_hex(8)
        exp = datetime.now(tz=timezone.utc) + timedelta(minutes=SIGNUP_CODE_EXPIRE_MINUTES)
        token = jwt.encode({'email': email, 'jti': jti, 'mac': _code_mac(jti, code), 'exp': exp},
                           SIGNUP_TOKEN_SECRET, algorithm=JWT_ALGORITHM)
        try:
            mailer.send(session, email, '[양봉상회] 회원가입 인증코드',
                        f'<p>양봉상회 회원가입 인증코드입니다.</p>'
                        f'<p style="font-size:24px;font-weight:700;letter-spacing:4px">{code}</p>'
                        f'<p>{SIGNUP_CODE_EXPIRE_MINUTES}분 안에 입력해 주세요. 본인이 요청하지 않았다면 이 메일을 무시하세요.</p>')
        except mailer.MailerError as e:
            print(f"[signupSendCode] 메일 발송 실패: {e}", flush=True)
            raise SignupError("인증 메일을 보내지 못했어요. 잠시 후 다시 시도해 주세요.")
        _signup_sent_at[email] = now
        return {'verifyToken': token, 'expiresIn': SIGNUP_CODE_EXPIRE_MINUTES * 60}

    def signupProcess(self, session, data):
        """
        Request : { "verifyToken", "code", "userName", "password",
                    "agreeAge14", "agreeTerms", "agreePrivacy", "termsVersion", "policyVersion" }
        반환    : 이메일 로그인과 같은 형식(가입 즉시 로그인)
        """
        data = data or {}
        _check_consents(data, SignupError)

        try:
            payload = jwt.decode(data.get('verifyToken') or '', SIGNUP_TOKEN_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise SignupError("인증코드 유효시간이 지났어요. 코드를 다시 받아 주세요.")
        except jwt.InvalidTokenError:
            raise SignupError("이메일 인증을 먼저 해 주세요.")

        jti, email = payload['jti'], payload['email']
        now = time.time()
        _prune_signup_state(now)
        if jti in _signup_used:
            raise SignupError("이미 사용한 인증코드예요. 코드를 다시 받아 주세요.")
        fails = _signup_attempts.get(jti, (0, now))[0]
        if fails >= SIGNUP_CODE_MAX_ATTEMPTS:
            raise SignupError("인증코드를 여러 번 틀렸어요. 코드를 다시 받아 주세요.")
        code = str(data.get('code') or '').strip()
        if not hmac.compare_digest(_code_mac(jti, code), payload['mac']):
            _signup_attempts[jti] = (fails + 1, now)
            left = SIGNUP_CODE_MAX_ATTEMPTS - fails - 1
            raise SignupError(f"인증코드가 맞지 않아요. ({left}번 남음)" if left else "인증코드를 여러 번 틀렸어요. 코드를 다시 받아 주세요.")

        user_name = (data.get('userName') or '').strip()
        if not 1 <= len(user_name) <= 45:
            raise SignupError("이름(닉네임)을 1~45자로 입력해 주세요.")
        password = data.get('password') or ''
        if not PASSWORD_REGEX.match(password):
            raise SignupError("비밀번호는 8자 이상, 대문자·소문자·숫자·특수문자를 각 1자 이상 포함해야 해요.")
        if self.socialLoginDaoImpl.select_users_by_email(session, email):
            raise SignupError("이미 가입된 이메일이에요. 로그인해 주세요.")

        new_id = self.socialLoginDaoImpl.create_user(
            session, user_name=user_name, email=email, phone=None,
            login_type=EMAIL, provider_uid=None, auth_id=DEFAULT_SIGNUP_ROLE, password=password)
        self._save_required_consents(session, new_id)
        _signup_used[jti] = now
        return self._login_result(session, new_id, user_name)

    def _naver_profile(self, session, code, state):
        """code → 네이버 access token → 회원 프로필(/v1/nid/me). client secret 은 서버에만 있다."""
        keys = {r['key_type']: r['key_value']
                for r in self.masterInfosDaoImpl.select_master_key_by_category(session, 'NAVER_AUTH')}
        client_id, client_secret = keys.get('NAVER_AUTH_ID'), keys.get('NAVER_AUTH_SECRET')
        if not client_id or not client_secret:
            raise NaverLoginError("네이버 로그인 설정이 없습니다. 관리자에게 문의해 주세요.")

        # 네이버 가이드(접근 토큰 발급 요청) 예시와 같이 쿼리 파라미터로 보낸다.
        token = requests.post(NAVER_TOKEN_URL, params={
            'grant_type': 'authorization_code', 'client_id': client_id, 'client_secret': client_secret,
            'code': code, 'state': state,
        }, timeout=10).json()
        access_token = token.get('access_token')
        if not access_token:
            # 코드 만료·재사용 등. 네이버 오류 내용은 로그로만 남기고 사용자에게는 일반 문구.
            print(f"[naverProcess] token 실패: {token.get('error')} {token.get('error_description')}", flush=True)
            raise NaverLoginError("네이버 인증이 만료됐어요. 다시 로그인해 주세요.")

        me = requests.get(NAVER_PROFILE_URL, headers={'Authorization': f'Bearer {access_token}'},
                          timeout=10).json()
        if me.get('resultcode') != '00':
            print(f"[naverProcess] profile 실패: {me.get('resultcode')} {me.get('message')}", flush=True)
            raise NaverLoginError("네이버 사용자 정보를 받지 못했습니다.")
        return me.get('response') or {}

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
