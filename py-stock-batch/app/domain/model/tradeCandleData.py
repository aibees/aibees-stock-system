from sqlalchemy import Column, String, PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import DECIMAL
from app.domain.model.base import Base

class TradeCandleData(Base):
    __tablename__ = "trade_candle_data"

    # PK
    coin = Column(String(10), nullable=False)
    datetime = Column(String(19), nullable=False)  # "YYYY-MM-DD HH:MM:SS"

    # OHLCV
    open = Column(DECIMAL(18, 8), nullable=False)
    high = Column(DECIMAL(18, 8), nullable=False)
    low = Column(DECIMAL(18, 8), nullable=False)
    close = Column(DECIMAL(18, 8), nullable=False)
    volume = Column(DECIMAL(18, 8), nullable=False)
    # Indicators
    ema20 = Column(DECIMAL(18, 8))
    ema60 = Column(DECIMAL(18, 8))
    ema120 = Column(DECIMAL(18, 8))

    bb_mid = Column(DECIMAL(18, 8))
    bb_lower = Column(DECIMAL(18, 8))
    bb_lower_chk = Column(DECIMAL(1, 0))
    bb_upper = Column(DECIMAL(18, 8))
    bb_upper_chk = Column(DECIMAL(1, 0))
    bb_mid_breakout = Column(DECIMAL(18, 8))
    bb_width = Column(DECIMAL(18, 8))
    bb_width_avg = Column(DECIMAL(18, 8))
    recent_high = Column(DECIMAL(18, 8))

    macd = Column(DECIMAL(18, 8))
    macd_s = Column(DECIMAL(18, 8))
    macd_lower_mean = Column(DECIMAL(18, 8))
    macd_upper_mean = Column(DECIMAL(18, 8))
    macd_recent_min = Column(DECIMAL(18, 8))
    macd_recent_max = Column(DECIMAL(18, 8))
    macd_g_cross_n = Column(String(1))
    macd_d_cross_n = Column(String(1))

    fs_k = Column(DECIMAL(18, 8))
    fs_d = Column(DECIMAL(18, 8))

    roc = Column(DECIMAL(18, 8))
    atr = Column(DECIMAL(18, 8))

    obv = Column(DECIMAL(18, 8))
    obv_signal = Column(DECIMAL(18, 8))
    obv_cross = Column(String(1))
    obv_recent_min = Column(DECIMAL(18, 8))
    obv_recent_max = Column(DECIMAL(18, 8))
    obv_g_cross_n = Column(String(1))
    obv_d_cross_n = Column(String(1))

    rsi = Column(DECIMAL(18, 8))
    rsi_signal = Column(DECIMAL(18, 8))
    rsi_cross = Column(String(1))

    vol_surge_n = Column(DECIMAL(18, 8))
    # Scores
    score_trend = Column(DECIMAL(18, 8))
    score_momentum = Column(DECIMAL(18, 8))
    score_volatility = Column(DECIMAL(18, 8))
    score_volume = Column(DECIMAL(18, 8))
    score_total = Column(DECIMAL(18, 8))
    regime= Column(String(10))

    # Decision
    watch_action = Column(String(45))
    active_action = Column(String(45))

    __table_args__ = (
        PrimaryKeyConstraint("coin", "datetime"),
    )

    def to_dict(self):
        # DECIMAL -> float 변환(주의: 미세 오차 가능)
        def f(x):
            return float(x) if x is not None else None

        return {
            "coin": self.coin,
            "datetime": self.datetime,

            "open": f(self.open),
            "high": f(self.high),
            "low": f(self.low),
            "close": f(self.close),
            "volume": f(self.volume),

            "ema20": f(self.ema20),
            "ema60": f(self.ema60),
            "ema120": f(self.ema120),

            "bb_mid": f(self.bb_mid),
            "bb_mid_breakout": f(self.bb_mid_breakout),
            "bb_lower": f(self.bb_lower),
            "bb_lower_chk": f(self.bb_lower_chk),
            "bb_upper": f(self.bb_upper),
            "bb_upper_chk": f(self.bb_upper_chk),
            "bb_width": f(self.bb_width),
            "bb_width_avg": f(self.bb_width_avg),
            "recent_high": f(self.recent_high),

            "macd": f(self.macd),
            "macd_s": f(self.macd_s),
            "macd_lower_mean": f(self.macd_lower_mean),
            "macd_recent_min": f(self.macd_recent_min),
            "macd_upper_mean": f(self.macd_upper_mean),
            "macd_recent_max": f(self.macd_recent_max),
            "macd_g_cross_n": self.macd_g_cross_n,
            "macd_d_cross_n": self.macd_d_cross_n,

            "fs_k": f(self.fs_k),
            "fs_d": f(self.fs_d),

            "roc": f(self.roc),
            "atr": f(self.atr),

            "obv": f(self.obv),
            "obv_signal": f(self.obv_signal),
            "obv_cross": self.obv_cross,
            "obv_recent_min": f(self.obv_recent_min),
            "obv_recent_max": f(self.obv_recent_max),
            "obv_g_cross_n": self.obv_g_cross_n,
            "obv_d_cross_n": self.obv_d_cross_n,

            "vol_surge_n": f(self.vol_surge_n),

            "rsi": f(self.rsi),
            "rsi_signal": f(self.rsi_signal),

            "score_trend": f(self.score_trend),
            "score_momentum": f(self.score_momentum),
            "score_volatility": f(self.score_volatility),
            "score_volume": f(self.score_volume),
            "score_total": f(self.score_total),
            "regime": self.regime,

            "watch_action": self.watch_action,
            "active_action": self.active_action
        }
