"""
trade_buy_target_stock_test — 매수추천 알고리즘 오프라인 재현 테스트용 테이블.

trade_buy_target_stock(운영 테이블)과 완전히 동일한 구조를 그대로 복제한 것으로,
운영 데이터를 건드리지 않고 새 알고리즘(kospi1.py) 결과를 저장/비교하기 위해 쓴다.
테이블 생성은 py-project/sql/trade_buy_target_stock_test.sql 참고.

※ 스키마 변경 시 tradeBuyTargetStock.py 와 함께 이 파일도 갱신할 것.
"""
from sqlalchemy import Column, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class TradeBuyTargetStockTest(Base):
    __tablename__ = "trade_buy_target_stock_test"

    __table_args__ = (PrimaryKeyConstraint("ymd", "stock_code"),)

    ymd = Column(String(8), nullable=False)
    stock_code = Column(String(45), nullable=False)
    rank_no = Column(Integer, nullable=True)
    stock_name = Column(String(45), nullable=True)
    open = Column(DECIMAL(18, 8), nullable=True)
    high = Column(DECIMAL(18, 8), nullable=True)
    low = Column(DECIMAL(18, 8), nullable=True)
    close = Column(DECIMAL(18, 8), nullable=True)
    volume = Column(DECIMAL(18, 8), nullable=True)
    rate = Column(String(45), nullable=True)
    action_type = Column(String(45), nullable=True)
    macd_cross = Column(String(45), nullable=True)
    obv_cross = Column(String(45), nullable=True)
    is_vol_limit = Column(String(45), nullable=True)
    is_under_bb_upper = Column(String(45), nullable=True)
    is_over_on_mid = Column(String(45), nullable=True)
    is_vol_surge = Column(String(45), nullable=True)
    is_bb_mid_breakout = Column(String(45), nullable=True)
    eps = Column(String(45), nullable=True)
    pbr = Column(String(45), nullable=True)
    per = Column(String(45), nullable=True)
    roe = Column(String(45), nullable=True)
    peg = Column(String(45), nullable=True)
    score = Column(DECIMAL(6, 2), nullable=True)

    def to_dict(self):
        return {
            "ymd": self.ymd,
            "stock_code": self.stock_code,
            "rank_no": self.rank_no,
            "stock_name": self.stock_name,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "rate": self.rate,
            "action_type": self.action_type,
            "macd_cross": self.macd_cross,
            "obv_cross": self.obv_cross,
            "is_vol_limit": self.is_vol_limit,
            "is_under_bb_upper": self.is_under_bb_upper,
            "is_over_on_mid": self.is_over_on_mid,
            "is_vol_surge": self.is_vol_surge,
            "is_bb_mid_breakout": self.is_bb_mid_breakout,
            "eps": self.eps,
            "pbr": self.pbr,
            "per": self.per,
            "roe": self.roe,
            "peg": self.peg,
            "score": self.score,
        }
