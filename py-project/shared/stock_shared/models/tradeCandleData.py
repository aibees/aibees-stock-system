"""
trade_candle_data — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, PrimaryKeyConstraint, String
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class TradeCandleData(Base):
    __tablename__ = "trade_candle_data"

    __table_args__ = (PrimaryKeyConstraint("coin", "datetime"),)

    coin = Column(String(10), nullable=False)
    datetime = Column(String(19), nullable=False)
    open = Column(DECIMAL(18, 8), nullable=False)
    high = Column(DECIMAL(18, 8), nullable=False)
    low = Column(DECIMAL(18, 8), nullable=False)
    close = Column(DECIMAL(18, 8), nullable=False)
    volume = Column(DECIMAL(18, 8), nullable=False)
    ema20 = Column(DECIMAL(18, 8), nullable=True)
    ema60 = Column(DECIMAL(18, 8), nullable=True)
    ema120 = Column(DECIMAL(18, 8), nullable=True)
    bb_mid = Column(DECIMAL(18, 8), nullable=True)
    bb_lower = Column(DECIMAL(18, 8), nullable=True)
    bb_lower_chk = Column(DECIMAL(1, 0), nullable=True)
    bb_upper = Column(DECIMAL(18, 8), nullable=True)
    bb_upper_chk = Column(DECIMAL(1, 0), nullable=True)
    bb_width = Column(DECIMAL(18, 8), nullable=True)
    bb_width_avg = Column(DECIMAL(18, 8), nullable=True)
    macd = Column(DECIMAL(18, 8), nullable=True)
    macd_s = Column(DECIMAL(18, 8), nullable=True)
    macd_lower_mean = Column(DECIMAL(18, 8), nullable=True)
    macd_upper_mean = Column(DECIMAL(18, 8), nullable=True)
    macd_recent_min = Column(DECIMAL(18, 8), nullable=True)
    macd_recent_max = Column(DECIMAL(18, 8), nullable=True)
    fs_k = Column(DECIMAL(18, 8), nullable=True)
    fs_d = Column(DECIMAL(18, 8), nullable=True)
    roc = Column(DECIMAL(18, 8), nullable=True)
    atr = Column(DECIMAL(18, 8), nullable=True)
    obv = Column(DECIMAL(18, 8), nullable=True)
    obv_signal = Column(DECIMAL(18, 8), nullable=True)
    obv_cross = Column(String(1), nullable=True)
    obv_recent_min = Column(DECIMAL(18, 8), nullable=True)
    obv_recent_max = Column(DECIMAL(18, 8), nullable=True)
    rsi = Column(DECIMAL(18, 8), nullable=True)
    rsi_signal = Column(DECIMAL(18, 8), nullable=True)
    rsi_cross = Column(String(1), nullable=True)
    score_trend = Column(DECIMAL(18, 8), nullable=True)
    score_momentum = Column(DECIMAL(18, 8), nullable=True)
    score_volatility = Column(DECIMAL(18, 8), nullable=True)
    score_volume = Column(DECIMAL(18, 8), nullable=True)
    score_total = Column(DECIMAL(18, 8), nullable=True)
    watch_action = Column(String(45), nullable=True)
    active_action = Column(String(45), nullable=True)
    regime = Column(String(45), nullable=True)
    bb_mid_breakout = Column(DECIMAL(18, 8), nullable=True)
    macd_g_cross_n = Column(String(1), nullable=True)
    macd_d_cross_n = Column(String(1), nullable=True)
    obv_g_cross_n = Column(String(1), nullable=True)
    obv_d_cross_n = Column(String(1), nullable=True)
    vol_surge_n = Column(DECIMAL(18, 8), nullable=True)
    recent_high = Column(DECIMAL(18, 8), nullable=True)

    def to_dict(self):
        return {
            "coin": self.coin,
            "datetime": self.datetime,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "ema20": self.ema20,
            "ema60": self.ema60,
            "ema120": self.ema120,
            "bb_mid": self.bb_mid,
            "bb_lower": self.bb_lower,
            "bb_lower_chk": self.bb_lower_chk,
            "bb_upper": self.bb_upper,
            "bb_upper_chk": self.bb_upper_chk,
            "bb_width": self.bb_width,
            "bb_width_avg": self.bb_width_avg,
            "macd": self.macd,
            "macd_s": self.macd_s,
            "macd_lower_mean": self.macd_lower_mean,
            "macd_upper_mean": self.macd_upper_mean,
            "macd_recent_min": self.macd_recent_min,
            "macd_recent_max": self.macd_recent_max,
            "fs_k": self.fs_k,
            "fs_d": self.fs_d,
            "roc": self.roc,
            "atr": self.atr,
            "obv": self.obv,
            "obv_signal": self.obv_signal,
            "obv_cross": self.obv_cross,
            "obv_recent_min": self.obv_recent_min,
            "obv_recent_max": self.obv_recent_max,
            "rsi": self.rsi,
            "rsi_signal": self.rsi_signal,
            "rsi_cross": self.rsi_cross,
            "score_trend": self.score_trend,
            "score_momentum": self.score_momentum,
            "score_volatility": self.score_volatility,
            "score_volume": self.score_volume,
            "score_total": self.score_total,
            "watch_action": self.watch_action,
            "active_action": self.active_action,
            "regime": self.regime,
            "bb_mid_breakout": self.bb_mid_breakout,
            "macd_g_cross_n": self.macd_g_cross_n,
            "macd_d_cross_n": self.macd_d_cross_n,
            "obv_g_cross_n": self.obv_g_cross_n,
            "obv_d_cross_n": self.obv_d_cross_n,
            "vol_surge_n": self.vol_surge_n,
            "recent_high": self.recent_high,
        }
