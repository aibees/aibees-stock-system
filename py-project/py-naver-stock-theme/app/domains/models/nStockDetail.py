from sqlalchemy import Column, Integer, String, Double, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class NStockDetail(Base):
    __tablename__ = 'n_stock_detail'

    ymd = Column(String(8), nullable=False)
    theme_code = Column(String(5), nullable=False)
    stock_code = Column(String(6), nullable=False)
    stock_name = Column(String(100), nullable=True)
    per_rate = Column(Double, nullable=True)
    per_flow = Column(String(4), nullable=True)
    curr_price = Column(Integer, nullable=True)
    buy_price = Column(Integer, nullable=True)
    sell_price = Column(Integer, nullable=True)
    volume = Column(Integer, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('ymd', 'theme_code', 'stock_code'),
    )
    
    def to_dict(self):
        return {
            'ymd': self.ymd,
            'theme_code': self.theme_code,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'per_rate': self.per_rate,
            'per_flow': self.per_flow,
            'curr_price': self.curr_price,
            'buy_price': self.buy_price,
            'sell_price': self.sell_price,
            'volume': self.volume,
        }