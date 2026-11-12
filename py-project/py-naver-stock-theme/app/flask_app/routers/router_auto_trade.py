"""
router_auto_trade.py — 운용모드 관리 (Blueprint url_prefix = /api/v1/auto-trade)

    GET /modes     모드 목록 + selectable(지금 worker 가 실제로 돌릴 수 있는 모드인지)
    GET /state     내 현재 운용모드 + worker 보유 포지션
    PUT /state     운용모드 즉시 전환        body: { "mode_code": "HALT" }
    GET /history   운용모드 변경 이력        ?limit=30
    POST /sell-now 지금 팔기(보유 전량 시장가) body: { "stock_code": "005930" }

⚠ 프록시 주의 (2026-10-11):
    py-stock-batch 도 매도 수기등록 blueprint 를 갖고 있다. 그 쪽이 이 prefix
    (`/api/v1/auto-trade`)에 등록돼 있던 동안, nginx 의
    `location ^~ /api/v1/auto-trade { proxy_pass ...stock-batch-flask-app:5557; }`
    가 `^~ /api/` 보다 우선해서 아래 3개 엔드포인트가 전부 404 였다 — 앱의
    "운용방식 설정"·"운용 현황" 화면이 통째로 죽어 있었는데, 매도 수기등록만
    batch 소관이라 정상이어서 서버 장애로 보이지 않았다.
    batch 쪽을 `/api/v1/manual-sell` 로 옮겨 해결했다(stock-vue/conf.d/http.conf).
    **이 prefix 를 batch 앱으로 보내는 location 블록을 다시 만들지 말 것.**

설계 메모:
    - user_id 는 JWT 에서만 얻는다. 매매 사용자(WORKER_USER) 권한이 있어야 한다.
    - worker 는 active_mode 만 읽는다(평일 08~20시 설정 폴링 60초, 그 외엔 다음 개장 루틴 직전 반영).
      보유분 청산 후 승계(pending)는 worker 에 구현이 없어 쓰지 않는다 — 전환은 항상 즉시.
    - HALT = 매매정지(sql/27, 2026-10-11 개정): 신규 매수만 멈추고 보유분 매도(손절·익절·트레일링)는 계속한다.
      worker 가 여전히 돌고 매도도 하므로 enabled_flag 는 모드와 무관하게 'Y' 로 둔다(worker 는 이 값을 읽지 않는다).
    - SELECTABLE_MODES: worker 에 실행기가 구현된 모드만. ETF_SWITCH 등 나머지는 화면에 "준비 중"으로만 보인다.
      worker 에 모드가 추가되면 여기에도 추가한다(py-stock-batch trade_worker/modes, position_strategy).
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import Blueprint, g, request

from stock_shared import trade_mode
from app.domains.dao.roleMenuDao import RoleMenuDao
from app.domains.dao.manualSellDao import SELL_NOW_MEMO, SELL_NOW_PRICE, ManualSellDao
from app.domains.dao.tradeModeDao import TradeModeDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

auto_trade_bp = Blueprint("auto_trade", __name__)
tradeModeDaoImpl = TradeModeDao()
roleMenuDaoImpl = RoleMenuDao()
manualSellDaoImpl = ManualSellDao()

KST = timezone(timedelta(hours=9))
WORKER_AUTH_ID = 'WORKER_USER'
HALT_MODE = trade_mode.HALT
SELECTABLE_MODES = (trade_mode.HALT, trade_mode.RECO)


def _require_worker():
    """매매 사용자가 아니면 403 응답, 맞으면 None."""
    if WORKER_AUTH_ID not in roleMenuDaoImpl.select_user_auth_ids(g.db, g.current_user_id):
        return ApiResponse.error("자동매매 사용자만 이용할 수 있습니다.", status=403)
    return None


@auto_trade_bp.route("/modes", methods=['GET'])
@require_auth
def get_modes():
    denied = _require_worker()
    if denied:
        return denied
    try:
        modes = tradeModeDaoImpl.select_modes(g.db)
        for m in modes:
            m['selectable'] = m['mode_code'] in SELECTABLE_MODES
            m['is_halt'] = m['mode_code'] == HALT_MODE
        return ApiResponse.success(modes)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("운용모드 목록을 불러오지 못했습니다.")


@auto_trade_bp.route("/state", methods=['GET'])
@require_auth
def get_state():
    denied = _require_worker()
    if denied:
        return denied
    try:
        state = tradeModeDaoImpl.select_state(g.db, g.current_user_id) or {
            'active_mode': None, 'active_from': None, 'enabled_flag': 'N', 'run_state': 'IDLE',
            'pending_mode': None, 'last_tick_at': None, 'last_message': None, 'updated_at': None,
        }
        positions = tradeModeDaoImpl.select_holding_positions(g.db, g.current_user_id)
        state['positions'] = positions
        state['position'] = positions[0] if positions else None   # 대시보드/운용현황 하위호환(1포지션)
        state['trading'] = bool(state.get('active_mode')) and state['active_mode'] != HALT_MODE
        return ApiResponse.success(state)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("운용 상태를 불러오지 못했습니다.")


@auto_trade_bp.route("/state", methods=['PUT'])
@require_auth
def put_state():
    denied = _require_worker()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    mode_code = str(body.get('mode_code') or '').strip().upper()
    if not mode_code:
        return ApiResponse.error("mode_code 가 필요합니다.", status=400)
    try:
        modes = {m['mode_code']: m for m in tradeModeDaoImpl.select_modes(g.db)}
        if mode_code not in modes:
            return ApiResponse.error("존재하지 않는 운용모드입니다.", status=400)
        if mode_code not in SELECTABLE_MODES:
            return ApiResponse.error("아직 준비 중인 운용모드입니다.", status=400)

        current = tradeModeDaoImpl.select_state(g.db, g.current_user_id) or {}
        from_mode = current.get('active_mode')
        name = modes[mode_code]['mode_name']
        if from_mode == mode_code:
            return ApiResponse.success({'applied': 'NONE', 'active_mode': mode_code,
                                        'message': f"이미 '{name}' 모드입니다."})

        # HALT 도 보유분 매도는 계속 돌므로 '운용 중'(Y) 이다.
        tradeModeDaoImpl.apply_mode(g.db, g.current_user_id, mode_code, 'Y')
        reason = ('매매정지' if mode_code == HALT_MODE
                  else ('매매 재개' if from_mode == HALT_MODE else '운용모드 전환'))
        tradeModeDaoImpl.insert_change_log(g.db, g.current_user_id, 'APPLY_NOW',
                                           from_mode, mode_code, reason)
        message = (f"'{name}'로 전환했어요. 1분 안에 신규 매수가 멈추고, 보유 종목 매도는 계속합니다."
                   if mode_code == HALT_MODE else
                   f"'{name}'로 전환했어요. 1분 안에 자동매매에 반영됩니다.")
        return ApiResponse.success({'applied': 'NOW', 'active_mode': mode_code, 'message': message})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("운용모드를 바꾸지 못했습니다.")


@auto_trade_bp.route("/history", methods=['GET'])
@require_auth
def get_history():
    denied = _require_worker()
    if denied:
        return denied
    try:
        limit = max(1, min(int(request.args.get('limit', 30)), 100))
    except (TypeError, ValueError):
        limit = 30
    try:
        return ApiResponse.success(tradeModeDaoImpl.select_change_logs(g.db, g.current_user_id, limit))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("변경 이력을 불러오지 못했습니다.")


def _is_regular_session(now: datetime) -> bool:
    """정규장(평일 09:00~15:30, 시장가 세션). 휴장일은 알 수 없다 — 등록되면 다음 거래일에 팔린다."""
    if now.weekday() >= 5:
        return False
    return 9 * 60 <= now.hour * 60 + now.minute < 15 * 60 + 30


@auto_trade_bp.route("/sell-now", methods=['POST'])
@require_auth
def sell_now():
    """지갑(MyWallet.vue) 보유 카드의 '지금 팔기' — 내 보유 전량 시장가 매도 요청.

    이 서버는 주문하지 않는다. 즉시 도달하는 손절 티어를 수기등록에 넣으면 worker 가 판다(manualSellDao).
    장외에 등록하면 다음 세션에 팔려 "지금 시장가"가 아니므로 정규장에만 받는다.
    같은 종목에 대기 중인 요청이 있으면 새로 만들지 않고 그 행을 돌려준다.
    """
    denied = _require_worker()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    stock_code = str(body.get('stock_code') or '').strip()
    if not stock_code:
        return ApiResponse.error("stock_code 가 필요합니다.", status=400)
    if not _is_regular_session(datetime.now(KST)):
        return ApiResponse.error("지금 팔기는 정규장(09:00~15:30)에만 할 수 있어요.", status=400)

    uid = g.current_user_id
    try:
        pending = manualSellDaoImpl.select_order_by_memo(g.db, uid, stock_code, SELL_NOW_MEMO)
        if pending:
            return ApiResponse.success(pending)
        holding = manualSellDaoImpl.select_holding(g.db, uid, stock_code)
        if not holding or Decimal(str(holding.get('qty') or 0)) <= 0:
            return ApiResponse.error("계좌에 보유 수량이 없는 종목입니다.", status=400)
        new_id = manualSellDaoImpl.insert(g.db, uid, stock_code, holding.get('stock_name'), SELL_NOW_PRICE,
                                          'DOWN', 1, holding['qty'], 'Y', SELL_NOW_MEMO)
        return ApiResponse.success(manualSellDaoImpl.select_order(g.db, uid, new_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("매도 요청을 저장하지 못했습니다.")
