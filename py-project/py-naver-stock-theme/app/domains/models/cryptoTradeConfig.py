from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CryptoTradeConfig(Base):
    __tablename__ = 'crypto_trade_config'

    config_id               = Column(String(64),   primary_key=True)
    symbol                  = Column(String(16),   nullable=False)
    exchange_id             = Column(String(32),   nullable=False, default='upbit')
    timeframe               = Column(String(8),    nullable=False, default='1d')
    strategy_type           = Column(String(32),   nullable=False, default='SQUEEZE_BREAKOUT')
    bb_period               = Column(Integer,      nullable=False, default=20)
    bb_std_mult             = Column(DECIMAL(4,2), nullable=False, default='2.00')
    rsi_period              = Column(Integer,      nullable=False, default=14)
    macd_fast               = Column(Integer,      nullable=False, default=12)
    macd_slow               = Column(Integer,      nullable=False, default=26)
    macd_signal             = Column(Integer,      nullable=False, default=9)
    obv_lookback            = Column(Integer,      nullable=False, default=20)
    squeeze_lookback        = Column(Integer,      nullable=False, default=20)
    squeeze_threshold_pct   = Column(DECIMAL(5,2), nullable=False, default='20.00')
    rsi_upper_limit         = Column(DECIMAL(5,2), nullable=False, default='75.00')
    rsi_lower_limit         = Column(DECIMAL(5,2), nullable=False, default='25.00')
    buy_amount_krw          = Column(DECIMAL(15,2),nullable=False, default='50000.00')
    target_profit_pct       = Column(DECIMAL(5,2), nullable=False, default='5.00')
    stop_loss_pct           = Column(DECIMAL(5,2), nullable=False, default='-3.00')
    enabled_flag            = Column(String(1),    nullable=False, default='Y')
    trail_pct               = Column(DECIMAL(5,2), nullable=False, default='0.00')
    trail_activation_pct    = Column(DECIMAL(5,2), nullable=False, default='2.00')

    def to_dict(self):
        return {
            'config_id':             self.config_id,
            'symbol':                self.symbol,
            'exchange_id':           self.exchange_id,
            'timeframe':             self.timeframe,
            'strategy_type':         self.strategy_type,
            'bb_period':             self.bb_period,
            'bb_std_mult':           float(self.bb_std_mult)           if self.bb_std_mult           is not None else None,
            'rsi_period':            self.rsi_period,
            'macd_fast':             self.macd_fast,
            'macd_slow':             self.macd_slow,
            'macd_signal':           self.macd_signal,
            'obv_lookback':          self.obv_lookback,
            'squeeze_lookback':      self.squeeze_lookback,
            'squeeze_threshold_pct': float(self.squeeze_threshold_pct) if self.squeeze_threshold_pct is not None else None,
            'rsi_upper_limit':       float(self.rsi_upper_limit)       if self.rsi_upper_limit       is not None else None,
            'rsi_lower_limit':       float(self.rsi_lower_limit)       if self.rsi_lower_limit       is not None else None,
            'buy_amount_krw':        float(self.buy_amount_krw)        if self.buy_amount_krw        is not None else None,
            'target_profit_pct':     float(self.target_profit_pct)     if self.target_profit_pct     is not None else None,
            'stop_loss_pct':         float(self.stop_loss_pct)         if self.stop_loss_pct         is not None else None,
            'enabled_flag':          self.enabled_flag,
            'trail_pct':             float(self.trail_pct)             if self.trail_pct             is not None else None,
            'trail_activation_pct':  float(self.trail_activation_pct)  if self.trail_activation_pct  is not None else None,
        }
