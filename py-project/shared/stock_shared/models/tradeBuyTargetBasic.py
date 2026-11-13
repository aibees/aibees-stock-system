"""
trade_buy_target_basic — 기본 단계(BASIC) 추천 종목. 옛 기계식 알고리즘(watch 게이트)이 고른 종목만 담는다.

기존 trade_buy_target_stock(2파 돌파 종합순위, 워커가 읽는 테이블)과 **분리**해서 둔다:
  · 워커·성과·시뮬은 계속 trade_buy_target_stock 만 본다 → 매매 경로가 이 테이블의 영향을 받지 않는다.
  · 기본 단계 열람자에게는 이 테이블 종목만 보여 준다(서버 RecoLevel).
컬럼은 trade_buy_target_stock 에서 종합순위(momentum_composite/composite_rank_no)만 뺀 같은 모양이다.
DDL: py-project/sql/2026-11-13_trade_buy_target_basic.sql
"""
from sqlalchemy import Column, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class TradeBuyTargetBasic(Base):
    __tablename__ = "trade_buy_target_basic"

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
    shape_proba = Column(DECIMAL(6, 4), nullable=True)       # 참고용(모델 추론값). 화면에는 고급 이상에서만 쓴다
    shape_exhaustion = Column(String(1), nullable=True)

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
            "shape_proba": self.shape_proba,
            "shape_exhaustion": self.shape_exhaustion,
        }
