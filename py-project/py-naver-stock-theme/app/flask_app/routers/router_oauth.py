"""
router_oauth.py — OAuth / 이메일 인증 라우터

변경 이력:
    - [유지] POST /login     : 소셜 oAuth 로그인 (기존)
    - [유지] GET  /infos/<type> : 소셜 키 정보 조회 (기존)
    - [유지] POST /email     : 이메일 로그인 (기존 라우트, 내부 로직 변경)
    - [신규] POST /refresh   : silent refresh — refreshToken으로 토큰 쌍 재발급
    - [신규] POST /logout    : 서버 측 refreshToken 폐기
    - [신규] require_auth    : Bearer 토큰 검증 decorator (인증 필요 API에 적용)
"""

import logging
import os
from functools import wraps

import jwt  # PyJWT

from flask import Blueprint, request, g

from app.services.common.authService import AuthService, JWT_SECRET, JWT_ALGORITHM, NaverLoginError, SignupError
from app.exceptions import ResetRequiredException  # 단일 출처 임포트
from app.domains.dao.masterInfoDao import MasterInfosDao
from app.flask_app.utils.apiResponse import ApiResponse


authServiceImpl    = AuthService()
masterInfosDaoImpl = MasterInfosDao()

oauth_bp = Blueprint("oauth", __name__)


# ════════════════════════════════════════════════════════════════════
# [신규] Bearer 토큰 검증 Decorator
# ════════════════════════════════════════════════════════════════════
def require_auth(f):
    """
    인증이 필요한 모든 엔드포인트에 붙이는 decorator.

    동작 순서:
        1. Authorization 헤더에서 'Bearer <token>' 형태로 토큰 추출
        2. PyJWT 로 서명 검증 및 만료(exp) 확인
        3. 검증 통과 시 g.current_user_id 에 사용자 ID 저장
           → 라우트 핸들러에서 g.current_user_id 로 접근 가능
        4. 검증 실패 시 반드시 401 반환 (명세: 403 사용 금지)

    사용 예시:
        @stocks_bp.route("/my-stocks")
        @require_auth
        def get_my_stocks():
            user_id = g.current_user_id
            ...

    명세 준수:
        - 검증 실패 응답: { "success": false, "error": { "message": "인증이 필요합니다." } }
        - HTTP 상태코드: 401
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # ── 헤더에서 토큰 추출 ──────────────────────────────────────
        auth_header = request.headers.get('Authorization', '')

        # 'Bearer <token>' 형식이 아닌 경우 즉시 401
        if not auth_header.startswith('Bearer '):
            return ApiResponse.unauthorized("Authorization 헤더가 없거나 형식이 올바르지 않습니다.")

        token = auth_header.split(' ', 1)[1]  # 'Bearer ' 이후의 토큰 문자열만 추출

        try:
            # ── 서명 검증 + 만료 확인 ────────────────────────────────
            # PyJWT decode():
            #   - 서명이 틀리면 InvalidSignatureError
            #   - exp 가 현재 시각보다 이전이면 ExpiredSignatureError 자동 발생
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

            # 검증 통과 — 이후 라우트 핸들러에서 사용자 ID 접근 가능
            # sub 클레임이 문자열 형태이므로 int 변환
            g.current_user_id = int(payload['sub'])

        except jwt.ExpiredSignatureError:
            # accessToken 만료 → 프론트엔드가 /refresh 를 통해 갱신해야 함
            return ApiResponse.unauthorized("액세스 토큰이 만료되었습니다.")

        except jwt.InvalidTokenError:
            # 서명 불일치, 형식 오류 등 그 외 모든 JWT 검증 실패
            return ApiResponse.unauthorized("유효하지 않은 액세스 토큰입니다.")

        # 검증 통과 → 원래 라우트 함수 실행
        return f(*args, **kwargs)

    return decorated


# ════════════════════════════════════════════════════════════════════
# 기존 라우트 (유지)
# ════════════════════════════════════════════════════════════════════

# 소셜 로그인 공개 키 조회 (인가 URL 을 만들 client ID 만)
#   보안: 비로그인 공개 API 라 client ID(*_ID)만 돌려준다. 예전에는 카테고리 전체를 반환해
#   NAVER_AUTH_SECRET 까지 노출됐다(→ 네이버 개발자센터에서 secret 재발급 필요).
#   type 도 허용 목록으로 제한해 다른 카테고리(*_AUTH)의 값을 조회할 수 없게 한다.
#   (휴대폰 번호만으로 사용자를 찾던 POST /oauth/login 은 검증 없이 계정 정보를 내줘 삭제했다)
SOCIAL_PROVIDERS = {'NAVER', 'KAKAO'}


@oauth_bp.route("/infos/<type>")
def oauth_key_info_naver(type):
    type_upper = str(type).upper()
    if type_upper not in SOCIAL_PROVIDERS:
        return ApiResponse.error("지원하지 않는 로그인 방식입니다.", status=404)
    try:
        rows = masterInfosDaoImpl.select_master_key_by_category(g.db, type_upper + '_AUTH')
        public = [
            {'key_type': r['key_type'], 'key_value': r['key_value']}
            for r in rows if str(r.get('key_type', '')).upper().endswith('_ID')
        ]
        return ApiResponse.success(public)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("로그인 정보를 불러오지 못했습니다.")


# ── 네이버 로그인 ────────────────────────────────────────────────────
@oauth_bp.route("/naver", methods=['POST'])
def oauth_login_naver():
    """
    POST /api/oauth/naver

    Request : { "code": "<네이버 인가 코드>", "state": "<인가 요청 때 보낸 state>" }
    Response: 이메일 로그인과 같은 형식 + "naverResult": "login" | "linked" | "created"
        login   이미 연결된 네이버 계정
        linked  이메일이 같은 기존 계정에 이번에 연결됨
        created 일치하는 계정이 없어 신규 가입(STOCK_USER)

    사용자 정보는 서버가 네이버에서 직접 받는다(클라이언트가 보낸 값은 쓰지 않는다).
    실패하면 가입 도중 만든 행이 남지 않게 롤백한다(요청 종료 시 자동 commit 되므로 반드시 필요).
    """
    data = request.get_json(silent=True) or {}
    try:
        return ApiResponse.success(authServiceImpl.naverProcess(g.db, data))
    except NaverLoginError as e:
        g.db.rollback()
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("네이버 로그인 중 오류가 발생했습니다.")


@oauth_bp.route("/naver/consent", methods=['POST'])
def oauth_naver_consent():
    """
    POST /api/oauth/naver/consent — 개인정보 처리방침 동의 후 로그인

    /naver 응답이 consentRequired 일 때(신규 가입·미동의 사용자) 동의 화면에서 호출한다.
    Request : { "consentToken": "<naver 응답의 consentToken>", "policyVersion": "...", "agreePrivacy": true }
    Response: 이메일 로그인과 같은 형식 + "naverResult"

    실패는 401 이 아니라 400 — 401 이면 프런트 interceptor 가 refresh/강제 로그아웃을 시도한다.
    """
    data = request.get_json(silent=True) or {}
    try:
        return ApiResponse.success(authServiceImpl.naverConsentProcess(g.db, data))
    except NaverLoginError as e:
        g.db.rollback()
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("가입 처리 중 오류가 발생했습니다.")


# ── 이메일 회원가입 ──────────────────────────────────────────────────
@oauth_bp.route("/signup/code", methods=['POST'])
def oauth_signup_code():
    """
    POST /api/oauth/signup/code — 가입 인증코드 메일 발송

    Request : { "email": "..." }
    Response: { "verifyToken": "<서명 토큰>", "expiresIn": 600 }   (코드는 메일로만 간다)
    """
    data = request.get_json(silent=True) or {}
    try:
        return ApiResponse.success(authServiceImpl.signupSendCode(g.db, data))
    except SignupError as e:
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("인증코드를 보내지 못했어요.")


@oauth_bp.route("/signup", methods=['POST'])
def oauth_signup():
    """
    POST /api/oauth/signup — 인증코드 확인 + 이메일 가입 + 동의 기록 후 바로 로그인

    Request : { "verifyToken", "code", "userName", "password",
                "agreeAge14", "agreeTerms", "agreePrivacy", "termsVersion", "policyVersion" }
    Response: 이메일 로그인과 같은 형식
    실패는 400 — 401 이면 프런트 interceptor 가 refresh/강제 로그아웃을 시도한다.
    """
    data = request.get_json(silent=True) or {}
    try:
        return ApiResponse.success(authServiceImpl.signupProcess(g.db, data))
    except SignupError as e:
        g.db.rollback()
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("가입 처리 중 오류가 발생했습니다.")


# ── 이메일 로그인 ────────────────────────────────────────────────────
# [수정] 내부적으로 authService.emailProcess() 가 실제 JWT + refreshToken 발급으로 변경됨
# 라우트 자체는 기존 그대로 유지
@oauth_bp.route("/email", methods=['POST'])
def oauth_login_email():
    """
    POST /api/oauth/email

    Request : { "email": "...", "pswd": "..." }
    Response: {
        "success": true,
        "data": {
            "accessToken": "<JWT>",
            "refreshToken": "<불투명 토큰>",
            "loginInfo": { "user_id": "1", "user_name": "홍길동", "role": ["USER"] }
        }
    }
    """
    data = request.get_json()
    try:
        results = authServiceImpl.emailProcess(g.db, data)
        return ApiResponse.success(results)
    except ResetRequiredException as rre:
        # reset_flag == 'Y': 인증은 통과했으나 비밀번호 재설정이 필요한 계정
        # 프론트엔드는 error.code === 'RESET_REQUIRED' 를 감지해 재설정 페이지로 유도
        print(rre)
        return ApiResponse.reset_required()
    except Exception as e:
        return ApiResponse.error(str(e))


# ════════════════════════════════════════════════════════════════════
# [신규] 비밀번호 재설정
# ════════════════════════════════════════════════════════════════════
@oauth_bp.route("/password/reset", methods=['POST'])
def oauth_password_reset():
    """
    POST /api/oauth/password/reset

    reset_flag == 'Y' 인 계정의 비밀번호를 새 값으로 교체.
    성공 시 기존 refreshToken 전체 폐기 → 이전 세션 무효화.

    Request : { "email": "...", "new_password": "..." }
    Response (성공):
        { "success": true, "data": null }

    Response (실패 — 사용자 없음 / reset 대상 아님 / 필수값 누락):
        HTTP 400
        { "success": false, "error": { "message": "..." } }
    """
    data = request.get_json() or {}
    try:
        authServiceImpl.resetPasswordProcess(g.db, data)
        return ApiResponse.success(None)
    except Exception as e:
        return ApiResponse.error(str(e))


# ════════════════════════════════════════════════════════════════════
# [신규] 토큰 재발급 (Silent Refresh)
# ════════════════════════════════════════════════════════════════════
@oauth_bp.route("/refresh", methods=['POST'])
def oauth_refresh():
    """
    POST /api/oauth/refresh

    프론트엔드 axios interceptor가 accessToken 만료 시 자동 호출.
    기존 refreshToken을 폐기하고 새 토큰 쌍을 발급(Rotation).

    Request : { "refreshToken": "<기존 refresh token>" }
    Response (성공):
        {
            "success": true,
            "data": {
                "accessToken": "<새 JWT>",
                "refreshToken": "<새 refresh token>"
            }
        }
    Response (실패 — DB 없음·폐기됨·만료):
        HTTP 401
        { "success": false, "error": { "message": "..." } }

    명세 준수:
        - 실패 시 반드시 401 반환 → 프론트가 자동 로그아웃 처리
    """
    data = request.get_json()
    try:
        results = authServiceImpl.refreshProcess(g.db, data)
        return ApiResponse.success(results)
    except Exception as e:
        # refreshProcess 에서 발생하는 모든 예외는 인증 실패로 간주 → 401
        return ApiResponse.unauthorized(str(e))


# ════════════════════════════════════════════════════════════════════
# [신규] 로그아웃 — 서버 측 refreshToken 폐기
# ════════════════════════════════════════════════════════════════════
@oauth_bp.route("/logout", methods=['POST'])
def oauth_logout():
    """
    POST /api/oauth/logout

    클라이언트 로컬 세션 초기화 + 서버 측 refreshToken 폐기.
    로그아웃 후 동일 refreshToken으로 /refresh 를 재시도하면
    재사용 감지 로직이 작동해 전체 세션이 강제 만료됨.

    Request : { "refreshToken": "<현재 refresh token>" }
    Response: { "success": true, "data": null }

    참고:
        - accessToken은 서버가 무효화할 수 없으므로 (stateless JWT),
          만료될 때까지 기다리거나 accessToken 블랙리스트 구현이 필요.
          현재는 refreshToken 폐기만으로 세션 갱신을 차단함.
        - 이 엔드포인트는 Authorization 헤더를 요구하지 않음
          (로그아웃 시 accessToken 이 이미 만료된 경우도 허용)
    """
    data = request.get_json() or {}
    try:
        result = authServiceImpl.logoutProcess(g.db, data)
        return ApiResponse.success(result)
    except Exception as e:
        return ApiResponse.error(str(e))
