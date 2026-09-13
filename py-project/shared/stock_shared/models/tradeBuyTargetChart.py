from sqlalchemy import Column, String, Text, DateTime, PrimaryKeyConstraint, func

from stock_shared.base import Base


class TradeBuyTargetChart(Base):
    """trade_buy_target_stock 의 부속 테이블. 종목당 최근 120영업일 OHLCV+SMA
    간이차트 데이터를 JSON 문자열로 저장한다(컬럼화하지 않음)."""

    __tablename__ = "trade_buy_target_chart"

    ymd = Column(String(8), nullable=False)
    stock_code = Column(String(45), nullable=False)
    chart_data = Column(Text, nullable=False)  # JSON 배열: [{date,open,high,low,close,volume,ma20,ma60}, ...]
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (PrimaryKeyConstraint("ymd", "stock_code"),)

    def to_dict(self):
        return {
            "ymd": self.ymd,
            "stock_code": self.stock_code,
            "chart_data": self.chart_data,
            "created_at": self.created_at,
        }
