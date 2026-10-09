"""
router_auto_trade.py — 운용모드 관리 (Blueprint url_prefix = /api/v1/auto-trade)

    GET /modes     모드 목록 + selectable(지금 worker 가 실제로 돌릴 수 있는 모드인지)
    GET /state     내 현재 운용모드 + worker 보유 포지션
    PUT /state     운용모드 즉시 전환        body: { "mode_code": "M0" }
    GET /history   운용모드 변경 이력        ?limit=30

설계 메모:
    - user_id 는 JWT 에서만 얻는다. 매매 사용자(WORKER_USER) 권한이 있어야 한다.
    - worker 는 active_mode 만 읽는다(평일 08~20시 설정 폴링 60초, 그 외엔 다음 개장 루틴 직전 반영).
      보유분 청산 후 승계(pending)는 worker 에 구현이 없어 쓰지 않는다 — 전환은 항상 즉시.
    - M0 = 매매정지(worker 는 켜둔 채 주문만 차단, sql/27). enabled_flag 는 worker 가 읽지 않지만
      화면 표시(운용 중/정지)가 실제와 맞도록 M0 이면 'N', 그 외 'Y' 로 함께 맞춘다.
    - SELECTABLE_MODES: worker 에 실행기가 구현된 모드만. M2~M4 는 화면에 "준비 중"으로만 보인다.
      worker 에 모드가 추가되면 여기에도 추가한다(py-stock-batch trade_worker/modes, position_strategy).
"""
import logging

from flask import Blueprint, g, request

from app.domains.dao.roleMenuDao import RoleMenuDao
from app.domains.dao.tradeModeDao import TradeModeDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

auto_trade_bp = Blueprint("auto_trade", __name__)
tradeModeDaoImpl = TradeModeDao()
roleMenuDaoImpl = RoleMenuDao()

WORKER_AUTH_ID = 'WORKER_USER'
HALT_MODE = 'M0'
SELECTABLE_MODES = ('M0', 'M1')


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

        enabled = 'N' if mode_code == HALT_MODE else 'Y'
        tradeModeDaoImpl.apply_mode(g.db, g.current_user_id, mode_code, enabled)
        reason = ('매매정지' if mode_code == HALT_MODE
                  else ('매매 재개' if from_mode == HALT_MODE else '운용모드 전환'))
        tradeModeDaoImpl.insert_change_log(g.db, g.current_user_id, 'APPLY_NOW',
                                           from_mode, mode_code, reason)
        message = (f"'{name}'로 전환했어요. 1분 안에 주문이 멈추고, 계좌 조회만 계속합니다."
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
