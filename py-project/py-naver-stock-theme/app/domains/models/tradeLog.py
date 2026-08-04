from sqlalchemy import Column, BigInteger, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradeLog(Base):
    __tablename__ = 'trade_log'

    trade_id     = Column(BigInteger,    primary_key=True, autoincrement=True)
    user_id      = Column(Integer,       nullable=True)
    coin_symbol  = Column(String(20),    nullable=False)
    action_type  = Column(String(15),    nullable=False)
    order_time   = Column(DateTime,      nullable=False)
    exec_time    = Column(DateTime,      nullable=True)
    price        = Column(DECIMAL(18,8), nullable=False)
    quantity     = Column(DECIMAL(18,8), nullable=False)
    total_amount = Column(DECIMAL(18,8), nullable=False)
    remain_qty   = Column(DECIMAL(18,8), nullable=False, default='0.00000000')
    fee          = Column(DECIMAL(18,8), nullable=False, default='0.00000000')
    pnl          = Column(DECIMAL(18,8), nullable=False, default='0.00000000')
    note         = Column(String(255),   nullable=True)
    krw_balance  = Column(DECIMAL(18,8), nullable=False)
    sma_checker  = Column(String(1),     nullable=True)
    rsi_checker  = Column(String(1),     nullable=True)
    macd_checker = Column(String(1),     nullable=True)
    stk_checker  = Column(String(1),     nullable=True)
    obv_checker  = Column(String(1),     nullable=True)
    score        = Column(DECIMAL(5,2),  nullable=True)

    def to_dict(self):
        def _f(v):
            return float(v) if v is not None else None

        return {
            'trade_id':     self.trade_id,
            'user_id':      self.user_id,
            'coin_symbol':  self.coin_symbol,
            'action_type':  self.action_type,
            'order_time':   self.order_time.strftime("%Y-%m-%d %H:%M:%S") if self.order_time else None,
            'exec_time':    self.exec_time.strftime("%Y-%m-%d %H:%M:%S")  if self.exec_time  else None,
            'price':        _f(self.price),
            'quantity':     _f(self.quantity),
            'total_amount': _f(self.total_amount),
            'remain_qty':   _f(self.remain_qty),
            'fee':          _f(self.fee),
            'pnl':          _f(self.pnl),
            'note':         self.note,
            'krw_balance':  _f(self.krw_balance),
            'sma_checker':  self.sma_checker,
            'rsi_checker':  self.rsi_checker,
            'macd_checker': self.macd_checker,
            'stk_checker':  self.stk_checker,
            'obv_checker':  self.obv_checker,
            'score':        _f(self.score),
        }
