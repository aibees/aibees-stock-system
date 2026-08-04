from sqlalchemy import select, update, and_, func, desc, delete, or_
from sqlalchemy.dialects.mysql import insert

from app.common.utils.aesUtils import aesUtils
from app.domain.model.userMaster import UserMaster
from app.domain.model.userDetail import UserDetail
from app.domain.model.userOptions import UserOptions
from app.domain.model.userInterestGroups import UserInterestGroups
from app.domain.model.userInterestStocks import UserInterestStocks

class UserMasterDao:
    def __init__(self):
        self.__name__ = 'UserMasterDao'

    def select_user_stock_options(self, session, data):
        stmt = select(
            UserMaster, UserOptions
        ).join(
            UserOptions, UserMaster.user_id == UserOptions.user_id
        ).where(
            UserMaster.user_id == data['user_id']
        )

        result = session.execute(stmt).mappings().all()
        return [
            {
                **row['UserMaster'].to_dict(),
                **row['UserOptions'].to_dict()
            }
            for row in result
        ][0]

    def select_target_emails(self, session):
        """
        UserOptions의 stock_buy_target_mail_flag가 'Y'인 사용자 이메일 리스트 조회.
        """
        stmt = select(
            UserMaster.email
        ).join(
            UserOptions, UserMaster.user_id == UserOptions.user_id
        ).where(
            UserOptions.stock_buy_target_mail_flag == 'Y'
        )
        return session.execute(stmt).scalars().all()

    def select_sell_target_users(self, session) -> list:
        """
        매도 알림 대상 유저 전체 조회.
        stock_sell_mail_flag='Y' 또는 stock_sell_tele_flag='Y' 인 유저를
        UserMaster + UserOptions + UserDetail 조인하여 반환.
        """
        stmt = select(
            UserMaster, UserOptions, UserDetail
        ).join(
            UserOptions, UserMaster.user_id == UserOptions.user_id
        ).join(
            UserDetail, UserMaster.user_id == UserDetail.user_id
        ).where(
            or_(
                UserOptions.stock_sell_mail_flag == 'Y',
                UserOptions.stock_sell_tele_flag == 'Y',
            )
        )
        result = session.execute(stmt).mappings().all()
        return [
            {
                **row['UserMaster'].to_dict(),
                **row['UserOptions'].to_dict(),
                'tele_bot_id':  row['UserDetail'].tele_bot_id,
                'tele_chat_id': row['UserDetail'].tele_chat_id,
            }
            for row in result
        ]

    def select_user_upbit_options(self, session, data):
        conditions = []
        stmt = select(
            UserMaster, UserOptions, UserDetail.upbit_access_key, UserDetail.upbit_secret_key
        ).join(
            UserMaster, UserMaster.user_id == UserOptions.user_id
        ).join(
            UserDetail, UserOptions.user_id == UserDetail.user_id
        ).where(
            UserOptions.upbit_push_flag == data['upbit_options']
        )

        result = session.execute(stmt).mappings().all()
        return [
            {
                **row['UserMaster'].to_dict(),
                **row['UserOptions'].to_dict(),
                # 'upbit_access_key': aesUtils.decrypt(row['upbit_access_key']),
                # 'upbit_secret_key': aesUtils.decrypt(row['upbit_secret_key']),
                'upbit_access_key': row['upbit_access_key'],
                'upbit_secret_key': row['upbit_secret_key'],
            }
            for row in result
        ]

    def select_user_target_code(self, session, data):
        stmt = select(
            UserInterestGroups, UserInterestStocks
        ).join(
            UserInterestStocks, UserInterestGroups.group_id == UserInterestStocks.group_id
        ).where(
            UserInterestGroups.user_id == data['user_id'],
            UserInterestGroups.division == data['division'],
            UserInterestStocks.enabled_flag == 'Y'
        )

        result = session.execute(stmt).mappings().all()

        return [
            {
                **row['UserInterestGroups'].to_dict(),
                **row['UserInterestStocks'].to_dict()
            }
            for row in result
        ]

    def update_interest_stock(self, session, data):
        stmt = update(
            UserInterestStocks
        ).where(
            UserInterestStocks.group_id == data['group_id'],
            UserInterestStocks.stock_code == data['stock_code']
        ).values(
            status = data['status']
        )

        session.execute(stmt)
        session.commit()
