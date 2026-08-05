"""
user_options — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT

from stock_shared.base import Base


class UserOptions(Base):
    __tablename__ = "user_options"

    user_id = Column(Integer, primary_key=True, nullable=False)
    upbit_push_flag = Column(String(1), nullable=True)
    stock_sell_mail_flag = Column(String(1), nullable=True)
    stock_buy_target_mail_flag = Column(String(1), nullable=True)
    stock_sell_tele_flag = Column(String(1), nullable=True)
    buy_confirm = Column(Integer, nullable=True)
    buy_entry = Column(Integer, nullable=True)
    sell_entry = Column(Integer, nullable=True)
    sell_exit = Column(Integer, nullable=True)
    user_balance = Column(DECIMAL(18, 8), nullable=True)
    ratio_trend = Column(DECIMAL(2, 2), nullable=True)
    ratio_momentum = Column(DECIMAL(2, 2), nullable=True)
    ratio_volatility = Column(DECIMAL(2, 2), nullable=True)
    ratio_volume = Column(DECIMAL(2, 2), nullable=True)
    time_frame = Column(String(45), nullable=True)
    macd_recent_day = Column(Integer, nullable=True)
    bb_over_recent_day = Column(Integer, nullable=True)
    vol_limit = Column(Integer, nullable=True)
    vol_surge = Column(DECIMAL(4, 2), nullable=True)
    s1_stop_loss_pct = Column(DECIMAL(6, 4), nullable=True)
    s1_take_profit_pct = Column(DECIMAL(6, 4), nullable=True)
    s1_max_hold_bars = Column(Integer, nullable=True)
    s1_rsi_overbought = Column(Integer, nullable=True)
    s1_rsi_ideal_low = Column(Integer, nullable=True)
    s1_rsi_ideal_high = Column(Integer, nullable=True)
    s1_vol_ma_window = Column(Integer, nullable=True)
    s1_vol_ma_mult = Column(DECIMAL(6, 2), nullable=True)
    s1_regime_window = Column(Integer, nullable=True)
    s1_regime_threshold = Column(DECIMAL(6, 4), nullable=True)
    s1_strict_need_macd_up = Column(TINYINT(1), nullable=True)
    s1_loose_need_vol_surge = Column(TINYINT(1), nullable=True)
    s1_surge_relax_mult = Column(DECIMAL(6, 2), nullable=True)
    s1_downtrend_surge_bypass = Column(TINYINT(1), nullable=True)
    s1_surge_bypass_mult = Column(DECIMAL(6, 2), nullable=True)
    s1_use_trailing = Column(TINYINT(1), nullable=True)
    s1_trail_basis = Column(String(5), nullable=True)
    s1_trail_activate_pct = Column(DECIMAL(6, 4), nullable=True)
    s1_k_trail_atr = Column(DECIMAL(6, 2), nullable=True)
    s1_trail_floor_pct = Column(DECIMAL(6, 4), nullable=True)
    s1_trail_drawdown_pct = Column(DECIMAL(6, 4), nullable=True)
    s1_trail_dual = Column(TINYINT(1), nullable=True)
    s1_time_stop_extend = Column(TINYINT(1), nullable=True)
    s1_time_stop_band = Column(DECIMAL(6, 4), nullable=True)
    s1_time_stop_grace = Column(Integer, nullable=True)
    s1_max_hold_bars_hard = Column(Integer, nullable=True)
    s1_obv_dead_min_bars = Column(Integer, nullable=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "upbit_push_flag": self.upbit_push_flag,
            "stock_sell_mail_flag": self.stock_sell_mail_flag,
            "stock_buy_target_mail_flag": self.stock_buy_target_mail_flag,
            "stock_sell_tele_flag": self.stock_sell_tele_flag,
            "buy_confirm": self.buy_confirm,
            "buy_entry": self.buy_entry,
            "sell_entry": self.sell_entry,
            "sell_exit": self.sell_exit,
            "user_balance": self.user_balance,
            "ratio_trend": self.ratio_trend,
            "ratio_momentum": self.ratio_momentum,
            "ratio_volatility": self.ratio_volatility,
            "ratio_volume": self.ratio_volume,
            "time_frame": self.time_frame,
            "macd_recent_day": self.macd_recent_day,
            "bb_over_recent_day": self.bb_over_recent_day,
            "vol_limit": self.vol_limit,
            "vol_surge": self.vol_surge,
            "s1_stop_loss_pct": self.s1_stop_loss_pct,
            "s1_take_profit_pct": self.s1_take_profit_pct,
            "s1_max_hold_bars": self.s1_max_hold_bars,
            "s1_rsi_overbought": self.s1_rsi_overbought,
            "s1_rsi_ideal_low": self.s1_rsi_ideal_low,
            "s1_rsi_ideal_high": self.s1_rsi_ideal_high,
            "s1_vol_ma_window": self.s1_vol_ma_window,
            "s1_vol_ma_mult": self.s1_vol_ma_mult,
            "s1_regime_window": self.s1_regime_window,
            "s1_regime_threshold": self.s1_regime_threshold,
            "s1_strict_need_macd_up": self.s1_strict_need_macd_up,
            "s1_loose_need_vol_surge": self.s1_loose_need_vol_surge,
            "s1_surge_relax_mult": self.s1_surge_relax_mult,
            "s1_downtrend_surge_bypass": self.s1_downtrend_surge_bypass,
            "s1_surge_bypass_mult": self.s1_surge_bypass_mult,
            "s1_use_trailing": self.s1_use_trailing,
            "s1_trail_basis": self.s1_trail_basis,
            "s1_trail_activate_pct": self.s1_trail_activate_pct,
            "s1_k_trail_atr": self.s1_k_trail_atr,
            "s1_trail_floor_pct": self.s1_trail_floor_pct,
            "s1_trail_drawdown_pct": self.s1_trail_drawdown_pct,
            "s1_trail_dual": self.s1_trail_dual,
            "s1_time_stop_extend": self.s1_time_stop_extend,
            "s1_time_stop_band": self.s1_time_stop_band,
            "s1_time_stop_grace": self.s1_time_stop_grace,
            "s1_max_hold_bars_hard": self.s1_max_hold_bars_hard,
            "s1_obv_dead_min_bars": self.s1_obv_dead_min_bars,
        }
