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
    s1_trail_giveback_pct = Column(DECIMAL(6, 4), nullable=True)
    s1_trail_dual = Column(TINYINT(1), nullable=True)
    s1_trail_fib_use = Column(TINYINT(1), nullable=True)
    s1_trail_fib_level = Column(DECIMAL(5, 3), nullable=True)
    s1_time_stop_extend = Column(TINYINT(1), nullable=True)
    s1_time_stop_band = Column(DECIMAL(6, 4), nullable=True)
    s1_time_stop_grace = Column(Integer, nullable=True)
    s1_max_hold_bars_hard = Column(Integer, nullable=True)
    s1_obv_dead_min_bars = Column(Integer, nullable=True)

    # ── 매수 필터 on/off 스위치 (NULL = 전략 기본값 True) ──────────────
    # KospiStrategy0.get_action_in_watch 의 각 게이트를 개별로 끈다.
    # ※ 매수타겟 생성(StockBuyCheckJob)은 user_id=1 옵션만 읽어 **공용 테이블**을
    #   만든다. 즉 이 값들은 사실상 전역 설정이라 화면에서도 관리자 전용이다.
    s1_enable_macd_filter = Column(TINYINT(1), nullable=True)
    s1_enable_rsi_filter = Column(TINYINT(1), nullable=True)
    s1_enable_bb_upper_filter = Column(TINYINT(1), nullable=True)
    s1_enable_vol_avg_filter = Column(TINYINT(1), nullable=True)
    s1_enable_regime_gate = Column(TINYINT(1), nullable=True)

    # core 진입 신호 mode: 'off' | 'golden' | 'slope' (NULL = 전략 기본값)
    s1_macd_signal_mode = Column(String(10), nullable=True)
    s1_obv_signal_mode = Column(String(10), nullable=True)
    # MA20(ema20) 기울기 게이트: 'off' | 'slope' (NULL = 전략 기본값 'off')
    s1_ma20_signal_mode = Column(String(10), nullable=True)

    # worker 매수타겟 정렬 순서. "score:desc,volume:desc" 형식(다중 키 tie-break).
    # NULL = 기본값(score:desc,rank_no:asc). 파싱은 repository._ORDER_FIELDS 참조.
    # 위 필터들과 달리 **유저별 개인화** — worker(BuyExecutor)만 쓰므로 서로 간섭 없음.
    s1_buy_order = Column(String(255), nullable=True)

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
            "s1_trail_giveback_pct": self.s1_trail_giveback_pct,
            "s1_trail_dual": self.s1_trail_dual,
            "s1_trail_fib_use": self.s1_trail_fib_use,
            "s1_trail_fib_level": self.s1_trail_fib_level,
            "s1_time_stop_extend": self.s1_time_stop_extend,
            "s1_time_stop_band": self.s1_time_stop_band,
            "s1_time_stop_grace": self.s1_time_stop_grace,
            "s1_max_hold_bars_hard": self.s1_max_hold_bars_hard,
            "s1_obv_dead_min_bars": self.s1_obv_dead_min_bars,
            "s1_enable_macd_filter": self.s1_enable_macd_filter,
            "s1_enable_rsi_filter": self.s1_enable_rsi_filter,
            "s1_enable_bb_upper_filter": self.s1_enable_bb_upper_filter,
            "s1_enable_vol_avg_filter": self.s1_enable_vol_avg_filter,
            "s1_enable_regime_gate": self.s1_enable_regime_gate,
            "s1_macd_signal_mode": self.s1_macd_signal_mode,
            "s1_obv_signal_mode": self.s1_obv_signal_mode,
            "s1_ma20_signal_mode": self.s1_ma20_signal_mode,
            "s1_buy_order": self.s1_buy_order,
        }
