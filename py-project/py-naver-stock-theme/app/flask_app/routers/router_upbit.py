"""
router_upbit.py — Upbit 연동 라우터

엔드포인트 (Blueprint url_prefix = /api/v1/upbit):
    GET /balance   Upbit 잔고 조회 (서버간 호출)

인증:
    - 다른 프로젝트(서버)에서 호출하는 서버간 API.
    - maria-Authorization 헤더로 검증 (require_maria_auth).
    - user_id 는 쿼리 파라미터로 전달받는다.

응답:
    - coin 미지정: { krw_balance, holdings: [...] }
    - coin 지정  : { coin, free, used, total }
"""

import os
import hmac
import logging
from functools import wraps
from pathlib import Path

from dotenv import dotenv_values
from flask import Blueprint, request, g

from app.services.upbit.upbitService import UpbitService
from app.flask_app.utils.apiResponse import ApiResponse

logging.basicConfig(level=logging.ERROR)

upbit_bp = Blueprint("upbit", __name__)
upbitServiceImpl = UpbitService()

# 서버간 호출 인증 토큰 — .env.mcp 의 MARIA_AUTH_TOKEN 으로 주입 (호출측과 동일 값 공유)
# 우선순위: 실제 환경변수(컨테이너 주입) > .env.mcp 파일 값 > 하드코딩 default
# dotenv_values 는 os.environ 을 오염시키지 않고 파일에서 해당 키만 파싱한다.
_ENV_MCP_PATH = Path(__file__).resolve().parents[3] / ".env.mcp"
MARIA_AUTH_TOKEN = (
    os.getenv("MARIA_AUTH_TOKEN")
    or dotenv_values(_ENV_MCP_PATH).get("MARIA_AUTH_TOKEN")
    or "ngnbiegfideblrlcffhugdjfdjegunneedvftcnbnelv"
)


# ════════════════════════════════════════════════════════════════════
# maria-Authorization 검증 Decorator (서버간 호출)
# ════════════════════════════════════════════════════════════════════
def require_maria_auth(f):
    """
    다른 프로젝트(서버)에서 호출하는 서버간 API 보호용 decorator.

    동작:
        1. 서버에 MARIA_AUTH_TOKEN 이 설정돼 있지 않으면 fail-closed(401)
        2. maria-Authorization 헤더를 사전 공유 토큰과 상수시간 비교
        3. 불일치 시 401
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 토큰 미설정 시 열려버리지 않도록 fail-closed
        if not MARIA_AUTH_TOKEN:
            logging.error("MARIA_AUTH_TOKEN 미설정 — 서버간 인증 불가")
            return ApiResponse.unauthorized("서버 인증 설정 오류입니다.")

        token = request.headers.get('maria-Authorization', '')
        # 타이밍 공격 방지를 위한 상수시간 비교
        if not hmac.compare_digest(token, MARIA_AUTH_TOKEN):
            return ApiResponse.unauthorized("서버간 인증 토큰이 유효하지 않습니다.")
        return f(*args, **kwargs)

    return decorated


# ════════════════════════════════════════════════════════════════════
# 1. 잔고 조회
#    GET /api/v1/upbit/balance?user_id=1[&coin=BTC]
# ════════════════════════════════════════════════════════════════════
@upbit_bp.route("/balance", methods=['GET'])
@require_maria_auth
def get_upbit_balance():
    user_id = request.args.get('user_id', type=int)
    coin = request.args.get('coin')  # 선택

    if user_id is None:
        return ApiResponse.error("user_id 는 필수입니다.", status=400)

    try:
        data = upbitServiceImpl.get_balance(g.db, user_id, coin)
        return ApiResponse.success(data)
    except ValueError as ve:
        # 인증정보 미설정 / 사용자 없음 등 클라이언트 오류
        return ApiResponse.error(str(ve), status=400)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))
