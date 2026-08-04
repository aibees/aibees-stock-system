from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.userOptions import UserOptions
from app.domains.models.userMaster import UserMaster
from app.domains.models.userDetail import UserDetail

import logging
logging.basicConfig(level=logging.ERROR)


class UserOptionsDao(BaseDao):
    model = UserOptions

    def __init__(self):
        self.__name__ = 'UserOptionsDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by user_id
    # ================================================================
    def select_by_user_id(self, session, user_id: int):
        stmt = select(UserOptions).where(UserOptions.user_id == user_id)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # ----------------------------------------------------------------
    # 개인설정 조회 — 3개 테이블 통합 (GET /api/v1/user-options)
    # ----------------------------------------------------------------
    def select_user_settings(self, session, user_id: int, is_admin: bool) -> dict:
        """user_master / user_detail / user_options 3개 테이블에서 설정 조회."""

        # user_master
        um = session.execute(
            select(UserMaster).where(UserMaster.user_id == user_id)
        ).scalars().first()

        # user_detail
        ud = session.execute(
            select(UserDetail).where(UserDetail.user_id == user_id)
        ).scalars().first()

        # user_options
        uo = session.execute(
            select(UserOptions).where(UserOptions.user_id == user_id)
        ).scalars().first()

        def _f(v):
            return float(v) if v is not None else None

        result = {
            'user_master': {
                'user_phone': um.user_phone if um else None,
                'email': um.email if um else None,
            },
            'user_detail': {
                'kis_id': ud.kis_id if ud else None,
                'kis_account': ud.kis_account if ud else None,
                'kis_access_key': ud.kis_access_key if ud else None,
                'kis_secret_key': ud.kis_secret_key if ud else None,
                'tele_bot_id': ud.tele_bot_id if ud else None,
                'tele_chat_id': ud.tele_chat_id if ud else None,
            },
            'user_options': {
                'stock_sell_mail_flag':       uo.stock_sell_mail_flag if uo else None,
                'stock_buy_target_mail_flag': uo.stock_buy_target_mail_flag if uo else None,
                'stock_sell_tele_flag':       uo.stock_sell_tele_flag if uo else None,
                's1_stop_loss_pct':           _f(uo.s1_stop_loss_pct) if uo else None,
                's1_take_profit_pct':         _f(uo.s1_take_profit_pct) if uo else None,
                's1_max_hold_bars':           uo.s1_max_hold_bars if uo else None,
                's1_rsi_overbought':          uo.s1_rsi_overbought if uo else None,
                's1_rsi_ideal_low':           uo.s1_rsi_ideal_low if uo else None,
                's1_rsi_ideal_high':          uo.s1_rsi_ideal_high if uo else None,
                's1_vol_ma_window':           uo.s1_vol_ma_window if uo else None,
                's1_vol_ma_mult':             _f(uo.s1_vol_ma_mult) if uo else None,
                's1_regime_window':           uo.s1_regime_window if uo else None,
                's1_regime_threshold':        _f(uo.s1_regime_threshold) if uo else None,
                's1_strict_need_macd_up':     uo.s1_strict_need_macd_up if uo else None,
                's1_loose_need_vol_surge':    uo.s1_loose_need_vol_surge if uo else None,
                's1_surge_relax_mult':        _f(uo.s1_surge_relax_mult) if uo else None,
                's1_downtrend_surge_bypass':  uo.s1_downtrend_surge_bypass if uo else None,
                's1_surge_bypass_mult':       _f(uo.s1_surge_bypass_mult) if uo else None,
                's1_use_trailing':            uo.s1_use_trailing if uo else None,
                's1_trail_basis':             uo.s1_trail_basis if uo else None,
                's1_trail_activate_pct':      _f(uo.s1_trail_activate_pct) if uo else None,
                's1_k_trail_atr':             _f(uo.s1_k_trail_atr) if uo else None,
                's1_trail_floor_pct':         _f(uo.s1_trail_floor_pct) if uo else None,
                's1_time_stop_extend':        uo.s1_time_stop_extend if uo else None,
                's1_time_stop_band':          _f(uo.s1_time_stop_band) if uo else None,
                's1_time_stop_grace':         uo.s1_time_stop_grace if uo else None,
                's1_max_hold_bars_hard':      uo.s1_max_hold_bars_hard if uo else None,
                's1_obv_dead_min_bars':       uo.s1_obv_dead_min_bars if uo else None,
            },
        }

        if is_admin:
            result['user_options']['vol_limit'] = uo.vol_limit if uo else None
            result['user_options']['vol_surge'] = _f(uo.vol_surge) if uo else None

        return result

    # ----------------------------------------------------------------
    # user_master 부분 UPDATE
    # ----------------------------------------------------------------
    def update_user_master(self, session, user_id: int, fields: dict) -> None:
        """화이트리스트 컬럼만 UPDATE."""
        ALLOWED = {'user_phone', 'email'}
        values = {k: v for k, v in fields.items() if k in ALLOWED}
        if not values:
            return
        session.execute(
            update(UserMaster).where(UserMaster.user_id == user_id).values(**values)
        )

    # ----------------------------------------------------------------
    # user_detail UPSERT (kis/tele 4개 컬럼)
    # ----------------------------------------------------------------
    def update_user_detail(self, session, user_id: int, fields: dict) -> None:
        """화이트리스트 컬럼만 UPDATE (user_detail은 회원가입 시 이미 존재)."""
        ALLOWED = {'kis_id', 'kis_account', 'kis_access_key', 'kis_secret_key', 'tele_bot_id', 'tele_chat_id'}
        values = {k: v for k, v in fields.items() if k in ALLOWED}
        if not values:
            return
        session.execute(
            update(UserDetail).where(UserDetail.user_id == user_id).values(**values)
        )

    # ----------------------------------------------------------------
    # user_options UPSERT (화이트리스트 컬럼만)
    # ----------------------------------------------------------------
    def upsert_user_options(self, session, user_id: int, fields: dict, is_admin: bool) -> None:
        """화이트리스트 컬럼만 UPSERT. 관리자 전용 컬럼은 is_admin 일 때만 허용."""
        ALLOWED_ALL = {
            'stock_sell_mail_flag', 'stock_buy_target_mail_flag', 'stock_sell_tele_flag',
            's1_stop_loss_pct', 's1_take_profit_pct', 's1_max_hold_bars',
            's1_rsi_overbought', 's1_rsi_ideal_low', 's1_rsi_ideal_high',
            's1_vol_ma_window', 's1_vol_ma_mult', 's1_regime_window', 's1_regime_threshold',
            's1_strict_need_macd_up', 's1_loose_need_vol_surge', 's1_surge_relax_mult',
            's1_downtrend_surge_bypass', 's1_surge_bypass_mult', 's1_use_trailing',
            's1_trail_basis', 's1_trail_activate_pct', 's1_k_trail_atr', 's1_trail_floor_pct',
            's1_time_stop_extend', 's1_time_stop_band', 's1_time_stop_grace',
            's1_max_hold_bars_hard', 's1_obv_dead_min_bars',
        }
        ALLOWED_ADMIN = {'vol_limit', 'vol_surge'}

        values = {k: v for k, v in fields.items() if k in ALLOWED_ALL}
        if is_admin:
            values.update({k: v for k, v in fields.items() if k in ALLOWED_ADMIN})

        if not values:
            return
        stmt = insert(UserOptions).values(user_id=user_id, **values)
        session.execute(stmt.on_duplicate_key_update(**values))

    # upsert (기존 메서드 — 다른 곳에서 사용 중이므로 유지)
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        cols = [
            'upbit_push_flag', 'stock_sell_mail_flag', 'stock_buy_target_mail_flag',
            'stock_sell_tele_flag', 'buy_confirm', 'buy_entry', 'sell_entry', 'sell_exit',
            'user_balance', 'ratio_trend', 'ratio_momentum', 'ratio_volatility', 'ratio_volume',
            'time_frame', 'macd_recent_day', 'bb_over_recent_day', 'vol_limit', 'vol_surge',
            's1_stop_loss_pct', 's1_take_profit_pct', 's1_max_hold_bars',
            's1_rsi_overbought', 's1_rsi_ideal_low', 's1_rsi_ideal_high',
            's1_vol_ma_window', 's1_vol_ma_mult', 's1_regime_window', 's1_regime_threshold',
            's1_strict_need_macd_up', 's1_loose_need_vol_surge', 's1_surge_relax_mult',
            's1_downtrend_surge_bypass', 's1_surge_bypass_mult', 's1_use_trailing',
            's1_trail_basis', 's1_trail_activate_pct', 's1_k_trail_atr', 's1_trail_floor_pct',
            's1_time_stop_extend', 's1_time_stop_band', 's1_time_stop_grace',
            's1_max_hold_bars_hard', 's1_obv_dead_min_bars',
        ]
        values = {c: data.get(c) for c in cols}
        stmt = insert(UserOptions).values(user_id=data['user_id'], **values)
        session.execute(stmt.on_duplicate_key_update(**values))

    # ----------------------------------------------------------------
    # s1_* 전략 파라미터 조회 (GET /api/v1/strategy/options)
    # ----------------------------------------------------------------
    def select_s1_options(self, session, user_id: int) -> dict | None:
        """user_options 에서 s1_* 컬럼만 반환. 행 없으면 None."""
        uo = session.execute(
            select(UserOptions).where(UserOptions.user_id == user_id)
        ).scalars().first()
        if not uo:
            return None

        def _f(v):
            return float(v) if v is not None else None

        return {
            's1_stop_loss_pct':        _f(uo.s1_stop_loss_pct),
            's1_take_profit_pct':      _f(uo.s1_take_profit_pct),
            's1_max_hold_bars':        uo.s1_max_hold_bars,
            's1_rsi_overbought':       uo.s1_rsi_overbought,
            's1_rsi_ideal_low':        uo.s1_rsi_ideal_low,
            's1_rsi_ideal_high':       uo.s1_rsi_ideal_high,
            's1_vol_ma_window':        uo.s1_vol_ma_window,
            's1_vol_ma_mult':          _f(uo.s1_vol_ma_mult),
            's1_regime_window':        uo.s1_regime_window,
            's1_regime_threshold':     _f(uo.s1_regime_threshold),
            's1_strict_need_macd_up':  uo.s1_strict_need_macd_up,
            's1_loose_need_vol_surge': uo.s1_loose_need_vol_surge,
            's1_surge_relax_mult':     _f(uo.s1_surge_relax_mult),
            's1_downtrend_surge_bypass': uo.s1_downtrend_surge_bypass,
            's1_surge_bypass_mult':    _f(uo.s1_surge_bypass_mult),
            's1_use_trailing':         uo.s1_use_trailing,
            's1_trail_basis':          uo.s1_trail_basis,
            's1_trail_activate_pct':   _f(uo.s1_trail_activate_pct),
            's1_k_trail_atr':          _f(uo.s1_k_trail_atr),
            's1_trail_floor_pct':      _f(uo.s1_trail_floor_pct),
            's1_time_stop_extend':     uo.s1_time_stop_extend,
            's1_time_stop_band':       _f(uo.s1_time_stop_band),
            's1_time_stop_grace':      uo.s1_time_stop_grace,
            's1_max_hold_bars_hard':   uo.s1_max_hold_bars_hard,
            's1_obv_dead_min_bars':    uo.s1_obv_dead_min_bars,
        }

    # ----------------------------------------------------------------
    # s1_* 전략 파라미터 UPSERT (PATCH /api/v1/strategy/options)
    # ----------------------------------------------------------------
    def upsert_s1_options(self, session, user_id: int, fields: dict) -> None:
        """화이트리스트 s1_* 컬럼만 UPSERT."""
        S1_ALLOWED = {
            's1_stop_loss_pct', 's1_take_profit_pct', 's1_max_hold_bars',
            's1_rsi_overbought', 's1_rsi_ideal_low', 's1_rsi_ideal_high',
            's1_vol_ma_window', 's1_vol_ma_mult', 's1_regime_window',
            's1_regime_threshold', 's1_strict_need_macd_up', 's1_loose_need_vol_surge',
            's1_surge_relax_mult', 's1_downtrend_surge_bypass', 's1_surge_bypass_mult',
            's1_use_trailing', 's1_trail_basis', 's1_trail_activate_pct',
            's1_k_trail_atr', 's1_trail_floor_pct', 's1_time_stop_extend',
            's1_time_stop_band', 's1_time_stop_grace', 's1_max_hold_bars_hard',
            's1_obv_dead_min_bars',
        }
        values = {k: v for k, v in fields.items() if k in S1_ALLOWED}
        if not values:
            return
        stmt = insert(UserOptions).values(user_id=user_id, **values)
        session.execute(stmt.on_duplicate_key_update(**values))

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
