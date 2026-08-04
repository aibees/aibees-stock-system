from sqlalchemy import Column, String, PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradeCandleData(Base):
    __tablename__ = 'trade_candle_data'

    coin     = Column(String(10),    nullable=False)
    datetime = Column(String(19),    nullable=False)

    # OHLCV
    open     = Column(DECIMAL(18,8), nullable=False)
    high     = Column(DECIMAL(18,8), nullable=False)
    low      = Column(DECIMAL(18,8), nullable=False)
    close    = Column(DECIMAL(18,8), nullable=False)
    volume   = Column(DECIMAL(18,8), nullable=False)

    # EMA
    ema20    = Column(DECIMAL(18,8), nullable=True)
    ema60    = Column(DECIMAL(18,8), nullable=True)
    ema120   = Column(DECIMAL(18,8), nullable=True)

    # Bollinger Bands
    bb_mid       = Column(DECIMAL(18,8), nullable=True)
    bb_lower     = Column(DECIMAL(18,8), nullable=True)
    bb_lower_chk = Column(DECIMAL(1,0),  nullable=True)
    bb_upper     = Column(DECIMAL(18,8), nullable=True)
    bb_upper_chk = Column(DECIMAL(1,0),  nullable=True)
    bb_width     = Column(DECIMAL(18,8), nullable=True)
    bb_width_avg = Column(DECIMAL(18,8), nullable=True)
    bb_mid_breakout = Column(DECIMAL(18,8), nullable=True)
    recent_high     = Column(DECIMAL(18,8), nullable=True)

    # MACD
    macd             = Column(DECIMAL(18,8), nullable=True)
    macd_s           = Column(DECIMAL(18,8), nullable=True)
    macd_lower_mean  = Column(DECIMAL(18,8), nullable=True)
    macd_upper_mean  = Column(DECIMAL(18,8), nullable=True)
    macd_recent_min  = Column(DECIMAL(18,8), nullable=True)
    macd_recent_max  = Column(DECIMAL(18,8), nullable=True)
    macd_g_cross_n   = Column(String(1),     nullable=True)
    macd_d_cross_n   = Column(String(1),     nullable=True)

    # Stochastic
    fs_k = Column(DECIMAL(18,8), nullable=True)
    fs_d = Column(DECIMAL(18,8), nullable=True)

    # OBV
    obv            = Column(DECIMAL(18,8), nullable=True)
    obv_signal     = Column(DECIMAL(18,8), nullable=True)
    obv_cross      = Column(String(1),     nullable=True)
    obv_recent_min = Column(DECIMAL(18,8), nullable=True)
    obv_recent_max = Column(DECIMAL(18,8), nullable=True)
    obv_g_cross_n  = Column(String(1),     nullable=True)
    obv_d_cross_n  = Column(String(1),     nullable=True)

    # RSI
    rsi        = Column(DECIMAL(18,8), nullable=True)
    rsi_signal = Column(DECIMAL(18,8), nullable=True)
    rsi_cross  = Column(String(1),     nullable=True)

    # Other indicators
    roc        = Column(DECIMAL(18,8), nullable=True)
    atr        = Column(DECIMAL(18,8), nullable=True)
    vol_surge_n = Column(DECIMAL(18,8), nullable=True)

    # Scores
    score_trend      = Column(DECIMAL(18,8), nullable=True)
    score_momentum   = Column(DECIMAL(18,8), nullable=True)
    score_volatility = Column(DECIMAL(18,8), nullable=True)
    score_volume     = Column(DECIMAL(18,8), nullable=True)
    score_total      = Column(DECIMAL(18,8), nullable=True)

    # Action / Regime
    watch_action  = Column(String(45), nullable=True)
    active_action = Column(String(45), nullable=True)
    regime        = Column(String(45), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('coin', 'datetime'),
    )

    def to_dict(self):
        def _f(v):
            return float(v) if v is not None else None

        return {
            'coin':             self.coin,
            'datetime':         self.datetime,
            'open':             _f(self.open),
            'high':             _f(self.high),
            'low':              _f(self.low),
            'close':            _f(self.close),
            'volume':           _f(self.volume),
            'ema20':            _f(self.ema20),
            'ema60':            _f(self.ema60),
            'ema120':           _f(self.ema120),
            'bb_mid':           _f(self.bb_mid),
            'bb_lower':         _f(self.bb_lower),
            'bb_lower_chk':     _f(self.bb_lower_chk),
            'bb_upper':         _f(self.bb_upper),
            'bb_upper_chk':     _f(self.bb_upper_chk),
            'bb_width':         _f(self.bb_width),
            'bb_width_avg':     _f(self.bb_width_avg),
            'bb_mid_breakout':  _f(self.bb_mid_breakout),
            'recent_high':      _f(self.recent_high),
            'macd':             _f(self.macd),
            'macd_s':           _f(self.macd_s),
            'macd_lower_mean':  _f(self.macd_lower_mean),
            'macd_upper_mean':  _f(self.macd_upper_mean),
            'macd_recent_min':  _f(self.macd_recent_min),
            'macd_recent_max':  _f(self.macd_recent_max),
            'macd_g_cross_n':   self.macd_g_cross_n,
            'macd_d_cross_n':   self.macd_d_cross_n,
            'fs_k':             _f(self.fs_k),
            'fs_d':             _f(self.fs_d),
            'obv':              _f(self.obv),
            'obv_signal':       _f(self.obv_signal),
            'obv_cross':        self.obv_cross,
            'obv_recent_min':   _f(self.obv_recent_min),
            'obv_recent_max':   _f(self.obv_recent_max),
            'obv_g_cross_n':    self.obv_g_cross_n,
            'obv_d_cross_n':    self.obv_d_cross_n,
            'rsi':              _f(self.rsi),
            'rsi_signal':       _f(self.rsi_signal),
            'rsi_cross':        self.rsi_cross,
            'roc':              _f(self.roc),
            'atr':              _f(self.atr),
            'vol_surge_n':      _f(self.vol_surge_n),
            'score_trend':      _f(self.score_trend),
            'score_momentum':   _f(self.score_momentum),
            'score_volatility': _f(self.score_volatility),
            'score_volume':     _f(self.score_volume),
            'score_total':      _f(self.score_total),
            'watch_action':     self.watch_action,
            'active_action':    self.active_action,
            'regime':           self.regime,
        }
