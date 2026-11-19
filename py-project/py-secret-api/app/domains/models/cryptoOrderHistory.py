from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base

class CryptoOrderHistory(Base):
    __tablename__ = 'crypto_order_history'

    order_id      = Column(BigInteger,    primary_key=True, autoincrement=True)
    config_id     = Column(String(64),    nullable=False)
    symbol        = Column(String(16),    nullable=False)
    side          = Column(String(4),     nullable=False)
    order_price   = Column(DECIMAL(20,8), nullable=False)
    qty           = Column(DECIMAL(20,8), nullable=False)
    amount_krw    = Column(DECIMAL(15,2), nullable=False)
    avg_buy_price = Column(DECIMAL(20,8), nullable=True)
    profit_pct    = Column(DECIMAL(8,4),  nullable=True)
    signal_reason = Column(String(512),   nullable=True)
    status        = Column(String(16),    nullable=False, default='FILLED')
    created_at    = Column(DateTime,      nullable=False)

    def to_dict(self):
        return {
            'order_id':      self.order_id,
            'config_id':     self.config_id,
            'symbol':        self.symbol,
            'side':          self.side,
            'order_price':   float(self.order_price)   if self.order_price   is not None else None,
            'qty':           float(self.qty)           if self.qty           is not None else None,
            'amount_krw':    float(self.amount_krw)    if self.amount_krw    is not None else None,
            'avg_buy_price': float(self.avg_buy_price) if self.avg_buy_price is not None else None,
            'profit_pct':    float(self.profit_pct)    if self.profit_pct    is not None else None,
            'signal_reason': self.signal_reason,
            'status':        self.status,
            'created_at':    self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
