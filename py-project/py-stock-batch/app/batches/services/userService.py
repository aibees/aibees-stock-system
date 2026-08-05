

from stock_shared.dao.userMasterDao import UserMasterDao
from stock_shared.dto.userOptionMeta import UserOptionMeta


def extractor(x) -> UserOptionMeta:
    user_meta = UserOptionMeta()
    user_meta.email        = x['email']
    user_meta.user_name    = x['user_name']
    user_meta.user_id      = x['user_id']
    user_meta.macd_recent_day    = x['macd_recent_day']
    user_meta.bb_over_recent_day = x['bb_over_recent_day']
    user_meta.vol_limit    = x['vol_limit']
    user_meta.vol_surge    = x['vol_surge']
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
    user_meta.s1_obv_dead_min_bars      = x.get('s1_obv_dead_min_bars')
    return user_meta


class UserService:
    def __init__(self):
        self.__name__ = 'UserService'
        self.userMasterDaoImpl = UserMasterDao()

    def get_user_options(self, session, user_id: int = 1) -> UserOptionMeta:
        result = self.userMasterDaoImpl.select_user_stock_options(session, {'user_id': user_id})
        return extractor(result)

    def get_all_sell_target_users(self, session) -> list[UserOptionMeta]:
        """매도 알림(email 또는 telegram) 설정된 유저 전체를 UserOptionMeta 리스트로 반환"""
        rows = self.userMasterDaoImpl.select_sell_target_users(session)
        return [extractor(r) for r in rows]

    def get_user_email_by_condition(self, session, option):
        if option == 'email':
            return self.userMasterDaoImpl.select_target_emails(session)
        return []
