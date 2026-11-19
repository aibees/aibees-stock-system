"""
배치 서버 인증 — 비밀상회 API(py-secret-api)가 발급한 accessToken(JWT)을 같은 키로 검증한다.

예전에는 이 서버에 인증이 아예 없었다. 웹 nginx 가 /api/v1/jobs·/api/v1/notify 를 그대로 넘기므로
주소만 알면 누구나 배치를 돌리고(/jobs/once), 전체 사용자에게 푸시를 보내고(/notify/test-send),
남의 user_id 로 기기를 등록해 그 사람의 체결 알림을 받을 수 있었다(/notify/register).

환경변수(.env, docker-compose env_file):
    JWT_SECRET_KEY  : 비밀상회 API 와 같은 값(32자 이상). 없으면 관리자 API 는 전부 503 으로 거절한다.
    BATCH_ADMIN_KEY : (선택, 32자 이상) 서버 안에서 curl 로 배치를 돌릴 때 X-Batch-Key 헤더로 보낸다.
                      설정하지 않으면 이 방식은 꺼진다.
"""
import hmac
import logging
import os
from functools import wraps

import jwt  # PyJWT (firebase-admin 의존성으로 이미 설치됨)
from dotenv import load_dotenv
from flask import g, request
from sqlalchemy import select

from app.flask_app.utils.apiResponse import ApiResponse
from stock_shared.models.userAuth import UserAuth
from stock_shared.models.userRole import UserRole

load_dotenv()

JWT_ALGORITHM = 'HS256'
ADMIN_AUTH_ID = 'ADMIN'
_MIN_SECRET_LENGTH = 32
_PLACEHOLDER = 'CHANGE_THIS_TO_A_STRONG_SECRET_IN_PRODUCTION'


def _read_secret(name):
    value = (os.environ.get(name) or '').strip()
    if not value or value == _PLACEHOLDER or len(value) < _MIN_SECRET_LENGTH:
        return None
    return value


JWT_SECRET = _read_secret('JWT_SECRET_KEY')
BATCH_ADMIN_KEY = _read_secret('BATCH_ADMIN_KEY')

if JWT_SECRET is None:
    logging.critical("[auth] JWT_SECRET_KEY 가 없거나 %d자 미만입니다. 배치 관리 API 는 토큰으로 열 수 없습니다.",
                     _MIN_SECRET_LENGTH)


class _AuthFailure(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def _bearer_token():
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    return header.split(' ', 1)[1].strip() or None


def _decode_user_id(token):
    """토큰 → user_id. 실패하면 _AuthFailure. 401 은 프런트가 토큰 재발급 후 다시 보낸다."""
    if JWT_SECRET is None:
        raise _AuthFailure("서버 인증 설정이 없습니다. 관리자에게 알려 주세요.", 503)
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload['sub'])
    except jwt.ExpiredSignatureError:
        raise _AuthFailure("액세스 토큰이 만료되었습니다.", 401)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise _AuthFailure("유효하지 않은 액세스 토큰입니다.", 401)


def user_auth_ids(session, user_id):
    """사용자의 유효 권한(auth_id) 목록. 비밀상회 API RoleMenuDao.select_user_auth_ids 와 같은 조건."""
    stmt = (
        select(UserAuth.auth_id)
        .join(UserRole, UserAuth.auth_id == UserRole.auth_id)
        .where(UserAuth.user_id == user_id, UserAuth.enabled_flag == 'Y')
    )
    return list(session.execute(stmt).scalars().all())


def _batch_key_ok():
    if BATCH_ADMIN_KEY is None:
        return False
    given = request.headers.get('X-Batch-Key', '')
    return bool(given) and hmac.compare_digest(given.encode(), BATCH_ADMIN_KEY.encode())


def require_admin(f):
    """ADMIN 권한 토큰 또는 X-Batch-Key 가 있어야 통과."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if _batch_key_ok():
            g.current_user_id = None
            return f(*args, **kwargs)
        token = _bearer_token()
        if token is None:
            return ApiResponse.error("관리자 인증이 필요합니다.", status=401)
        try:
            user_id = _decode_user_id(token)
        except _AuthFailure as e:
            return ApiResponse.error(e.message, status=e.status)
        if ADMIN_AUTH_ID not in user_auth_ids(g.db, user_id):
            return ApiResponse.error("관리자 권한이 필요합니다.", status=403)
        g.current_user_id = user_id
        return f(*args, **kwargs)
    return decorated


def optional_user(f):
    """토큰이 없으면 g.current_user_id=None 으로 통과, 있으면 검증한다.
    만료·위조 토큰은 401 — 게스트로 조용히 강등하면 로그인 사용자의 기기가 익명으로 덮어써진다."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _bearer_token()
        if token is None:
            g.current_user_id = None
            return f(*args, **kwargs)
        try:
            g.current_user_id = _decode_user_id(token)
        except _AuthFailure as e:
            return ApiResponse.error(e.message, status=e.status)
        return f(*args, **kwargs)
    return decorated
