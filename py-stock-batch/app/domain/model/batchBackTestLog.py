from sqlalchemy import Column, Integer, DateTime, String, BigInteger, Index
from sqlalchemy.dialects.mysql import DECIMAL, ENUM
from app.domain.model.base import Base

class TradeLog(Base):
    __tablename__ = "trade_log"

    trade_id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)  # 거래 식별자
    user_id = Column(Integer, nullable=False)
    coin_symbol = Column(String(20), nullable=False)  # 예: BTC/KRW
    action_type = Column(String(15), nullable=False)   # 거래유형: BUY / SELL

    order_time = Column(DateTime, nullable=False)
    exec_time = Column(DateTime, nullable=True)

    price = Column(DECIMAL(18, 8), nullable=False) # 체결 단가
    quantity = Column(DECIMAL(18, 8), nullable=False) # 체결 수량
    total_amount = Column(DECIMAL(18, 8), nullable=False)  # price * quantity

    remain_qty = Column(DECIMAL(18, 8), nullable=False, default=0)
    fee = Column(DECIMAL(18, 8), nullable=False, default=0) # 체결 수수료
    pnl = Column(DECIMAL(18, 8), nullable=False, default=0) # 체결로 인한 손익
    krw_balance = Column(DECIMAL(18, 8), nullable=False, default=0)

    # log trace 용
    sma_checker = Column(String(1), nullable=True)
    rsi_checker = Column(String(1), nullable=True)
    macd_checker = Column(String(1), nullable=True)
    stk_checker = Column(String(1), nullable=True)
    obv_checker = Column(String(1), nullable=True)

    score = Column(DECIMAL(5, 2), nullable=True)

    note = Column(String(255), nullable=True)

    __table_args__ = (
        Index("idx_trade_log_exec_time", "exec_time"),
        Index("idx_trade_log_coin_symbol", "coin_symbol"),
    )

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "coin_symbol": self.coin_symbol,
            "side": self.action_type,
            "order_time": self.order_time.isoformat() if self.order_time else None,
            "exec_time": self.exec_time.isoformat() if self.exec_time else None,
            "price": str(self.price) if self.price is not None else None,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "total_amount": str(self.total_amount) if self.total_amount is not None else None,
            "remain_qty": str(self.remain_qty) if self.remain_qty is not None else None,
            "fee": str(self.fee) if self.fee is not None else None,
            "pnl": str(self.pnl) if self.pnl is not None else None,
            "note": self.note,
            "sma_checker": str(self.sma_checker) if self.sma_checker is not None else None,
            "rsi_checker": str(self.rsi_checker) if self.rsi_checker is not None else None,
            "macd_checker": str(self.macd_checker) if self.macd_checker is not None else None,
            "stk_checker": str(self.stk_checker) if self.stk_checker is not None else None,
            "obv_checker": str(self.obv_checker) if self.obv_checker is not None else None,
            "krw_balance": str(self.krw_balance) if self.krw_balance is not None else None,
        }