from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from app.domains.models.campaign import Campaign

import logging
logging.basicConfig(level=logging.ERROR)


class CampaignDao(BaseDao):
    model = Campaign

    def __init__(self):
        self.__name__ = 'CampaignDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by ymd
    # ================================================================
    def select_by_ymd(self, session, ymd: str):
        stmt = select(Campaign).where(Campaign.ymd == ymd)
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # insert
    # ================================================================
    def insert(self, session, data: dict) -> None:
        stmt = insert(Campaign).values(
            ymd=data['ymd'],
            campaign=data.get('campaign'),
            adv=data.get('adv'),
            card_nm=data.get('card_nm'),
            keyword=data.get('keyword'),
            exposed=data.get('exposed'),
            clicked=data.get('clicked'),
            avg_click_amt=data.get('avg_click_amt'),
            total_amt=data.get('total_amt'),
        )
        session.execute(stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
