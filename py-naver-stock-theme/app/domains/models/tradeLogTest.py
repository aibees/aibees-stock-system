from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradeLogTest(Base):
    __tablename__ = 'trade_log_test'

    log_id         = Column(Integer,     primary_key=True, autoincrement=True)
    ymd            = Column(String(8),   nullable=True)
    times          = Column(String(6),   nullable=True)
    user_id        = Column(Integer,     nullable=True)
    time_frame     = Column(String(45),  nullable=True)
    bar_time       = Column(DateTime,    nullable=True)
    coin_code      = Column(String(45),  nullable=True)
    action         = Column(String(45),  nullable=True)
    buy_price      = Column(DECIMAL(18,8), nullable=True)
    buy_amount     = Column(DECIMAL(18,8), nullable=True)
    sell_price     = Column(String(45),  nullable=True)
    sell_amount    = Column(String(45),  nullable=True)
    user_balance   = Column(String(45),  nullable=True)
    score_trend    = Column(String(45),  nullable=True)
    score_momentum = Column(String(45),  nullable=True)
    score_vola     = Column(String(45),  nullable=True)
    score_volume   = Column(String(45),  nullable=True)
    score_total    = Column(String(45),  nullable=True)
    created_date   = Column(String(45),  nullable=True)

    def to_dict(self):
        return {
            'log_id':         self.log_id,
            'ymd':            self.ymd,
            'times':          self.times,
            'user_id':        self.user_id,
            'time_frame':     self.time_frame,
            'bar_time':       self.bar_time.strftime("%Y-%m-%d %H:%M:%S") if self.bar_time else None,
            'coin_code':      self.coin_code,
            'action':         self.action,
            'buy_price':      float(self.buy_price)  if self.buy_price  is not None else None,
            'buy_amount':     float(self.buy_amount) if self.buy_amount is not None else None,
            'sell_price':     self.sell_price,
            'sell_amount':    self.sell_amount,
            'user_balance':   self.user_balance,
            'score_trend':    self.score_trend,
            'score_momentum': self.score_momentum,
            'score_vola':     self.score_vola,
            'score_volume':   self.score_volume,
            'score_total':    self.score_total,
            'created_date':   self.created_date,
        }
