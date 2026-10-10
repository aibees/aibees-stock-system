"""
stock_investor_daily — DB(stock) 스키마 기준 모델 (sql/31_stock_market_cap_investor.sql).
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, PrimaryKeyConstraint, String

from stock_shared.base import Base


class StockInvestorDaily(Base):
    __tablename__ = "stock_investor_daily"

    __table_args__ = (PrimaryKeyConstraint("ymd", "stock_code"),)

    ymd = Column(String(8), nullable=False)
    stock_code = Column(String(6), nullable=False)
    close_price = Column(Integer, nullable=True)
    prsn_qty = Column(BigInteger, nullable=True)   # 순매수 수량(주)
    frgn_qty = Column(BigInteger, nullable=True)
    orgn_qty = Column(BigInteger, nullable=True)
    prsn_amt = Column(BigInteger, nullable=True)   # 순매수 대금(백만원)
    frgn_amt = Column(BigInteger, nullable=True)
    orgn_amt = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            "ymd": self.ymd,
            "stock_code": self.stock_code,
            "close_price": self.close_price,
            "prsn_qty": self.prsn_qty,
            "frgn_qty": self.frgn_qty,
            "orgn_qty": self.orgn_qty,
            "prsn_amt": self.prsn_amt,
            "frgn_amt": self.frgn_amt,
            "orgn_amt": self.orgn_amt,
            "updated_at": self.updated_at,
        }
