from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.userWallet import UserWallet

import logging
logging.basicConfig(level=logging.ERROR)


class UserWalletDao(BaseDao):
    model = UserWallet

    def __init__(self):
        self.__name__ = 'UserWalletDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by user_id
    # ================================================================
    def select_by_user_id(self, session, user_id: int):
        stmt = select(UserWallet).where(UserWallet.user_id == user_id)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # upsert
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        stmt = insert(UserWallet).values(
            user_id=data['user_id'],
            user_balance=data['user_balance'],
        )
        upsert_stmt = stmt.on_duplicate_key_update(
            user_balance=data['user_balance'],
        )
        session.execute(upsert_stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
