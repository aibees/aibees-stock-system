from sqlalchemy import Column, Integer, String, DECIMAL, SmallInteger
from app.domain.model.base import Base

class UserOptions(Base):
    __tablename__ = 'user_options'

    user_id = Column(Integer, primary_key=True, nullable=False)
    upbit_push_flag = Column(String(1))
    buy_confirm = Column(Integer)
    buy_entry = Column(Integer)
    sell_entry = Column(Integer)
    sell_exit = Column(Integer)
    time_frame = Column(String(4))
    user_balance = Column(DECIMAL(2, 2))
    ratio_trend = Column(DECIMAL(2, 2))
    ratio_momentum = Column(DECIMAL(2, 2))
    ratio_volatility = Column(DECIMAL(2, 2))
    ratio_volume = Column(DECIMAL(2, 2))

    macd_recent_day = Column(Integer)
    bb_over_recent_day = Column(Integer)
    vol_limit = Column(Integer)
    vol_surge = Column(DECIMAL(2, 2))

    stock_buy_target_mail_flag  = Column(String(1))
    stock_sell_mail_flag        = Column(String(1))
    stock_sell_tele_flag        = Column(String(1))

    # ── KospiStrategy1 파라미터 ──────────────────────────────────────
    # 손절/익절/보유
    s1_stop_loss_pct         = Column(DECIMAL(6, 4))
    s1_take_profit_pct       = Column(DECIMAL(6, 4))
    s1_max_hold_bars         = Column(Integer)
    # RSI / 거래량
    s1_rsi_overbought        = Column(Integer)
    s1_rsi_ideal_low         = Column(Integer)
    s1_rsi_ideal_high        = Column(Integer)
    s1_vol_ma_window         = Column(Integer)
    s1_vol_ma_mult           = Column(DECIMAL(6, 2))
    # 추세국면 게이트
    s1_regime_window         = Column(Integer)
    s1_regime_threshold      = Column(DECIMAL(6, 4))
    s1_strict_need_macd_up   = Column(SmallInteger)
    s1_loose_need_vol_surge  = Column(SmallInteger)
    s1_surge_relax_mult      = Column(DECIMAL(6, 2))
    s1_downtrend_surge_bypass = Column(SmallInteger)
    s1_surge_bypass_mult     = Column(DECIMAL(6, 2))
    # 트레일링 스탑
    s1_use_trailing          = Column(SmallInteger)
    s1_trail_basis           = Column(String(5))
    s1_trail_activate_pct    = Column(DECIMAL(6, 4))
    s1_k_trail_atr           = Column(DECIMAL(6, 2))
    s1_trail_floor_pct       = Column(DECIMAL(6, 4))
    # 동적 타임스탑
    s1_time_stop_extend      = Column(SmallInteger)
    s1_time_stop_band        = Column(DECIMAL(6, 4))
    s1_time_stop_grace       = Column(Integer)
    s1_max_hold_bars_hard    = Column(Integer)
    # 하드코딩 변수화
    s1_obv_dead_min_bars     = Column(Integer)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "upbit_push_flag": self.upbit_push_flag,
            "buy_confirm": self.buy_confirm,
            "buy_entry": self.buy_entry,
            "sell_entry": self.sell_entry,
            "sell_exit": self.sell_exit,
            "time_frame": self.time_frame,
            "user_balance": self.user_balance,
            "ratio_trend": self.ratio_trend or 0.35,
            "ratio_momentum": self.ratio_momentum or 0.25,
            "ratio_volatility": self.ratio_volatility or 0.25,
            "ratio_volume": self.ratio_volume or 0.15,
            "macd_recent_day": self.macd_recent_day or 7,
            "bb_over_recent_day": self.bb_over_recent_day or 7,
            "vol_limit": self.vol_limit or 0,
            "vol_surge": self.vol_surge or 3.0,
            "stock_buy_target_mail_flag": self.stock_buy_target_mail_flag,
            "stock_sell_mail_flag": self.stock_sell_mail_flag,
            "stock_sell_tele_flag": self.stock_sell_tele_flag,
            # KospiStrategy1 파라미터 (None이면 전략 기본값 사용)
            "s1_stop_loss_pct":          self.s1_stop_loss_pct,
            "s1_take_profit_pct":        self.s1_take_profit_pct,
            "s1_max_hold_bars":          self.s1_max_hold_bars,
            "s1_rsi_overbought":         self.s1_rsi_overbought,
            "s1_rsi_ideal_low":          self.s1_rsi_ideal_low,
            "s1_rsi_ideal_high":         self.s1_rsi_ideal_high,
            "s1_vol_ma_window":          self.s1_vol_ma_window,
            "s1_vol_ma_mult":            self.s1_vol_ma_mult,
            "s1_regime_window":          self.s1_regime_window,
            "s1_regime_threshold":       self.s1_regime_threshold,
            "s1_strict_need_macd_up":    self.s1_strict_need_macd_up,
            "s1_loose_need_vol_surge":   self.s1_loose_need_vol_surge,
            "s1_surge_relax_mult":       self.s1_surge_relax_mult,
            "s1_downtrend_surge_bypass": self.s1_downtrend_surge_bypass,
            "s1_surge_bypass_mult":      self.s1_surge_bypass_mult,
            "s1_use_trailing":           self.s1_use_trailing,
            "s1_trail_basis":            self.s1_trail_basis,
            "s1_trail_activate_pct":     self.s1_trail_activate_pct,
            "s1_k_trail_atr":            self.s1_k_trail_atr,
            "s1_trail_floor_pct":        self.s1_trail_floor_pct,
            "s1_time_stop_extend":       self.s1_time_stop_extend,
            "s1_time_stop_band":         self.s1_time_stop_band,
            "s1_time_stop_grace":        self.s1_time_stop_grace,
            "s1_max_hold_bars_hard":     self.s1_max_hold_bars_hard,
            "s1_obv_dead_min_bars":      self.s1_obv_dead_min_bars,
        }