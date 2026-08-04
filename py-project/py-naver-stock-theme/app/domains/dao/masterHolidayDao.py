from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from app.domains.models.masterHoliday import MasterHoliday

import logging
logging.basicConfig(level=logging.ERROR)


class MasterHolidayDao(BaseDao):
    model = MasterHoliday

    def __init__(self):
        self.__name__ = 'MasterHolidayDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by ymd
    # ================================================================
    def select_by_ymd(self, session, ymd: str):
        stmt = select(MasterHoliday).where(MasterHoliday.ymd == ymd)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # select holidays in range (ymd: yyyyMMdd 형식)
    # ================================================================
    def select_by_range(self, session, from_ymd: str, to_ymd: str):
        stmt = select(MasterHoliday).where(
            and_(
                MasterHoliday.ymd >= from_ymd,
                MasterHoliday.ymd <= to_ymd,
                MasterHoliday.is_holiday == 'Y',
            )
        ).order_by(MasterHoliday.ymd)
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # upsert
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        stmt = insert(MasterHoliday).values(
            ymd=data['ymd'],
            kind=data.get('kind'),
            name=data.get('name'),
            is_holiday=data.get('is_holiday'),
        )
        upsert_stmt = stmt.on_duplicate_key_update(
            kind=data.get('kind'),
            name=data.get('name'),
            is_holiday=data.get('is_holiday'),
        )
        session.execute(upsert_stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
