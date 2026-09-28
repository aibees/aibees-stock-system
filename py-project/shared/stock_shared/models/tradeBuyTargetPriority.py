from sqlalchemy import Column, DateTime, Integer, PrimaryKeyConstraint, String, func

from stock_shared.base import Base


class TradeBuyTargetPriority(Base):
    """Home.vue "최우선타겟" select 로 사용자가 지정한 종목 — 유저당 1건(전역, 날짜 무관).

    worker(BuyExecutor1)가 다음 영업일 09:00 정규장 라운드에서 읽어 그 날 매수타겟
    목록 중 이 종목을 1순위로 승격시키고, 라운드가 끝나면(성공/스킵 무관) 1회성으로
    stock_code/stock_name 을 NULL 로 되돌린다(15_trade_buy_target_priority_ddl.sql 참고).
    """

    __tablename__ = "trade_buy_target_priority"

    __table_args__ = (PrimaryKeyConstraint("user_id"),)

    user_id = Column(Integer, nullable=False)
    stock_code = Column(String(45), nullable=True)
    stock_name = Column(String(45), nullable=True)
    set_ymd = Column(String(8), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "set_ymd": self.set_ymd,
            "updated_at": self.updated_at,
        }
