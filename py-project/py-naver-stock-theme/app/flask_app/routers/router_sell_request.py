"""
router_sell_request.py — 매도신호 신청 (stock_sell_request) 라우터

프론트엔드: SellRequest.vue
패턴: batch-jobs(router_batches.py)와 동일 스타일

보안 핵심:
    - user_id 는 클라이언트가 보내지 않는다.
    - 모든 엔드포인트에 @require_auth 를 적용해 JWT 에서 user_id 를 추출하고
      (g.current_user_id), 조회/수정/삭제는 반드시 본인 데이터로만 제한한다.

엔드포인트 (Blueprint url_prefix = /api/v1):
    GET    /sell-requests               목록 조회 (본인 데이터만)
    POST   /sell-requests               등록 (5개 초과 / PK 중복 차단)
    PUT    /sell-requests/<stock_code>  수정
    PATCH  /sell-requests/<stock_code>  사용/미사용 토글
    DELETE /sell-requests/<stock_code>  삭제
"""

import logging
from flask import Blueprint, request, g

from app.domains.dao.stockSellRequestDao import StockSellRequestDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

logging.basicConfig(level=logging.ERROR)

sell_request_bp = Blueprint("sell_requests", __name__)

sellRequestDaoImpl = StockSellRequestDao()

# 본인 보유 최대 건수 (프론트에서도 막지만 서버에서 최종 방어)
MAX_SELL_REQUEST_PER_USER = 5


# ===============================================================================
# 유효성 검증 헬퍼
# ===============================================================================
def _normalize_payload(data: dict) -> dict:
    """
    요청 body 를 정규화한다.
    - 빈 문자열은 None 으로 변환 (entry_date/entry_price/hold_qty/memo 는 null 허용)
    - entry_price / hold_qty 는 숫자 변환 시도
    """
    def _blank_to_none(v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == '':
            return None
        return v

    def _to_number(v):
        v = _blank_to_none(v)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError("entry_price / hold_qty 는 숫자여야 합니다.")

    enabled_flag = data.get('enabled_flag') or 'Y'
    if enabled_flag not in ('Y', 'N'):
        raise ValueError("enabled_flag 값은 'Y' 또는 'N' 이어야 합니다.")

    return {
        'stock_code': _blank_to_none(data.get('stock_code')),
        'stock_name': _blank_to_none(data.get('stock_name')),
        'entry_date': _blank_to_none(data.get('entry_date')),
        'entry_price': _to_number(data.get('entry_price')),
        'hold_qty': _to_number(data.get('hold_qty')),
        'memo': _blank_to_none(data.get('memo')),
        'enabled_flag': enabled_flag,
    }


# ===============================================================================
# 0. ROOT :: TEST
# ===============================================================================
@sell_request_bp.route("/sell-requests/ping", methods=['GET'])
def sell_requests_index():
    return {'msg': 'aibees flask :: sell-requests home'}


# ===============================================================================
# 1. 목록 조회 — 본인 데이터만
#    GET /api/v1/sell-requests
# ===============================================================================
@sell_request_bp.route("/sell-requests", methods=['GET'])
@require_auth
def select_sell_request_list():
    try:
        results = sellRequestDaoImpl.select_all_by_user(g.db, g.current_user_id)
        return ApiResponse.success(results)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ===============================================================================
# 2. 등록 (신규)
#    POST /api/v1/sell-requests
# ===============================================================================
@sell_request_bp.route("/sell-requests", methods=['POST'])
@require_auth
def insert_sell_request():
    data = request.get_json(silent=True) or {}

    try:
        payload = _normalize_payload(data)
    except ValueError as ve:
        return ApiResponse.error(str(ve))

    if not payload['stock_code']:
        return ApiResponse.error("stock_code는 필수입니다.")

    try:
        # 본인 보유 건수 5개 초과 차단 (서버 최종 방어)
        current_cnt = sellRequestDaoImpl.count_by_user(g.db, g.current_user_id)
        if current_cnt >= MAX_SELL_REQUEST_PER_USER:
            return ApiResponse.error(
                f"매도신호 신청은 최대 {MAX_SELL_REQUEST_PER_USER}개까지 등록할 수 있습니다."
            )

        # PK 중복 (user_id, stock_code) 차단
        exists = sellRequestDaoImpl.select_by_pk(g.db, g.current_user_id, payload['stock_code'])
        if exists:
            return ApiResponse.error(
                f"이미 등록된 종목입니다. (stock_code={payload['stock_code']})", status=409
            )

        sellRequestDaoImpl.insert(g.db, g.current_user_id, payload)
        g.db.commit()

        return ApiResponse.success(
            sellRequestDaoImpl.select_by_pk(g.db, g.current_user_id, payload['stock_code'])
        )
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ===============================================================================
# 3. 수정
#    PUT /api/v1/sell-requests/<stock_code>
# ===============================================================================
@sell_request_bp.route("/sell-requests/<stock_code>", methods=['PUT'])
@require_auth
def update_sell_request(stock_code):
    data = request.get_json(silent=True) or {}

    try:
        payload = _normalize_payload(data)
    except ValueError as ve:
        return ApiResponse.error(str(ve))

    try:
        exists = sellRequestDaoImpl.select_by_pk(g.db, g.current_user_id, stock_code)
        if not exists:
            return ApiResponse.error(
                f"존재하지 않는 종목입니다. (stock_code={stock_code})", status=404
            )

        sellRequestDaoImpl.update_by_user_key(g.db, g.current_user_id, stock_code, payload)
        g.db.commit()

        return ApiResponse.success(
            sellRequestDaoImpl.select_by_pk(g.db, g.current_user_id, stock_code)
        )
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ===============================================================================
# 4. 사용/미사용 토글 (PATCH)
#    PATCH /api/v1/sell-requests/<stock_code>
# ===============================================================================
@sell_request_bp.route("/sell-requests/<stock_code>", methods=['PATCH'])
@require_auth
def patch_sell_request_enabled(stock_code):
    data = request.get_json(silent=True) or {}
    enabled_flag = data.get('enabled_flag')

    if enabled_flag not in ('Y', 'N'):
        return ApiResponse.error("enabled_flag 값은 'Y' 또는 'N' 이어야 합니다.")

    try:
        exists = sellRequestDaoImpl.select_by_pk(g.db, g.current_user_id, stock_code)
        if not exists:
            return ApiResponse.error(
                f"존재하지 않는 종목입니다. (stock_code={stock_code})", status=404
            )

        sellRequestDaoImpl.update_enabled_flag(g.db, g.current_user_id, stock_code, enabled_flag)
        g.db.commit()

        return ApiResponse.success({'stock_code': stock_code, 'enabled_flag': enabled_flag})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ===============================================================================
# 5. 삭제
#    DELETE /api/v1/sell-requests/<stock_code>
# ===============================================================================
@sell_request_bp.route("/sell-requests/<stock_code>", methods=['DELETE'])
@require_auth
def delete_sell_request(stock_code):
    try:
        exists = sellRequestDaoImpl.select_by_pk(g.db, g.current_user_id, stock_code)
        if not exists:
            return ApiResponse.error(
                f"존재하지 않는 종목입니다. (stock_code={stock_code})", status=404
            )

        sellRequestDaoImpl.delete_by_user_key(g.db, g.current_user_id, stock_code)
        g.db.commit()

        return ApiResponse.success(True)
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))
