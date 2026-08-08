"""
router_strategy.py — 매매전략 셋업 및 백테스트

엔드포인트 (url_prefix = /api/v1/strategy):
    GET   /options              전략 파라미터 조회 (s1_* 컬럼)
    PATCH /options              전략 파라미터 수정 (변경분만, flat key-value)
    GET   /param-guide          파라미터 조정 화면 메타(master_strategy_param)
    POST  /param-guide          메타 등록   (관리자)
    PATCH /param-guide/<key>    메타 수정   (관리자)
    DELETE/param-guide/<key>    메타 삭제   (관리자)
    POST  /backtest             단일 종목 백테스트 (구 버전 — StockModService 기반)
    POST  /backtest/ingest      KIS 지표 계산 + trade_candle_data UPSERT
    POST  /backtest/run         단일 종목 KisBacktester 백테스트
    POST  /backtest/run-all     전 종목 KisBacktester 집계
    GET   /candle               trade_candle_data 조회

보안:
    - user_id 는 클라이언트가 보내지 않음. JWT 에서 추출.
    - s1_* 화이트리스트 외 key → 400 INVALID_FIELD
    - backtest 기간 제한: start_date >= 오늘 - 200일, end_date <= 오늘
"""
from __future__ import annotations

import logging
import pandas as pd
from datetime import datetime, timedelta

from flask import Blueprint, g, request

from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from app.domains.dao.userOptionsDao import UserOptionsDao
from app.domains.dao.masterStrategyParamDao import MasterStrategyParamDao
from stock_shared.dto.userOptionMeta import UserOptionMeta
from app.ext_services.kis.KisEngine import KisEngine
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse
from stock_shared.strategy.backtester import KisBacktester
from stock_shared.strategy.buy_order import DEFAULT_BUY_ORDER, describe_buy_order
from stock_shared.strategy.buy_target_sim import BuyTargetSimulator
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.strategy.reco_performance import RecoPerformanceAnalyzer
from app.services.kis.KisStockService import KisStockService
from app.services.strategy.backtestService import BacktestService
from app.services.strategy.strategyParamGuideService import StrategyParamGuideService

logging.basicConfig(level=logging.ERROR)

strategy_bp        = Blueprint('strategy', __name__)
userOptionsDaoImpl = UserOptionsDao()
candleDaoImpl      = TradeCandleDataDao()
masterStockDaoImpl = MasterStockDao()
backtestSvc        = BacktestService()
kisStockSvc        = KisStockService()
kisBacktester      = KisBacktester()
kisEngine          = KisEngine(virtual=False)
paramGuideSvc      = StrategyParamGuideService()
paramGuideDao      = MasterStrategyParamDao()

# 관리자 user_id — 파라미터 메타(master_strategy_param) 편집 권한
ADMIN_USER_ID = 1

# KIS 지표 적재에 필요한 UserOptionMeta 기본값
_DEFAULT_USER_INFO_FOR_INGEST = UserOptionMeta()
_DEFAULT_USER_INFO_FOR_INGEST.vol_surge        = 3.0
_DEFAULT_USER_INFO_FOR_INGEST.delay_date       = 5
_DEFAULT_USER_INFO_FOR_INGEST.macd_recent_day  = 5
_DEFAULT_USER_INFO_FOR_INGEST.bb_over_recent_day = 5

# FIELD_MAP: UserCoinInfo 속성 ↔ DataFrame 컬럼 (배치 test_5.py와 동일)
_FIELD_MAP_KIS = {
    'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close',
    'volume': 'volume', 'vol_surge_n': 'vol_surge_n', 'datetime': 'datetime',
    'ema20': 'ema20', 'ema60': 'ema60', 'ema120': 'ema120',
    'bb_mid': 'bb_mid', 'bb_lower': 'bb_lower', 'bb_lower_chk': 'bb_lower_chk',
    'bb_upper': 'bb_upper', 'bb_upper_chk': 'bb_upper_chk',
    'bb_width': 'bb_width', 'bb_width_avg': 'bb_width_avg',
    'bb_mid_breakout': 'bb_mid_breakout', 'recent_high': 'recent_high',
    'macd': 'macd', 'macd_s': 'macd_s',
    'macd_lower_mean': 'macd_lower_mean', 'macd_upper_mean': 'macd_upper_mean',
    'macd_recent_min': 'macd_recent_min', 'macd_recent_max': 'macd_recent_max',
    'macd_g_cross_n': 'macd_g_cross_n', 'macd_d_cross_n': 'macd_d_cross_n',
    'obv': 'obv', 'obv_signal': 'obv_signal',
    'obv_g_cross_n': 'obv_g_cross_n', 'obv_d_cross_n': 'obv_d_cross_n',
    'rsi': 'rsi', 'atr': 'atr',
}

# ─────────────────────────────────────────────────────────────────────
# 컬럼 메타 (col → type)
# ─────────────────────────────────────────────────────────────────────
_S1_COLS: dict[str, str] = {
    's1_stop_loss_pct':        'decimal',
    's1_take_profit_pct':      'decimal',
    's1_max_hold_bars':        'int',
    's1_rsi_overbought':       'int',
    's1_rsi_ideal_low':        'int',
    's1_rsi_ideal_high':       'int',
    's1_vol_ma_window':        'int',
    's1_vol_ma_mult':          'decimal',
    's1_regime_window':        'int',
    's1_regime_threshold':     'decimal',
    's1_strict_need_macd_up':  'tinyint',
    's1_loose_need_vol_surge': 'tinyint',
    's1_surge_relax_mult':     'decimal',
    's1_downtrend_surge_bypass': 'tinyint',
    's1_surge_bypass_mult':    'decimal',
    's1_use_trailing':         'tinyint',
    's1_trail_activate_pct':   'decimal',
    's1_k_trail_atr':          'decimal',
    's1_trail_floor_pct':      'decimal',
    's1_trail_drawdown_pct':   'decimal',
    's1_trail_giveback_pct':   'decimal',
    's1_trail_dual':           'tinyint',
    's1_trail_fib_use':        'tinyint',
    's1_trail_fib_level':      'fib_level',
    's1_time_stop_extend':     'tinyint',
    's1_time_stop_band':       'decimal',
    's1_time_stop_grace':      'int',
    's1_max_hold_bars_hard':   'int',
    's1_obv_dead_min_bars':    'int',
    # ── 매수 필터 on/off · core 진입신호 mode ──
    's1_enable_macd_filter':     'tinyint',
    's1_enable_rsi_filter':      'tinyint',
    's1_enable_bb_upper_filter': 'tinyint',
    's1_enable_vol_avg_filter':  'tinyint',
    's1_enable_regime_gate':     'tinyint',
    's1_macd_signal_mode':       'signal_mode',
    's1_obv_signal_mode':        'signal_mode',
    # ── worker 매수타겟 정렬 (개인화) ──
    's1_buy_order':              'buy_order',
}

# core 진입신호 mode 허용값
_SIGNAL_MODES = ('off', 'golden', 'slope')

# 피보나치 되돌림 트레일 허용 비율 (자유 입력 아님, 3개 프리셋만 허용)
_FIB_LEVELS = (0.382, 0.5, 0.618)

# ─────────────────────────────────────────────────────────────────────
# 권한 분리 — 어디서 소비되는 값인가로 갈린다
#
#  [관리자 전용] 매수 전략 파라미터
#     KospiStrategy1.get_action_in_watch 가 쓰고, 이를 호출하는
#     StockBuyCheckJob 은 get_user_options(session) 를 user_id 없이 부른다(=user_id 1).
#     산출물 trade_buy_target_stock 은 **전 유저 공용 추천 테이블**이다.
#     → 일반 유저가 바꿔도 자기 화면엔 반영되지 않고(공용 테이블이라),
#       관리자가 바꾸면 전원에게 영향이 간다. 개인화가 성립하지 않는 값들.
#
#  [개인화] 그 외 (매도 파라미터 전체 + s1_buy_order)
#     worker(SellStrategy / BuyExecutor)가 user_id 별로 읽어 쓴다. 서로 간섭 없음.
# ─────────────────────────────────────────────────────────────────────
_S1_ADMIN_ONLY_COLS = frozenset({
    's1_rsi_overbought', 's1_rsi_ideal_low', 's1_rsi_ideal_high',
    's1_vol_ma_window', 's1_vol_ma_mult',
    's1_regime_window', 's1_regime_threshold',
    's1_strict_need_macd_up', 's1_loose_need_vol_surge', 's1_surge_relax_mult',
    's1_downtrend_surge_bypass', 's1_surge_bypass_mult',
    's1_enable_macd_filter', 's1_enable_rsi_filter', 's1_enable_bb_upper_filter',
    's1_enable_vol_avg_filter', 's1_enable_regime_gate',
    's1_macd_signal_mode', 's1_obv_signal_mode',
})

# s1_buy_order 허용 필드 — trade_worker/repository.py _ORDER_FIELDS 와 동일해야 한다.
# (worker 는 모르는 필드를 조용히 무시하지만, 저장 시점에 걸러야 사용자가 오타를 안다)
_BUY_ORDER_FIELDS = ('score', 'volume', 'rate', 'rank_no', 'close')
_BUY_ORDER_DIRS = ('asc', 'desc')


def _validate_buy_order(spec: str):
    """s1_buy_order 문법 검증. 반환 (정규화된 spec, 에러메시지|None).

    worker 는 오타를 무시하고 기본값으로 돌지만, 그러면 사용자는 저장이 됐는데
    왜 안 먹는지 알 수 없다. 저장 단계에서 막아 그 혼란을 없앤다.
    """
    parts = []
    seen = set()
    for token in spec.split(','):
        token = token.strip()
        if not token:
            continue
        field, _, direction = token.partition(':')
        field = field.strip().lower()
        direction = direction.strip().lower()
        if field not in _BUY_ORDER_FIELDS:
            return None, f'정렬 필드가 올바르지 않습니다: {field} (허용: {", ".join(_BUY_ORDER_FIELDS)})'
        if direction and direction not in _BUY_ORDER_DIRS:
            return None, f'정렬 방향은 asc 또는 desc 여야 합니다: {field}:{direction}'
        if field in seen:
            return None, f'정렬 필드가 중복되었습니다: {field}'
        seen.add(field)
        parts.append(f'{field}:{direction}' if direction else field)

    if not parts:
        return None, '정렬 항목이 비어 있습니다. 기본값으로 두려면 null 을 보내세요.'
    return ','.join(parts), None


# ─────────────────────────────────────────────────────────────────────
# 유효성 검증
# ─────────────────────────────────────────────────────────────────────
def _error(code: str, message: str, status: int = 400):
    """code 포함 에러 응답.

    직렬화는 ApiResponse._dumps 를 쓴다(datetime 등 공통 default 적용).
    여기서 json.dumps 를 직접 부르면 응답 계층의 직렬화 규칙을 우회하게 된다.
    """
    from flask import Response
    from app.flask_app.utils.apiResponse import _dumps
    return Response(
        _dumps({'success': False, 'error': {'code': code, 'message': message}}),
        status=status,
        content_type='application/json; charset=utf-8',
    )


def _validate_s1_body(body: dict, is_admin: bool = False):
    """
    PATCH body 검증.
    - 알 수 없는 key       → 400 INVALID_FIELD
    - 타입 불일치          → 400 INVALID_FIELD
    - 관리자 전용 key      → 403 FORBIDDEN (is_admin=False 일 때)
    반환: (정제된 dict, None) 또는 (None, error_response)
    """
    clean: dict = {}
    for k, v in body.items():
        col_type = _S1_COLS.get(k)
        if col_type is None:
            return None, _error('INVALID_FIELD', f'허용되지 않는 필드입니다: {k}')

        # 공용 매수타겟에 영향을 주는 값은 관리자만 바꿀 수 있다.
        if k in _S1_ADMIN_ONLY_COLS and not is_admin:
            return None, _error(
                'FORBIDDEN',
                f'{k} 는 전체 매수타겟 생성에 적용되는 값이라 관리자만 변경할 수 있습니다.',
                status=403,
            )

        if v is None:
            clean[k] = None
            continue

        if col_type == 'tinyint':
            if v not in (0, 1):
                return None, _error('INVALID_FIELD', f'{k} 는 0 또는 1 이어야 합니다.')
            clean[k] = int(v)

        elif col_type == 'int':
            if not isinstance(v, int) or isinstance(v, bool):
                return None, _error('INVALID_FIELD', f'{k} 는 정수여야 합니다.')
            clean[k] = v

        elif col_type == 'decimal':
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return None, _error('INVALID_FIELD', f'{k} 는 숫자여야 합니다.')
            clean[k] = float(v)

        elif col_type == 'fib_level':
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return None, _error('INVALID_FIELD', f'{k} 는 숫자여야 합니다.')
            if not any(abs(fv - lvl) < 1e-6 for lvl in _FIB_LEVELS):
                return None, _error(
                    'INVALID_FIELD',
                    f'{k} 는 {" / ".join(str(l) for l in _FIB_LEVELS)} 중 하나여야 합니다.')
            clean[k] = fv

        elif col_type == 'signal_mode':
            if v not in _SIGNAL_MODES:
                return None, _error(
                    'INVALID_FIELD',
                    f'{k} 는 {" / ".join(_SIGNAL_MODES)} 중 하나여야 합니다.')
            clean[k] = str(v)

        elif col_type == 'buy_order':
            if not isinstance(v, str):
                return None, _error('INVALID_FIELD', f'{k} 는 문자열이어야 합니다.')
            normalized, err_msg = _validate_buy_order(v)
            if err_msg:
                return None, _error('INVALID_FIELD', err_msg)
            clean[k] = normalized

        elif col_type == 'varchar':
            clean[k] = str(v)

    return clean, None


def _validate_backtest_body(body: dict):
    """POST /backtest body 검증."""
    stock_code = body.get('stock_code')
    start_date = body.get('start_date')
    end_date   = body.get('end_date')

    if not stock_code or not isinstance(stock_code, str):
        return None, None, None, _error('INVALID_FIELD', 'stock_code 가 필요합니다.')
    if not start_date or not end_date:
        return None, None, None, _error('INVALID_FIELD', 'start_date, end_date 가 필요합니다.')

    try:
        sd = datetime.strptime(start_date, '%Y-%m-%d')
        ed = datetime.strptime(end_date,   '%Y-%m-%d')
    except ValueError:
        return None, None, None, _error('INVALID_FIELD', '날짜 형식은 YYYY-MM-DD 이어야 합니다.')

    today     = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    min_start = today - timedelta(days=200)

    # if sd < min_start:
    #     return None, None, None, _error(
    #         'INVALID_RANGE', '테스트 기간은 오늘로부터 200일 이내만 가능합니다.'
    #     )
    if ed > today:
        return None, None, None, _error(
            'INVALID_RANGE', 'end_date 는 오늘 이후일 수 없습니다.'
        )
    if sd > ed:
        return None, None, None, _error(
            'INVALID_RANGE', 'start_date 는 end_date 보다 앞이어야 합니다.'
        )

    return stock_code, start_date, end_date, None


# ═══════════════════════════════════════════════════════════════════
# 1. 전략 파라미터 조회
#    GET /api/v1/strategy/options
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/options', methods=['GET'])
@require_auth
def get_strategy_options():
    """s1_* 전체를 반환하되, 편집 권한 메타를 함께 내려준다.

    화면(BuySetting.vue)은 admin_only 목록으로 필드를 read-only 처리한다.
    값 자체는 비관리자도 볼 수 있다 — 어떤 조건으로 타겟이 뽑혔는지는
    알아야 정렬 기준을 정할 수 있기 때문.
    """
    try:
        data = userOptionsDaoImpl.select_s1_options(g.db, g.current_user_id) or {}
        is_admin = (g.current_user_id == ADMIN_USER_ID)
        return ApiResponse.success({
            **data,
            '_meta': {
                'is_admin': is_admin,
                'admin_only_fields': sorted(_S1_ADMIN_ONLY_COLS),
                'buy_order_fields': list(_BUY_ORDER_FIELDS),
            },
        })
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2. 전략 파라미터 수정 (변경분만)
#    PATCH /api/v1/strategy/options
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/options', methods=['PATCH'])
@require_auth
def patch_strategy_options():
    body = request.get_json(silent=True) or {}
    if not body:
        return ApiResponse.error('변경할 항목이 없습니다.', status=400)

    clean, err = _validate_s1_body(body, is_admin=(g.current_user_id == ADMIN_USER_ID))
    if err:
        return err

    try:
        userOptionsDaoImpl.upsert_s1_options(g.db, g.current_user_id, clean)
        g.db.commit()
        return ApiResponse.success({'updated': True})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-1. 파라미터 조정 화면 메타 조회
#      GET /api/v1/strategy/param-guide?strategy_code=S1
#
#      Vue(TradeSetting.vue)가 이 응답만으로 카드/필드를 렌더링한다.
#      화면에 하드코딩된 GROUPS 상수를 대체하는 엔드포인트.
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/param-guide', methods=['GET'])
@require_auth
def get_param_guide():
    strategy_code = request.args.get('strategy_code', 'S1')
    # 관리자는 enabled_flag='N' 항목까지 볼 수 있다(메타 관리용).
    include_disabled = (
        g.current_user_id == ADMIN_USER_ID
        and request.args.get('include_disabled') == 'Y'
    )
    try:
        data = paramGuideSvc.get_guide(g.db, strategy_code, include_disabled)
        return ApiResponse.success(data)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-2. 메타 등록 (관리자)
#      POST /api/v1/strategy/param-guide
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/param-guide', methods=['POST'])
@require_auth
def post_param_guide():
    if g.current_user_id != ADMIN_USER_ID:
        return _error('FORBIDDEN', '관리자만 수정할 수 있습니다.', status=403)

    body = request.get_json(silent=True) or {}
    body.setdefault('strategy_code', 'S1')

    err_msg = paramGuideSvc.validate(body, for_insert=True)
    if err_msg:
        return _error('INVALID_FIELD', err_msg)

    try:
        exists = paramGuideDao.select_one(g.db, body['strategy_code'], body['param_key'])
        if exists is not None:
            return _error('DUPLICATE', f"이미 존재하는 param_key 입니다: {body['param_key']}", status=409)

        paramGuideDao.insert_param(g.db, body)
        g.db.commit()
        return ApiResponse.success({'created': True, 'param_key': body['param_key']})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-3. 메타 수정 (관리자) — 넘어온 컬럼만
#      PATCH /api/v1/strategy/param-guide/<param_key>?strategy_code=S1
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/param-guide/<param_key>', methods=['PATCH'])
@require_auth
def patch_param_guide(param_key):
    if g.current_user_id != ADMIN_USER_ID:
        return _error('FORBIDDEN', '관리자만 수정할 수 있습니다.', status=403)

    body = request.get_json(silent=True) or {}
    if not body:
        return _error('INVALID_FIELD', '변경할 항목이 없습니다.')

    strategy_code = request.args.get('strategy_code', 'S1')

    err_msg = paramGuideSvc.validate(body, for_insert=False)
    if err_msg:
        return _error('INVALID_FIELD', err_msg)

    try:
        ok = paramGuideDao.update_param(g.db, strategy_code, param_key, body)
        if not ok:
            return _error('NOT_FOUND', f'대상을 찾을 수 없습니다: {param_key}', status=404)
        g.db.commit()
        return ApiResponse.success({'updated': True, 'param_key': param_key})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-4. 메타 삭제 (관리자)
#      DELETE /api/v1/strategy/param-guide/<param_key>?strategy_code=S1
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/param-guide/<param_key>', methods=['DELETE'])
@require_auth
def delete_param_guide(param_key):
    if g.current_user_id != ADMIN_USER_ID:
        return _error('FORBIDDEN', '관리자만 삭제할 수 있습니다.', status=403)

    strategy_code = request.args.get('strategy_code', 'S1')
    try:
        cnt = paramGuideDao.delete_param(g.db, strategy_code, param_key)
        if not cnt:
            return _error('NOT_FOUND', f'대상을 찾을 수 없습니다: {param_key}', status=404)
        g.db.commit()
        return ApiResponse.success({'deleted': True, 'param_key': param_key})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-5. worker 가 실제로 사용하는 설정만 요약
#      GET /api/v1/strategy/worker-config
#
#      user_options 의 s1_* 는 소비처가 둘로 갈린다:
#        · worker(SellStrategy/BuyExecutor) — 개인화, 내 매매에 직접 영향
#        · 매수타겟 배치(StockBuyCheckJob)  — 전 유저 공용 추천 생성
#      이 API 는 **앞쪽만** 내려준다. 시뮬레이션 화면이 "내 worker 가 지금
#      이렇게 동작한다"를 보여주는 용도라, 공용 파라미터가 섞이면 오해를 준다.
# ═══════════════════════════════════════════════════════════════════

# (키, 라벨, 표시타입, 전략 기본값)  — 기본값은 KospiStrategy1.__init__ 과 일치
_WORKER_SELL_FIELDS = [
    ('s1_stop_loss_pct',      '손절',              'pct',  0.05),
    ('s1_take_profit_pct',    '익절',              'pct',  0.30),
    ('s1_obv_dead_min_bars',  'OBV 데드크로스 무시', 'bars', 5),
    ('s1_use_trailing',       '트레일링 사용',      'bool', 1),
    ('s1_trail_activate_pct', '트레일링 활성화',    'pct',  0.08),
    ('s1_k_trail_atr',        'ATR 배수(k)',       'num',  3.0),
    ('s1_trail_drawdown_pct', '고점 대비 하락',     'pct',  None),
    ('s1_trail_giveback_pct', '이익 반납',          'pct',  None),
    ('s1_trail_dual',         'ATR 이중감시',       'bool', 1),
    ('s1_trail_fib_use',      '피보나치 되돌림 사용', 'bool', 0),
    ('s1_trail_fib_level',    '되돌림 비율',        'num',  0.382),
    ('s1_max_hold_bars',      '보유 한도',          'bars', 12),
    ('s1_time_stop_extend',   '추세생존 시 연장',    'bool', 1),
    ('s1_time_stop_band',     '정체 판정 밴드',      'pct',  0.02),
    ('s1_time_stop_grace',    '신고가 grace',       'bars', 3),
    ('s1_max_hold_bars_hard', '절대 보유 한도',      'bars', 20),
]


@strategy_bp.route('/worker-config', methods=['GET'])
@require_auth
def get_worker_config():
    try:
        opts = userOptionsDaoImpl.select_s1_options(g.db, g.current_user_id) or {}

        sell = []
        for key, label, vtype, default in _WORKER_SELL_FIELDS:
            v = opts.get(key)
            sell.append({
                'key': key, 'label': label, 'type': vtype,
                'value': v, 'default': default,
                'is_default': v is None,          # NULL = 전략 클래스 기본값 사용
            })

        spec = opts.get('s1_buy_order')
        return ApiResponse.success({
            'buy': {
                'key': 's1_buy_order',
                'label': '매수 후보 우선순위',
                'value': spec,
                'applied': describe_buy_order(spec),   # 실제 적용되는 정렬(오타 보정 후)
                'is_default': not spec,
                'default': DEFAULT_BUY_ORDER,
            },
            'sell': sell,
        })
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-6. 매수추천 기반 실전 시뮬레이션
#      POST /api/v1/strategy/sim/buy-target
#
#      body(전부 선택):
#        start_date "2026-04-01" / end_date "2026-08-07"
#        init_cash 1000000 / fee_rate 0.0011
#        entry_price "next_open"|"close" / skip_gapup true|false
#
#      매도 판정은 **저장된 내 s1_* 설정**을 그대로 쓴다(화면에서 조정 불가).
#      종목 선택은 s1_buy_order — worker BuyExecutor 와 동일한 정렬.
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/sim/buy-target', methods=['POST'])
@require_auth
def post_sim_buy_target():
    body = request.get_json(silent=True) or {}

    start_date = body.get('start_date')
    end_date = body.get('end_date')
    if not start_date:
        return _error('INVALID_FIELD', 'start_date 가 필요합니다.')
    for label, v in (('start_date', start_date), ('end_date', end_date)):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                return _error('INVALID_FIELD', f'{label} 형식은 YYYY-MM-DD 이어야 합니다.')
    if end_date and end_date < start_date:
        return _error('INVALID_RANGE', 'start_date 는 end_date 보다 앞이어야 합니다.')

    entry_price = body.get('entry_price', 'next_open')
    if entry_price not in ('next_open', 'close'):
        return _error('INVALID_FIELD', "entry_price 는 'next_open' 또는 'close' 여야 합니다.")

    try:
        init_cash = int(body.get('init_cash', 1_000_000))
        fee_rate = float(body.get('fee_rate', 0.0011))
    except (TypeError, ValueError):
        return _error('INVALID_FIELD', 'init_cash / fee_rate 가 숫자가 아닙니다.')
    if init_cash <= 0:
        return _error('INVALID_FIELD', 'init_cash 는 0보다 커야 합니다.')

    try:
        # 저장된 s1_* → UserOptionMeta (매도 판정 파라미터)
        ui = _build_base_user_info(g.db, g.current_user_id)
        strategy = KospiStrategy1()
        strategy.configure(ui)

        opts = userOptionsDaoImpl.select_s1_options(g.db, g.current_user_id) or {}

        sim = BuyTargetSimulator(g.db, ui, strategy=strategy)
        result = sim.run(
            start=start_date, end=end_date,
            init_cash=init_cash, fee_rate=fee_rate,
            entry_price=entry_price,
            skip_gapup=bool(body.get('skip_gapup', False)),
            buy_order=opts.get('s1_buy_order'),
        )
        return ApiResponse.success(result)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 2-7. 매수추천 이후 성과 (추천 건별)
#      GET /api/v1/strategy/reco-performance
#
#      query(전부 선택):
#        from_ymd 20260601 / to_ymd 20260806
#        days 60            from_ymd 미지정 시 최근 N일
#        horizon 20         추천일 이후 관측할 거래일 수 (0=끝까지)
#        zigzag 5           변곡점 임계 % (0=계산 안 함)
#
#      같은 종목이 여러 번 추천됐으면 **추천일마다 별도 행**으로 나온다.
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/reco-performance', methods=['GET'])
@require_auth
def get_reco_performance():
    args = request.args

    from_ymd = args.get('from_ymd')
    to_ymd = args.get('to_ymd')
    if not from_ymd:
        try:
            days = int(args.get('days', 60))
        except ValueError:
            return _error('INVALID_FIELD', 'days 는 정수여야 합니다.')
        from_ymd = (datetime.today() - timedelta(days=days)).strftime('%Y%m%d')

    for label, v in (('from_ymd', from_ymd), ('to_ymd', to_ymd)):
        if v and (len(v) != 8 or not v.isdigit()):
            return _error('INVALID_FIELD', f'{label} 형식은 YYYYMMDD 이어야 합니다.')

    try:
        horizon = int(args.get('horizon', 0))
        zigzag_pct = float(args.get('zigzag', 5))
    except ValueError:
        return _error('INVALID_FIELD', 'horizon / zigzag 가 숫자가 아닙니다.')
    if horizon < 0 or zigzag_pct < 0:
        return _error('INVALID_FIELD', 'horizon / zigzag 는 0 이상이어야 합니다.')

    try:
        result = RecoPerformanceAnalyzer(g.db).run(
            from_ymd=from_ymd, to_ymd=to_ymd,
            horizon_days=horizon, zigzag_pct=zigzag_pct,
        )
        return ApiResponse.success(result)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 3. 백테스트 실행
#    POST /api/v1/strategy/backtest
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/backtest', methods=['POST'])
@require_auth
def post_backtest():
    body = request.get_json(silent=True) or {}

    stock_code, start_date, end_date, err = _validate_backtest_body(body)
    if err:
        return err
    print("stock_code : " + stock_code)
    print("start_date : " + start_date)
    print("end_date : " + end_date)
    try:
        # DB에서 사용자 s1_* 설정 로드 (없으면 None → 서비스 내부에서 기본값 적용)
        user_opts = userOptionsDaoImpl.select_s1_options(g.db, g.current_user_id)
        result    = backtestSvc.run(stock_code, start_date, end_date, user_opts)
        print(result)
        return ApiResponse.success(result)

    except ValueError as e:
        code = str(e)
        if code == 'INSUFFICIENT_DATA':
            return _error('INSUFFICIENT_DATA', '데이터가 부족합니다. 다른 종목이나 기간을 사용해 주세요.')
        return ApiResponse.error(code)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 4. KIS 지표 적재
#    POST /api/v1/strategy/backtest/ingest
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/backtest/ingest', methods=['POST'])
@require_auth
def post_backtest_ingest():
    """
    body: { end_date: "YYYY-MM-DD", lookback_days?: int, stock_codes?: [str] }
    OHLCV → compute_indicator_df → trade_candle_data UPSERT
    """
    body        = request.get_json(silent=True) or {}
    end_date    = body.get('end_date')
    lookback    = int(body.get('lookback_days', 250))
    stock_codes = body.get('stock_codes')  # None이면 전체 종목

    if not end_date:
        return _error('INVALID_FIELD', 'end_date 가 필요합니다.')
    try:
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return _error('INVALID_FIELD', '날짜 형식은 YYYY-MM-DD 이어야 합니다.')

    start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback)).strftime('%Y-%m-%d')

    # 대상 종목 결정
    if stock_codes:
        stocks = [{'stock_code': c, 'stock_name': c} for c in stock_codes]
    else:
        all_stocks = masterStockDaoImpl.select_all_stocks(g.db)
        stocks = all_stocks

    results = []
    for stock in stocks:
        code = stock.get('stock_code')
        name = stock.get('stock_name', code)
        try:
            ohlcv = kisEngine.getOHLCV(code, start_date, end_date)
            if ohlcv is None or ohlcv.empty:
                results.append({'code': code, 'status': 'skip', 'reason': '데이터 없음'})
                continue

            computed = kisStockSvc.compute_indicator_df(ohlcv, _DEFAULT_USER_INFO_FOR_INGEST)
            computed.fillna(0.0, inplace=True)

            from stock_shared.vo.userCoinInfo import UserCoinInfo
            count = 0
            for row in computed.itertuples(index=False):
                ci = UserCoinInfo()
                ci.coin_code = code
                for attr, col in _FIELD_MAP_KIS.items():
                    setattr(ci, attr, getattr(row, col, 0.0))
                candleDaoImpl.upsert_candle_data_kis(g.db, ci)
                count += 1

            g.db.commit()
            results.append({'code': code, 'status': 'ok', 'rows': count})

        except Exception as e:
            g.db.rollback()
            logging.exception(e)
            results.append({'code': code, 'status': 'error', 'reason': str(e)})

    return ApiResponse.success({'start_date': start_date, 'end_date': end_date, 'results': results})


# ═══════════════════════════════════════════════════════════════════
# 5. KisBacktester 단일 종목 백테스트
#    POST /api/v1/strategy/backtest/run
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/backtest/run', methods=['POST'])
@require_auth
def post_backtest_run():
    """
    body: { coin_code: str, start_date?: str, end_date?: str, fee_rate?: float }
    trade_candle_data 조회 → KisBacktester.run_one → summary + trade_list
    """
    body      = request.get_json(silent=True) or {}
    coin_code = body.get('coin_code')
    if not coin_code:
        return _error('INVALID_FIELD', 'coin_code 가 필요합니다.')

    start_date = body.get('start_date')
    end_date   = body.get('end_date')
    fee_rate   = float(body.get('fee_rate', 0.0015))

    try:
        rows = candleDaoImpl.select_candle_data(g.db, {
            'coin_code':  coin_code,
            'start_date': start_date,
            'end_date':   end_date,
        })
        if len(rows) < 5:
            return _error('INSUFFICIENT_DATA', '데이터가 부족합니다.')

        # user options → UserOptionMeta로 s1_* override
        base_ui   = _build_base_user_info(g.db, g.current_user_id)
        backtester = KisBacktester(fee_rate=fee_rate)
        result     = backtester.run_one(coin_code, rows, base_ui)
        return ApiResponse.success(result)

    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 6. KisBacktester 전 종목 집계
#    POST /api/v1/strategy/backtest/run-all
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/backtest/run-all', methods=['POST'])
@require_auth
def post_backtest_run_all():
    """
    body: { start_date?: str, end_date?: str, fee_rate?: float }
    trade_candle_data 전 종목 조회 → 종목별 run_one → aggregate
    """
    body       = request.get_json(silent=True) or {}
    start_date = body.get('start_date')
    end_date   = body.get('end_date')
    fee_rate   = float(body.get('fee_rate', 0.0015))

    try:
        all_stocks = masterStockDaoImpl.select_all_stocks(g.db)
        base_ui    = _build_base_user_info(g.db, g.current_user_id)
        backtester = KisBacktester(fee_rate=fee_rate)

        individual = []
        for stock in all_stocks:
            code = stock.get('stock_code')
            try:
                rows = candleDaoImpl.select_candle_data(g.db, {
                    'coin_code': code, 'start_date': start_date, 'end_date': end_date,
                })
                if len(rows) < 5:
                    continue
                res = backtester.run_one(code, rows, base_ui)
                individual.append(res)
            except Exception as e:
                logging.exception(e)
                continue

        summary_all = backtester.aggregate(individual)
        # 종목별 정렬: total_return 내림차순
        individual_sorted = sorted(individual, key=lambda x: x['total_return'], reverse=True)
        return ApiResponse.success({
            'aggregate': summary_all,
            'symbols': individual_sorted,
        })

    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ═══════════════════════════════════════════════════════════════════
# 7. trade_candle_data 조회
#    GET /api/v1/strategy/candle?coin=&start_date=&end_date=
# ═══════════════════════════════════════════════════════════════════
@strategy_bp.route('/candle', methods=['GET'])
@require_auth
def get_candle():
    coin       = request.args.get('coin')
    start_date = request.args.get('start_date')
    end_date   = request.args.get('end_date')

    if not coin:
        return _error('INVALID_FIELD', 'coin 파라미터가 필요합니다.')

    try:
        rows = candleDaoImpl.select_candle_data(g.db, {
            'coin_code':  coin,
            'start_date': start_date,
            'end_date':   end_date,
        })
        return ApiResponse.success({'coin': coin, 'count': len(rows), 'data': rows})
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# ──────────────────────────────────────────────────────────────────
# 내부 헬퍼: DB s1_* → UserOptionMeta
# ──────────────────────────────────────────────────────────────────
def _build_base_user_info(db_session, user_id: int) -> UserOptionMeta:
    """user_options s1_* → UserOptionMeta 에 세팅."""
    ui       = UserOptionMeta()
    s1_opts  = userOptionsDaoImpl.select_s1_options(db_session, user_id)
    if s1_opts:
        for k, v in s1_opts.items():
            if hasattr(ui, k) and v is not None:
                setattr(ui, k, v)
    return ui
