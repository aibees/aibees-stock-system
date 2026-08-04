from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.tradeLog import TradeLog

import logging
logging.basicConfig(level=logging.ERROR)


class TradeLogDao(BaseDao):
    model = TradeLog

    def __init__(self):
        self.__name__ = 'TradeLogDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by coin_symbol
    # ================================================================
    def select_by_symbol(self, session, coin_symbol: str):
        stmt = select(TradeLog).where(
            TradeLog.coin_symbol == coin_symbol
        ).order_by(TradeLog.order_time.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by user_id
    # ================================================================
    def select_by_user(self, session, user_id: int):
        stmt = select(TradeLog).where(
            TradeLog.user_id == user_id
        ).order_by(TradeLog.order_time.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by exec_time range
    # ================================================================
    def select_by_exec_time_range(self, session, from_dt, to_dt):
        stmt = select(TradeLog).where(
            and_(
                TradeLog.exec_time >= from_dt,
                TradeLog.exec_time <= to_dt,
            )
        ).order_by(TradeLog.exec_time.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # insert
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(TradeLog).values(
            user_id=data.get('user_id'),
            coin_symbol=data['coin_symbol'],
            action_type=data['action_type'],
            order_time=data['order_time'],
            exec_time=data.get('exec_time'),
            price=data['price'],
            quantity=data['quantity'],
            total_amount=data['total_amount'],
            remain_qty=data.get('remain_qty', 0),
            fee=data.get('fee', 0),
            pnl=data.get('pnl', 0),
            note=data.get('note'),
            krw_balance=data['krw_balance'],
            sma_checker=data.get('sma_checker'),
            rsi_checker=data.get('rsi_checker'),
            macd_checker=data.get('macd_checker'),
            stk_checker=data.get('stk_checker'),
            obv_checker=data.get('obv_checker'),
            score=data.get('score'),
        )
        session.execute(stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
