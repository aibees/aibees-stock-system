from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.cryptoOrderHistory import CryptoOrderHistory

import logging
logging.basicConfig(level=logging.ERROR)


class CryptoOrderHistoryDao(BaseDao):
    model = CryptoOrderHistory

    def __init__(self):
        self.__name__ = 'CryptoOrderHistoryDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by config_id
    # ================================================================
    def select_by_config_id(self, session, config_id: str):
        stmt = select(CryptoOrderHistory).where(
            CryptoOrderHistory.config_id == config_id
        ).order_by(CryptoOrderHistory.created_at.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by symbol
    # ================================================================
    def select_by_symbol(self, session, symbol: str):
        stmt = select(CryptoOrderHistory).where(
            CryptoOrderHistory.symbol == symbol
        ).order_by(CryptoOrderHistory.created_at.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by date range
    # ================================================================
    def select_by_date_range(self, session, start_dt, end_dt):
        stmt = select(CryptoOrderHistory).where(
            and_(
                CryptoOrderHistory.created_at >= start_dt,
                CryptoOrderHistory.created_at <= end_dt,
            )
        ).order_by(CryptoOrderHistory.created_at.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # insert
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(CryptoOrderHistory).values(
            config_id=data['config_id'],
            symbol=data['symbol'],
            side=data['side'],
            order_price=data['order_price'],
            qty=data['qty'],
            amount_krw=data['amount_krw'],
            avg_buy_price=data.get('avg_buy_price'),
            profit_pct=data.get('profit_pct'),
            signal_reason=data.get('signal_reason'),
            status=data.get('status', 'FILLED'),
            created_at=data['created_at'],
        )
        session.execute(stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
