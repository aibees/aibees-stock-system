from sqlalchemy import select

from app.domains.models.userDetail import UserDetail

import logging

logging.basicConfig(level=logging.ERROR)


class UserDetailDao:
    def __init__(self):
        self.__name__ = 'UserDetailDao'

    # select KIS 인증정보 (kis_id, kis_account, app_key, sec_key)
    # ================================================================
    def select_kis_credentials(self, session, user_id: int):
        """
        user_detail 에서 KIS 실투자 인증정보를 조회합니다.
        반환: {id, account, app_key, sec_key} 또는 None
        """
        stmt = select(
            UserDetail.kis_id,
            UserDetail.kis_account,
            UserDetail.kis_access_key,
            UserDetail.kis_secret_key,
        ).where(
            UserDetail.user_id == user_id
        )

        row = session.execute(stmt).first()
        if row is None:
            return None

        return {
            'id': row.kis_id,
            'account': row.kis_account,
            'app_key': row.kis_access_key,
            'sec_key': row.kis_secret_key,
        }

    # select UPBIT 인증정보 (access, secret)
    # ================================================================
    def select_upbit_credentials(self, session, user_id: int):
        """
        user_detail 에서 UPBIT 인증정보를 조회합니다.
        반환: {access, secret} 또는 None
        """
        stmt = select(
            UserDetail.upbit_access_key,
            UserDetail.upbit_secret_key,
        ).where(
            UserDetail.user_id == user_id
        )

        row = session.execute(stmt).first()
        if row is None:
            return None

        return {
            'access': row.upbit_access_key,
            'secret': row.upbit_secret_key,
        }
