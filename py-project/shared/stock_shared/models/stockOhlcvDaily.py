"""
stock_ohlcv_daily / stock_ohlcv_daily_state — 백테스트용 일봉 원천 (sql/43_stock_ohlcv_daily.sql).

가격은 **수정주가**(KIS FID_ORG_ADJ_PRC=0), KRX(J) 단일 기준.
분할·증자가 생기면 과거 가격 전체가 바뀌므로 StockOhlcvDailyJob 이 종목 단위로 통째로 재수집한다.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer, PrimaryKeyConstraint, String

from stock_shared.base import Base


class StockOhlcvDaily(Base):
    __tablename__ = "stock_ohlcv_daily"

    __table_args__ = (PrimaryKeyConstraint("stock_code", "trade_date"),)

    stock_code = Column(String(6), nullable=False)
    trade_date = Column(Date, nullable=False)
    open_price = Column(Integer, nullable=False)
    high_price = Column(Integer, nullable=False)
    low_price = Column(Integer, nullable=False)
    close_price = Column(Integer, nullable=False)
    volume = Column(BigInteger, nullable=False)     # 거래량(주)
    amount = Column(BigInteger, nullable=False)     # 거래대금(원)

    def to_dict(self):
        return {
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "amount": self.amount,
        }


class StockOhlcvDailyState(Base):
    __tablename__ = "stock_ohlcv_daily_state"

    __table_args__ = (PrimaryKeyConstraint("stock_code"),)

    stock_code = Column(String(6), nullable=False)
    first_date = Column(Date, nullable=True)
    last_date = Column(Date, nullable=True)
    bar_cnt = Column(Integer, nullable=False, default=0)
    backfill_done = Column(String(1), nullable=False, default="N")
    readjust_cnt = Column(Integer, nullable=False, default=0)
    last_readjust = Column(Date, nullable=True)
    last_error = Column(String(255), nullable=True)
    updated_at = Column(DateTime, nullable=False)

    def to_dict(self):
        return {
            "stock_code": self.stock_code,
            "first_date": self.first_date,
            "last_date": self.last_date,
            "bar_cnt": self.bar_cnt,
            "backfill_done": self.backfill_done,
            "readjust_cnt": self.readjust_cnt,
            "last_readjust": self.last_readjust,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }
