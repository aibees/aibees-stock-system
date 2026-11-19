from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.userInterestStocks import UserInterestStocks

import logging
logging.basicConfig(level=logging.ERROR)


class UserInterestStocksDao(BaseDao):
    model = UserInterestStocks

    def __init__(self):
        self.__name__ = 'UserInterestStocksDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by group_id
    # ================================================================
    def select_by_group(self, session, group_id: int):
        stmt = select(UserInterestStocks).where(
            UserInterestStocks.group_id == group_id
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select enabled stocks by group_id
    # ================================================================
    def select_enabled_by_group(self, session, group_id: int):
        stmt = select(UserInterestStocks).where(
            and_(
                UserInterestStocks.group_id == group_id,
                UserInterestStocks.enabled_flag == 'Y',
            )
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # insert
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(UserInterestStocks).values(
            group_id=data['group_id'],
            stock_code=data['stock_code'],
            status=data.get('status', 'ACTIVE'),
            added_at=data.get('added_at'),
            enabled_flag=data.get('enabled_flag', 'Y'),
            curr_balance=data.get('curr_balance'),
        )
        session.execute(stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
