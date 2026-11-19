"""
router_priority_target.py — 최우선타겟 지정. **비밀상회 전용**(2026-11-19 router_stocks 에서 분리).

매매 워커가 읽는 값이라(최우선타겟 = 갭게이트 면제 + 1포지션 예외) 매매가 없는 양봉상회에는 열지 않는다.
url_prefix /api/v1/stocks — 경로는 예전과 같다.
"""
import logging
import traceback

from flask import Blueprint, request, g

from app.services.stocks.PriorityTargetService import PriorityTargetService
from web_shared.constants.Literal import Literal
from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse

priority_bp = Blueprint("priority_target", __name__)
stockServiceImpl = PriorityTargetService()


# ===============================================================================
# 최우선타겟 (Home.vue 매수추천 카드 select)
#   GET    /buy-target/priority  조회 — {stock_code, stock_name, set_ymd} 또는 전부 null
#   PUT    /buy-target/priority  지정 — body {ymd, stock_code}
#   DELETE /buy-target/priority  해제
# 본인 것만 다루므로 JWT 인증 필요(user_id 는 클라이언트가 보내지 않는다).
# ===============================================================================
@priority_bp.route('/buy-target/priority', methods=['GET'])
@require_auth
def get_buy_target_priority():
    try:
        result = stockServiceImpl.get_priority_target(g.db, g.current_user_id)
        return ApiResponse.success(result)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


@priority_bp.route('/buy-target/priority', methods=['PUT'])
@require_auth
def set_buy_target_priority():
    body = request.get_json(silent=True) or {}
    ymd = body.get(Literal.YMD)
    stock_code = body.get(Literal.STOCK_CODE)
    if not ymd or not stock_code:
        return ApiResponse.error("ymd, stock_code 는 필수입니다.", status=400)

    try:
        result = stockServiceImpl.set_priority_target(g.db, g.current_user_id, ymd, stock_code)
        return ApiResponse.success(result)
    except ValueError as e:
        return ApiResponse.error(str(e), status=400)
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])


@priority_bp.route('/buy-target/priority', methods=['DELETE'])
@require_auth
def clear_buy_target_priority():
    try:
        stockServiceImpl.clear_priority_target(g.db, g.current_user_id)
        return ApiResponse.success({'cleared': True})
    except Exception as e:
        logging.error(str(e))
        traceback.print_exc()
        return ApiResponse.error(str(e)[:255])
