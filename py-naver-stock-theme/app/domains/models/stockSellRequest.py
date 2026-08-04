from sqlalchemy import Column, String, Integer, PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class StockSellRequest(Base):
    """
    매도 체크 희망 종목 입력 테이블 (SellRequest.vue 관리)

    - PK : (user_id, stock_code) 복합키
    - user_id 는 클라이언트가 보내지 않고 JWT 에서 추출한 값으로만 채워짐
    - entry_price / hold_qty 는 DDL 상 DECIMAL(18,8)
    """

    __tablename__ = 'stock_sell_request'

    # Primary Keys (복합키)
    user_id = Column(Integer, nullable=False)
    stock_code = Column(String(45), nullable=False)  # 종목코드

    # Stock Info
    stock_name = Column(String(45))                  # 종목명
    entry_date = Column(String(8))                   # 매수 체결일 YYYYMMDD
    entry_price = Column(DECIMAL(18, 8))             # 매수 평균단가
    hold_qty = Column(DECIMAL(18, 8))                # 보유 수량
    memo = Column(String(255))                       # 사용자 메모
    enabled_flag = Column(String(1), nullable=False, default='Y')  # Y: 배치 체크 대상 / N: 제외

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "stock_code"),
    )

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'entry_date': self.entry_date,
            'entry_price': float(self.entry_price) if self.entry_price is not None else None,
            'hold_qty': float(self.hold_qty) if self.hold_qty is not None else None,
            'memo': self.memo,
            'enabled_flag': self.enabled_flag,
        }
