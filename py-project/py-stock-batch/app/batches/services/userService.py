import logging


from stock_shared.dao.userMasterDao import UserMasterDao
from stock_shared.dao.userOptionM2Dao import UserOptionM2Dao
from stock_shared.dto.userOptionMeta import UserOptionMeta


# user_options 의 레거시 지표 컬럼 기본값.
#   이 값들은 화면에서 비워둘 수 있어 NULL 로 들어오는 유저가 있는데(user 2/3/4/6),
#   예전엔 `x['macd_recent_day']` 로 직접 대입해 UserOptionMeta 의 기본값을 None 으로
#   덮어썼다. 그 None 이 KisStockService.compute_indicator_df 의
#   rolling(window=None) 까지 흘러가 "window must be an integer 0 or greater" 로 터지고,
#   일봉 지표 전체 → 초기 라인/일별 평가가 전부 실패했다(2026-09-29 user_id=3).
#   UserOptionMeta 쪽 기본값(0)은 rolling 에 넣으면 전부 NaN 이라 쓸모가 없어서,
#   실제로 동작 중인 유저(1/5)와 같은 값을 여기서 명시한다.
_DEFAULT_MACD_RECENT_DAY = 5
_DEFAULT_BB_OVER_RECENT_DAY = 5
_DEFAULT_VOL_LIMIT = 500000
_DEFAULT_VOL_SURGE = 3.0


def _or_default(v, default):
    """NULL(None) 이면 기본값. 0/빈값은 사용자가 의도한 값일 수 있어 그대로 둔다."""
    return default if v is None else v


def extractor(x) -> UserOptionMeta:
    user_meta = UserOptionMeta()
    user_meta.email        = x['email']
    user_meta.user_name    = x['user_name']
    user_meta.user_id      = x['user_id']
    user_meta.macd_recent_day    = _or_default(x['macd_recent_day'], _DEFAULT_MACD_RECENT_DAY)
    user_meta.bb_over_recent_day = _or_default(x['bb_over_recent_day'], _DEFAULT_BB_OVER_RECENT_DAY)
    user_meta.vol_limit    = _or_default(x['vol_limit'], _DEFAULT_VOL_LIMIT)
    user_meta.vol_surge    = _or_default(x['vol_surge'], _DEFAULT_VOL_SURGE)
    # 메신저 설정
    user_meta.tele_bot_id          = x.get('tele_bot_id', '')
    user_meta.tele_chat_id         = x.get('tele_chat_id', '')
    user_meta.stock_sell_mail_flag = x.get('stock_sell_mail_flag', 'N')
    user_meta.stock_sell_tele_flag = x.get('stock_sell_tele_flag', 'N')
    # KospiStrategy1 파라미터 (None이면 전략 기본값 유지)
    user_meta.s1_stop_loss_pct          = x.get('s1_stop_loss_pct')
    user_meta.s1_take_profit_pct        = x.get('s1_take_profit_pct')
    user_meta.s1_max_hold_bars          = x.get('s1_max_hold_bars')
    user_meta.s1_rsi_overbought         = x.get('s1_rsi_overbought')
    user_meta.s1_rsi_ideal_low          = x.get('s1_rsi_ideal_low')
    user_meta.s1_rsi_ideal_high         = x.get('s1_rsi_ideal_high')
    user_meta.s1_vol_ma_window          = x.get('s1_vol_ma_window')
    user_meta.s1_vol_ma_mult            = x.get('s1_vol_ma_mult')
    user_meta.s1_regime_window          = x.get('s1_regime_window')
    user_meta.s1_regime_threshold       = x.get('s1_regime_threshold')
    user_meta.s1_strict_need_macd_up    = x.get('s1_strict_need_macd_up')
    user_meta.s1_loose_need_vol_surge   = x.get('s1_loose_need_vol_surge')
    user_meta.s1_surge_relax_mult       = x.get('s1_surge_relax_mult')
    user_meta.s1_downtrend_surge_bypass = x.get('s1_downtrend_surge_bypass')
    user_meta.s1_surge_bypass_mult      = x.get('s1_surge_bypass_mult')
    user_meta.s1_use_trailing           = x.get('s1_use_trailing')
    user_meta.s1_trail_drawdown_pct     = x.get('s1_trail_drawdown_pct')
    user_meta.s1_trail_dual             = x.get('s1_trail_dual')
    user_meta.s1_trail_activate_pct     = x.get('s1_trail_activate_pct')
    user_meta.s1_k_trail_atr            = x.get('s1_k_trail_atr')
    user_meta.s1_trail_floor_pct        = x.get('s1_trail_floor_pct')
    user_meta.s1_time_stop_extend       = x.get('s1_time_stop_extend')
    user_meta.s1_time_stop_band         = x.get('s1_time_stop_band')
    user_meta.s1_time_stop_grace        = x.get('s1_time_stop_grace')
    user_meta.s1_max_hold_bars_hard     = x.get('s1_max_hold_bars_hard')
    user_meta.s1_trail_giveback_pct     = x.get('s1_trail_giveback_pct')
    user_meta.s1_trail_fib_use          = x.get('s1_trail_fib_use')
    user_meta.s1_trail_fib_level        = x.get('s1_trail_fib_level')
    # 매수 필터 on/off · core 신호 mode
    #   ※ 여태 이 매핑이 없어서 configure() 가 항상 None 을 받았고,
    #     결과적으로 전략 클래스 기본값만 쓰였다(유저 설정이 먹지 않던 원인).
    user_meta.s1_enable_macd_filter     = x.get('s1_enable_macd_filter')
    user_meta.s1_enable_rsi_filter      = x.get('s1_enable_rsi_filter')
    user_meta.s1_enable_bb_upper_filter = x.get('s1_enable_bb_upper_filter')
    user_meta.s1_enable_vol_avg_filter  = x.get('s1_enable_vol_avg_filter')
    user_meta.s1_enable_regime_gate     = x.get('s1_enable_regime_gate')
    user_meta.s1_enable_shape_exhaustion_filter = x.get('s1_enable_shape_exhaustion_filter')
    user_meta.s1_enable_avg_vol_filter  = x.get('s1_enable_avg_vol_filter')
    user_meta.s1_avg_vol_min            = x.get('s1_avg_vol_min')
    user_meta.s1_enable_sma120_filter   = x.get('s1_enable_sma120_filter')
    user_meta.s1_macd_signal_mode       = x.get('s1_macd_signal_mode')
    user_meta.s1_obv_signal_mode        = x.get('s1_obv_signal_mode')
    user_meta.s1_ma20_signal_mode       = x.get('s1_ma20_signal_mode')
    # worker 매수타겟 정렬 순서 ("score:desc,volume:desc" 형식, None=기본값)
    user_meta.s1_buy_order              = x.get('s1_buy_order')
    return user_meta


class UserService:
    def __init__(self):
        self.__name__ = 'UserService'
        self.userMasterDaoImpl = UserMasterDao()

    def get_user_options(self, session, user_id: int = 1) -> UserOptionMeta:
        result = self.userMasterDaoImpl.select_user_stock_options(session, {'user_id': user_id})
        meta = extractor(result)
        self._apply_mode_options(session, user_id, meta)
        return meta

    @staticmethod
    def _apply_mode_options(session, user_id: int, meta: UserOptionMeta) -> None:
        """모드별 옵션 테이블(user_option_m2 등)을 s2_* 로 메타에 얹는다.

        user_options 는 전역 설정이고 모드별 파라미터는 별도 테이블에 있다.
        행이 없으면(= 아직 설정 안 함) 아무것도 덮지 않는다 → 전략 클래스 기본값.
        조회가 실패해도 worker 를 죽이지 않는다. 기본값으로 도는 편이 낫다.
        """
        try:
            for k, v in UserOptionM2Dao().select_prefixed(session, user_id).items():
                setattr(meta, k, v)
        except Exception as e:  # noqa: BLE001
            logging.warning('user_option_m2 조회 실패(user_id=%s) → 기본값 사용: %s',
                            user_id, e)

    def get_user_email_by_condition(self, session, option):
        if option == 'email':
            return self.userMasterDaoImpl.select_target_emails(session)
        return []
