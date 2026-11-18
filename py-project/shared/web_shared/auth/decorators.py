"""
웹 공통 인증 데코레이터(양봉상회·비밀상회 웹서버 공용, 2026-11-18 router_oauth·router_master 에서 옮김).

    require_auth  : Bearer JWT 필수. 통과하면 g.current_user_id
    optional_auth : 토큰 없으면 게스트(g.current_user_id=None), 있으면 require_auth 와 같은 검증
    require_admin : ADMIN 권한(role) 필수
    require_super : 슈퍼유저(SUPER_USER_IDS) 필수

g.db(요청 DB 세션)는 web_shared.app_factory 가 요청마다 연다.
"""
from functools import wraps

import jwt  # PyJWT
from flask import request, g

from web_shared.auth.service import JWT_SECRET, JWT_ALGORITHM, JWT_SECRET_MISSING
from web_shared.dao.roleMenuDao import RoleMenuDao, ADMIN_AUTH_ID, is_super_user
from web_shared.http.response import ApiResponse

roleMenuDaoImpl = RoleMenuDao()


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

        # 서명 키가 설정되지 않은 서버는 어떤 토큰도 믿지 않는다(fail closed). 401 이 아니라 503 —
        # 401 이면 프런트가 재발급·재로그인을 반복하므로 설정 문제임을 구분해 돌려준다.
        if JWT_SECRET_MISSING:
            return ApiResponse.error("서버 인증 설정이 없습니다. 관리자에게 알려 주세요.", status=503)

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


def require_admin(f):
    """ADMIN 권한 사용자만 통과. JWT 검증(@require_auth)을 포함한다."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        auth_ids = roleMenuDaoImpl.select_user_auth_ids(g.db, g.current_user_id)
        if ADMIN_AUTH_ID not in auth_ids:
            return ApiResponse.error("관리자 권한이 필요합니다.", status=403)
        return f(*args, **kwargs)
    return decorated

def optional_auth(f):
    """토큰이 없으면 게스트(g.current_user_id=None)로 통과, 있으면 @require_auth 와 동일하게 검증.

    토큰이 있는데 만료/위조면 401 이 나가야 프런트의 silent refresh 가 동작한다
    (게스트로 조용히 강등하면 로그인 사용자의 메뉴가 사라진 채 새로고침 루프가 생긴다).
    """
    authed = require_auth(f)

    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.headers.get('Authorization', '').startswith('Bearer '):
            g.current_user_id = None
            return f(*args, **kwargs)
        return authed(*args, **kwargs)
    return decorated


def require_super(f):
    """슈퍼유저(SUPER_USER_IDS, 기본 user_id=1)만 통과. JWT 검증을 포함한다."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not is_super_user(g.current_user_id):
            return ApiResponse.error("권한이 없습니다.", status=403)
        return f(*args, **kwargs)
    return decorated
