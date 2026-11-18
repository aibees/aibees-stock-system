"""
router_manual_buy.py — 수동 매수 (Blueprint url_prefix = /api/v1/auto-trade/manual-buy)

    GET  /               내 주문 목록          ?limit=30
    POST /               주문 요청             body: { client_key, stock_code, order_type, qty 또는 qty_pct, limit_price }
    POST /<id>/cancel    주문 취소

설계 메모:
    - user_id 는 JWT 에서만 얻고 WORKER_USER 권한을 요구한다(주문 API 라 batch 앱의 무인증 경로에 두지 않는다).
    - 이 서버는 주문을 내지 않는다. 요청을 trade_worker_manual_buy 에 저장하면 worker 가 폴링해서 낸다
      (py-stock-batch trade_worker/manual_buy.py). 거래 시간·주문가능수량 판정도 실제 주문 직전에 worker 가 한다.
    - 추천·매수 게이트와 무관하게 master_stock 의 모든 종목을 살 수 있고, HALT 여도 막지 않는다.
    - qty_pct 는 주문가능수량 대비 %다. 화면이 시장가의 현재가를 모르고 증거금율도 종목마다 달라, 주문 직전 worker 가
      KIS 주문가능수량으로 수량을 확정한다. 그 전까지 qty 는 0 이다.
    - client_key 가 같은 재전송은 같은 주문을 돌려준다(주문이 두 번 나가지 않는다).
"""
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError

from app.domains.dao.manualBuyDao import ManualBuyDao
from app.flask_app.routers.router_auto_trade import _require_worker
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

manual_buy_bp = Blueprint("manual_buy", __name__)
manualBuyDaoImpl = ManualBuyDao()

ORDER_TYPES = ('MARKET', 'LIMIT')
MAX_ORDER_QTY = 1_000_000     # 오입력 방지. 실제 상한은 worker 의 주문가능수량 조회가 정한다
# 2023.1 호가가격단위 (trade_worker Broker._TICKS 와 같은 표)
_TICKS = ((2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50), (200_000, 100), (500_000, 500))


def _tick_size(price) -> int:
    for upper, tick in _TICKS:
        if price < upper:
            return tick
    return 1_000


def _jsonable(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _parse_order(body: dict):
    """요청 본문 검증. (값 dict, None) 또는 (None, 오류 문구)."""
    client_key = str(body.get('client_key') or '').strip()
    if not client_key or len(client_key) > 64:
        return None, "client_key 가 올바르지 않습니다."

    stock_code = str(body.get('stock_code') or '').strip()
    if not stock_code:
        return None, "종목을 선택해 주세요."

    order_type = str(body.get('order_type') or '').strip().upper()
    if order_type not in ORDER_TYPES:
        return None, "주문 방식은 시장가 또는 지정가여야 합니다."

    qty, qty_pct = 0, None
    raw_qty, raw_pct = body.get('qty'), body.get('qty_pct')
    if (raw_qty in (None, '')) == (raw_pct in (None, '')):
        return None, "수량 또는 비율 중 하나만 입력해 주세요."
    if raw_pct not in (None, ''):
        try:
            qty_pct = Decimal(str(raw_pct))
            if not qty_pct.is_finite() or qty_pct != qty_pct.to_integral_value():
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            return None, "비율은 1~100% 로 입력해 주세요."
        if qty_pct < 1 or qty_pct > 100:
            return None, "비율은 1~100% 로 입력해 주세요."
    else:
        try:
            qty_dec = Decimal(str(raw_qty))
            if qty_dec != qty_dec.to_integral_value():
                raise ValueError
            qty = int(qty_dec)
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            return None, "수량은 1주 단위로 입력해 주세요."
        if qty < 1 or qty > MAX_ORDER_QTY:
            return None, f"수량은 1~{MAX_ORDER_QTY:,}주로 입력해 주세요."

    limit_price = None
    if order_type == 'LIMIT':
        try:
            limit_price = Decimal(str(body.get('limit_price')))
            if not limit_price.is_finite():
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            return None, "지정가를 입력해 주세요."
        if limit_price <= 0:
            return None, "지정가를 입력해 주세요."
        tick = _tick_size(limit_price)
        if limit_price % tick != 0:
            return None, f"이 가격대의 호가 단위는 {tick:,}원이에요. 호가 단위에 맞춰 입력해 주세요."

    return {'client_key': client_key, 'stock_code': stock_code, 'order_type': order_type,
            'qty': qty, 'qty_pct': qty_pct, 'limit_price': limit_price}, None


@manual_buy_bp.route("", methods=['GET'], strict_slashes=False)
@require_auth
def list_orders():
    denied = _require_worker()
    if denied:
        return denied
    try:
        limit = min(max(int(request.args.get('limit', 30)), 1), 100)
    except (TypeError, ValueError):
        return ApiResponse.error("limit 이 올바르지 않습니다.", status=400)
    try:
        manualBuyDaoImpl.expire_stale(g.db, g.current_user_id)
        rows = manualBuyDaoImpl.select_list(g.db, g.current_user_id, limit)
        return ApiResponse.success([_jsonable(r) for r in rows])
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("수동 매수 내역을 불러오지 못했습니다.")


@manual_buy_bp.route("", methods=['POST'], strict_slashes=False)
@require_auth
def create_order():
    denied = _require_worker()
    if denied:
        return denied
    order, error = _parse_order(request.get_json(silent=True) or {})
    if error:
        return ApiResponse.error(error, status=400)
    uid = g.current_user_id
    try:
        existing = manualBuyDaoImpl.select_by_client_key(g.db, uid, order['client_key'])
        if existing:
            return ApiResponse.success(_jsonable(existing))

        stock = manualBuyDaoImpl.select_stock(g.db, order['stock_code'])
        if not stock:
            return ApiResponse.error("종목 마스터에 없는 종목입니다.", status=400)

        try:
            manualBuyDaoImpl.insert(g.db, uid, order['client_key'], order['stock_code'],
                                    stock.get('stock_name') or '', order['order_type'],
                                    order['limit_price'], order['qty'], order['qty_pct'])
        except IntegrityError:
            # 같은 키의 동시 요청 — 먼저 들어간 주문을 돌려준다
            g.db.rollback()
        row = manualBuyDaoImpl.select_by_client_key(g.db, uid, order['client_key'])
        return ApiResponse.success(_jsonable(row))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("매수 요청을 저장하지 못했습니다.")


@manual_buy_bp.route("/<int:order_id>/cancel", methods=['POST'])
@require_auth
def cancel_order(order_id):
    denied = _require_worker()
    if denied:
        return denied
    uid = g.current_user_id
    try:
        if not (manualBuyDaoImpl.cancel_requested_order(g.db, uid, order_id)
                or manualBuyDaoImpl.request_open_cancel(g.db, uid, order_id)):
            return ApiResponse.error("지금은 취소할 수 없는 주문입니다.", status=400)
        return ApiResponse.success(_jsonable(manualBuyDaoImpl.select_by_id(g.db, uid, order_id)))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("주문을 취소하지 못했습니다.")
