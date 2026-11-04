"""
router_manual_sell.py — 매도 수기등록 (Blueprint url_prefix = /api/v1/auto-trade/manual-sell)

    GET  /holdings        계좌 실보유 목록(LimitOrder.vue 의 종목 목록)
    GET  /orders          내 수기등록 전체(모든 상태)
    POST /orders          새 티어 등록   body: { stock_code, sell_price, trigger_type, qty_ratio, memo, enabled_flag }
    POST /orders/cancel   티어 취소      body: { manual_sell_id }

설계 메모:
    - 등록된 지정가는 실제 매도로 이어진다. 그래서 인증이 없는 batch 앱에서 이 서버로 옮겼다(2026-11-05).
      user_id 는 JWT 에서만 얻고 WORKER_USER 권한을 요구한다. 본문의 user_id 는 읽지 않는다.
    - 등록 조건은 계좌 실보유(user_holdings)뿐이다 — HTS/MTS 로 산 종목도 등록할 수 있다.
      실시간 감시 시작은 worker 의 계좌 동기화·수기등록 재적재 주기에 달려 있다.
    - 종목당 여러 티어(사다리)를 허용한다. 등록은 항상 새 행이고, 취소는 id 로 그 행만 한다.
    - base_qty(등록 시점 보유수량)를 저장해 먼저 체결된 티어가 다음 티어의 수량을 줄이지 않게 한다.
"""
import logging
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, request

from app.domains.dao.manualSellDao import ManualSellDao
from app.flask_app.routers.router_auto_trade import _require_worker
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

manual_sell_bp = Blueprint("manual_sell", __name__)
manualSellDaoImpl = ManualSellDao()


def _decimal_or_none(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _parse_tier(body: dict):
    """(값 dict, None) 또는 (None, 오류 문구)."""
    stock_code = str(body.get('stock_code') or '').strip()
    if not stock_code:
        return None, "stock_code 가 필요합니다."

    sell_price = _decimal_or_none(body.get('sell_price'))
    if sell_price is None or sell_price <= 0:
        return None, "sell_price 가 필요합니다."

    # 방향: UP=지정가 이상이면 매도(익절·기본), DOWN=지정가 이하이면 매도(손절).
    # 잘못된 값을 조용히 UP 으로 바꾸지 않는다 — 손절 의도가 익절로 저장되면 아무 때도 팔리지 않는다.
    trigger_type = str(body.get('trigger_type') or 'UP').upper()
    if trigger_type not in ('UP', 'DOWN'):
        return None, "trigger_type 은 UP(익절) 또는 DOWN(손절) 이어야 합니다."

    raw_ratio = body.get('qty_ratio')
    qty_ratio = _decimal_or_none(1 if raw_ratio in (None, '') else raw_ratio)
    if qty_ratio is None or qty_ratio <= 0 or qty_ratio > 1:
        return None, "매도 비율은 1~100% 로 입력해 주세요."

    enabled_flag = 'N' if str(body.get('enabled_flag') or 'Y').upper() == 'N' else 'Y'
    memo = body.get('memo')
    memo = str(memo)[:255] if memo else None

    return {'stock_code': stock_code, 'sell_price': sell_price, 'trigger_type': trigger_type,
            'qty_ratio': qty_ratio, 'enabled_flag': enabled_flag, 'memo': memo}, None


@manual_sell_bp.route("/holdings", methods=['GET'])
@require_auth
def get_holdings():
    denied = _require_worker()
    if denied:
        return denied
    try:
        return ApiResponse.success(manualSellDaoImpl.select_holdings(g.db, g.current_user_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("보유 종목을 불러오지 못했습니다.")


@manual_sell_bp.route("/orders", methods=['GET'])
@require_auth
def get_orders():
    denied = _require_worker()
    if denied:
        return denied
    try:
        return ApiResponse.success(manualSellDaoImpl.select_orders(g.db, g.current_user_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("매도 수기등록을 불러오지 못했습니다.")


@manual_sell_bp.route("/orders", methods=['POST'])
@require_auth
def create_order():
    denied = _require_worker()
    if denied:
        return denied
    tier, error = _parse_tier(request.get_json(silent=True) or {})
    if error:
        return ApiResponse.error(error, status=400)
    uid = g.current_user_id
    try:
        holding = manualSellDaoImpl.select_holding(g.db, uid, tier['stock_code'])
        if not holding or Decimal(str(holding.get('qty') or 0)) <= 0:
            return ApiResponse.error("계좌에 보유 중인 종목만 등록할 수 있습니다.", status=400)
        new_id = manualSellDaoImpl.insert(
            g.db, uid, tier['stock_code'], holding.get('stock_name'), tier['sell_price'],
            tier['trigger_type'], tier['qty_ratio'], holding['qty'], tier['enabled_flag'], tier['memo'])
        return ApiResponse.success(manualSellDaoImpl.select_order(g.db, uid, new_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("매도 수기등록을 저장하지 못했습니다.")


@manual_sell_bp.route("/orders/cancel", methods=['POST'])
@require_auth
def cancel_order():
    denied = _require_worker()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    try:
        order_id = int(body.get('manual_sell_id'))
    except (TypeError, ValueError):
        return ApiResponse.error("manual_sell_id 가 올바르지 않습니다.", status=400)
    try:
        if not manualSellDaoImpl.cancel(g.db, g.current_user_id, order_id):
            return ApiResponse.error("취소할 수 있는 등록이 아닙니다.", status=400)
        return ApiResponse.success(None)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("매도 수기등록을 취소하지 못했습니다.")
