"""
router_strategy.py — 매매전략 셋업 및 백테스트

엔드포인트 (url_prefix = /api/v1/strategy):
    GET   /options              전략 파라미터 조회 (s1_* 컬럼)
    PATCH /options              전략 파라미터 수정 (변경분만, flat key-value)
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

from app.domains.dao.masterStockDao import MasterStockDao
from app.domains.dao.tradeCandleDataDao import TradeCandleDataDao
from app.domains.dao.userOptionsDao import UserOptionsDao
from app.domains.vo.UserOptionMeta import UserOptionMeta
from app.ext_services.kis.KisEngine import KisEngine
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse
from app.services.kis.KisBacktester import KisBacktester
from app.services.kis.KisStockService import KisStockService
from app.services.strategy.backtestService import BacktestService

logging.basicConfig(level=logging.ERROR)

strategy_bp        = Blueprint('strategy', __name__)
userOptionsDaoImpl = UserOptionsDao()
candleDaoImpl      = TradeCandleDataDao()
masterStockDaoImpl = MasterStockDao()
backtestSvc        = BacktestService()
kisStockSvc        = KisStockService()
kisBacktester      = KisBacktester()
kisEngine          = KisEngine(virtual=False)

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
    's1_trail_basis':          'varchar',
    's1_trail_activate_pct':   'decimal',
    's1_k_trail_atr':          'decimal',
    's1_trail_floor_pct':      'decimal',
    's1_time_stop_extend':     'tinyint',
    's1_time_stop_band':       'decimal',
    's1_time_stop_grace':      'int',
    's1_max_hold_bars_hard':   'int',
    's1_obv_dead_min_bars':    'int',
}


# ─────────────────────────────────────────────────────────────────────
# 유효성 검증
# ─────────────────────────────────────────────────────────────────────
def _error(code: str, message: str, status: int = 400):
    """code 포함 에러 응답."""
    from flask import Response
    import simplejson as json
    return Response(
        json.dumps({'success': False, 'error': {'code': code, 'message': message}},
                   ensure_ascii=False),
        status=status,
        content_type='application/json; charset=utf-8',
    )


def _validate_s1_body(body: dict):
    """
    PATCH body 검증.
    - 알 수 없는 key → 400 INVALID_FIELD
    - 타입 불일치   → 400 INVALID_FIELD
    반환: (정제된 dict, None) 또는 (None, error_response)
    """
    clean: dict = {}
    for k, v in body.items():
        col_type = _S1_COLS.get(k)
        if col_type is None:
            return None, _error('INVALID_FIELD', f'허용되지 않는 필드입니다: {k}')

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

        elif col_type == 'varchar':
            if k == 's1_trail_basis' and v not in ('close', 'high'):
                return None, _error('INVALID_FIELD', 's1_trail_basis 는 close 또는 high 이어야 합니다.')
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
    try:
        data = userOptionsDaoImpl.select_s1_options(g.db, g.current_user_id)
        return ApiResponse.success(data)
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

    clean, err = _validate_s1_body(body)
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

            from app.domains.vo.UserCoinInfo import UserCoinInfo
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
