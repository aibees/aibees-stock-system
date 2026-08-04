from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Index
from sqlalchemy.dialects.mysql import DECIMAL
from app.domain.model.base import Base

class TradeLog(Base):
    __tablename__ = "trade_log"

    trade_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)

    user_id = Column(Integer)  # DEFAULT NULL
    coin_symbol = Column(String(20), nullable=False)  # 예: BTC/KRW
    action_type = Column(String(5), nullable=False)   # BUY/SELL 등 (ENUM 미사용, varchar(5))

    order_time = Column(DateTime, nullable=False)
    exec_time = Column(DateTime)

    price = Column(DECIMAL(18, 8), nullable=False)
    quantity = Column(DECIMAL(18, 8), nullable=False)
    total_amount = Column(DECIMAL(18, 8), nullable=False)  # price * quantity

    remain_qty = Column(DECIMAL(18, 8), nullable=False, default=0)
    fee = Column(DECIMAL(18, 8), nullable=False, default=0)
    pnl = Column(DECIMAL(18, 8), nullable=False, default=0)
    krw_balance = Column(DECIMAL(18, 8), nullable=False, default=0)

    note = Column(String(255))

    __table_args__ = (
        Index("idx_trade_log_exec_time", "exec_time"),
        Index("idx_trade_log_coin_symbol", "coin_symbol"),
    )

    def to_dict(self):
        def s(x):
            return str(x) if x is not None else None

        return {
            "trade_id": self.trade_id,
            "user_id": self.user_id,
            "coin_symbol": self.coin_symbol,
            "action_type": self.action_type,
            "order_time": self.order_time.isoformat() if self.order_time else None,
            "exec_time": self.exec_time.isoformat() if self.exec_time else None,
            "price": s(self.price),
            "quantity": s(self.quantity),
            "total_amount": s(self.total_amount),
            "remain_qty": s(self.remain_qty),
            "fee": s(self.fee),
            "pnl": s(self.pnl),
            "note": self.note,
            "krw_balance": s(self.krw_balance),
        }