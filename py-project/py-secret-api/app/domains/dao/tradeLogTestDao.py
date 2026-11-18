from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from app.domains.models.tradeLogTest import TradeLogTest

import logging
logging.basicConfig(level=logging.ERROR)


class TradeLogTestDao(BaseDao):
    model = TradeLogTest

    def __init__(self):
        self.__name__ = 'TradeLogTestDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by coin_code
    # ================================================================
    def select_by_coin(self, session, coin_code: str):
        stmt = select(TradeLogTest).where(
            TradeLogTest.coin_code == coin_code
        ).order_by(TradeLogTest.ymd.desc(), TradeLogTest.times.desc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by ymd
    # ================================================================
    def select_by_ymd(self, session, ymd: str):
        stmt = select(TradeLogTest).where(
            TradeLogTest.ymd == ymd
        ).order_by(TradeLogTest.times.asc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by ymd range
    # ================================================================
    def select_by_ymd_range(self, session, from_ymd: str, to_ymd: str):
        stmt = select(TradeLogTest).where(
            and_(
                TradeLogTest.ymd >= from_ymd,
                TradeLogTest.ymd <= to_ymd,
            )
        ).order_by(TradeLogTest.ymd.asc(), TradeLogTest.times.asc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # insert
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(TradeLogTest).values(
            ymd=data.get('ymd'),
            times=data.get('times'),
            user_id=data.get('user_id'),
            time_frame=data.get('time_frame'),
            bar_time=data.get('bar_time'),
            coin_code=data.get('coin_code'),
            action=data.get('action'),
            buy_price=data.get('buy_price'),
            buy_amount=data.get('buy_amount'),
            sell_price=data.get('sell_price'),
            sell_amount=data.get('sell_amount'),
            user_balance=data.get('user_balance'),
            score_trend=data.get('score_trend'),
            score_momentum=data.get('score_momentum'),
            score_vola=data.get('score_vola'),
            score_volume=data.get('score_volume'),
            score_total=data.get('score_total'),
            created_date=data.get('created_date'),
        )
        session.execute(stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
