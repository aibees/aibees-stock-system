"""
router_user_options.py — 개인설정 조회 / 수정

엔드포인트 (Blueprint url_prefix = /api/v1):
    GET   /user-options   설정 조회 (본인 데이터, JWT에서 user_id 추출)
    PATCH /user-options   설정 수정 (변경된 항목만 body에 포함)

보안 핵심:
    - user_id 는 클라이언트가 절대 보내지 않는다.
    - 서버가 JWT 에서 user_id 를 추출해 본인 데이터만 처리한다.
    - 화이트리스트에 없는 컬럼은 무시 또는 400 반환.
    - vol_limit / vol_surge 는 user_id=1(관리자)에게만 허용.

대상 테이블 / 컬럼:
    user_master  : user_phone, email
    user_detail  : kis_id, kis_account, kis_access_key, kis_secret_key, tele_bot_id, tele_chat_id
    user_options : stock_sell_mail_flag, stock_buy_target_mail_flag, stock_sell_tele_flag,
                   s1_* (전략 파라미터), (vol_limit, vol_surge — 관리자 전용)
"""

import logging
from flask import Blueprint, g

from app.domains.dao.userOptionsDao import UserOptionsDao
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

logging.basicConfig(level=logging.ERROR)

user_options_bp = Blueprint("user_options", __name__)
userOptionsDaoImpl = UserOptionsDao()

# 관리자 user_id
ADMIN_USER_ID = 1

# 화이트리스트 — 테이블별 허용 컬럼
WHITELIST = {
    'user_master': {'user_phone', 'email'},
    'user_detail': {'kis_id', 'kis_account', 'kis_access_key', 'kis_secret_key', 'tele_bot_id', 'tele_chat_id'},
    'user_options': {
        'stock_sell_mail_flag', 'stock_buy_target_mail_flag', 'stock_sell_tele_flag',
        's1_stop_loss_pct', 's1_take_profit_pct', 's1_max_hold_bars',
        's1_rsi_overbought', 's1_rsi_ideal_low', 's1_rsi_ideal_high',
        's1_vol_ma_window', 's1_vol_ma_mult', 's1_regime_window', 's1_regime_threshold',
        's1_strict_need_macd_up', 's1_loose_need_vol_surge', 's1_surge_relax_mult',
        's1_downtrend_surge_bypass', 's1_surge_bypass_mult', 's1_use_trailing',
        's1_trail_activate_pct', 's1_k_trail_atr', 's1_trail_floor_pct',
        's1_trail_drawdown_pct', 's1_trail_dual',
        's1_time_stop_extend', 's1_time_stop_band', 's1_time_stop_grace',
        's1_max_hold_bars_hard', 's1_obv_dead_min_bars',
        # 관리자 전용
        'vol_limit', 'vol_surge',
    },
}

# 관리자 전용 컬럼
ADMIN_ONLY_COLUMNS = {'vol_limit', 'vol_surge'}


# ===============================================================================
# 유효성 검증 헬퍼
# ===============================================================================
def _validate_patch_body(body: dict, user_id: int):
    """
    PATCH body 검증.
    - 알 수 없는 최상위 key → 400
    - 화이트리스트에 없는 컬럼 → 400
    - stock_buy_target_mail_flag 값 검증
    - 관리자 전용 컬럼을 일반 사용자가 보내면 → 403
    반환: (정제된 body, None) 또는 (None, ApiResponse)
    """
    VALID_TABLES = set(WHITELIST.keys())
    is_admin = (user_id == ADMIN_USER_ID)

    for table_key in body:
        if table_key not in VALID_TABLES:
            return None, ApiResponse.error(
                f"알 수 없는 항목입니다: {table_key}", status=400
            )

        columns = body[table_key]
        if not isinstance(columns, dict):
            return None, ApiResponse.error(
                f"{table_key} 의 값은 객체여야 합니다.", status=400
            )

        for col in columns:
            if col not in WHITELIST[table_key]:
                return None, ApiResponse.error(
                    f"허용되지 않는 컬럼입니다: {table_key}.{col}", status=400
                )
            if col in ADMIN_ONLY_COLUMNS and not is_admin:
                return None, ApiResponse.error(
                    f"{col} 은 관리자만 수정할 수 있습니다.", status=403
                )

    # Y/N 플래그 컬럼 검증
    uo = body.get('user_options') or {}
    for flag_col in ('stock_sell_mail_flag', 'stock_buy_target_mail_flag', 'stock_sell_tele_flag'):
        flag = uo.get(flag_col)
        if flag is not None and flag not in ('Y', 'N'):
            return None, ApiResponse.error(
                f"{flag_col} 는 Y 또는 N 이어야 합니다.", status=400
            )

    # vol_limit 정수 검증
    vol_limit = (body.get('user_options') or {}).get('vol_limit')
    if vol_limit is not None:
        if not isinstance(vol_limit, int):
            return None, ApiResponse.error("vol_limit 은 정수여야 합니다.", status=400)

    # vol_surge 숫자 검증
    vol_surge = (body.get('user_options') or {}).get('vol_surge')
    if vol_surge is not None:
        if not isinstance(vol_surge, (int, float)):
            return None, ApiResponse.error("vol_surge 는 숫자여야 합니다.", status=400)

    return body, None


# ===============================================================================
# 1. 조회
#    GET /api/v1/user-options
# ===============================================================================
@user_options_bp.route("/user-options", methods=['GET'])
@require_auth
def get_user_options():
    try:
        is_admin = (g.current_user_id == ADMIN_USER_ID)
        data = userOptionsDaoImpl.select_user_settings(g.db, g.current_user_id, is_admin)
        return ApiResponse.success(data)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ===============================================================================
# 2. 수정 (변경된 항목만)
#    PATCH /api/v1/user-options
# ===============================================================================
@user_options_bp.route("/user-options", methods=['PATCH'])
@require_auth
def patch_user_options():
    from flask import request
    body = request.get_json(silent=True) or {}

    if not body:
        return ApiResponse.error("변경할 항목이 없습니다.", status=400)

    clean_body, err_response = _validate_patch_body(body, g.current_user_id)
    if err_response:
        return err_response

    is_admin = (g.current_user_id == ADMIN_USER_ID)

    try:
        if 'user_master' in clean_body:
            userOptionsDaoImpl.update_user_master(
                g.db, g.current_user_id, clean_body['user_master']
            )

        if 'user_detail' in clean_body:
            userOptionsDaoImpl.update_user_detail(
                g.db, g.current_user_id, clean_body['user_detail']
            )

        if 'user_options' in clean_body:
            userOptionsDaoImpl.upsert_user_options(
                g.db, g.current_user_id, clean_body['user_options'], is_admin
            )

        g.db.commit()
        return ApiResponse.success({'updated': True})

    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))
