from sqlalchemy import Column, BigInteger, Integer, DateTime, String, PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import DECIMAL
from app.domain.model.base import Base

class TradeBuyTargetStock(Base):
    __tablename__ = 'trade_buy_target_stock'

    ymd = Column(String(8), nullable=False)
    stock_code = Column(String(45), nullable=False)
    stock_name = Column(String(45))
    open = Column(DECIMAL(18, 8))
    high = Column(DECIMAL(18, 8))
    low = Column(DECIMAL(18, 8))
    close = Column(DECIMAL(18, 8))
    volume = Column(DECIMAL(18, 8))
    rate = Column(String(45))
    action_type = Column(String(45))
    macd_cross = Column(String(45))
    obv_cross = Column(String(45))
    is_vol_limit = Column(String(45))
    is_under_bb_upper = Column(String(45))
    is_over_on_mid = Column(String(45))
    is_vol_surge = Column(String(45))
    is_bb_mid_breakout = Column(String(45))
    eps = Column(String(45))
    pbr = Column(String(45))
    per = Column(String(45))
    roe = Column(String(45))
    peg = Column(String(45))

    # 종합 적합도 점수(0~100) 및 당일 매수타겟 내 순위(1=최상위)
    score = Column(DECIMAL(6, 2))
    rank_no = Column(Integer)


    __table_args__ = (
        PrimaryKeyConstraint("ymd", "stock_code"),
    )

    def to_dict(self):
        return {
            'ymd': self.ymd,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'open': float(self.open) if self.open is not None else None,
            'high': float(self.high) if self.high is not None else None,
            'low': float(self.low) if self.low is not None else None,
            'close': float(self.close) if self.close is not None else None,
            'volume': float(self.volume) if self.volume is not None else None,
            'rate': self.rate,
            'action_type': self.action_type,
            'macd_cross': self.macd_cross,
            'obv_cross': self.obv_cross,
            'is_vol_limit': self.is_vol_limit,
            'is_under_bb_upper': self.is_under_bb_upper,
            'is_over_on_mid': self.is_over_on_mid,
            'is_vol_surge': self.is_vol_surge,
            'is_bb_mid_breakout': self.is_bb_mid_breakout,
            'eps': self.eps,
            'pbr': self.pbr,
            'per': self.per,
            'roe': self.roe,
            'peg': self.peg,
            'score': float(self.score) if self.score is not None else None,
            'rank_no': self.rank_no
        }