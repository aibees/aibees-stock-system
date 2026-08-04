from app.domains.models.userDetail import UserDetail
from app.domains.models.userMaster import UserMaster
from app.domains.models.userLoginType import UserLoginType
from app.domains.models.userAuth import UserAuth
from app.domains.models.userRole import UserRole
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
from datetime import datetime
import logging

logging.basicConfig(level=logging.ERROR)

class UserMasterDao:
    def __init__(self):
        self.__name__ = 'UserMasterDao'
        
    # select
    # ================================================================
    def select_user_by_phone(self, session, param):
        stmt = select(
            UserMaster
        ).where(
            UserMaster.user_phone == param['user_phone'],
            UserMaster.type == param['type'].upper()
        )
        
        results = session.execute(stmt).scalars().first()
        if results is None :
            return None
        else:
            return results.to_dict()
        
    # select userInfo
    # ================================================================
    def select_user_authinfo(self, session, param):
        stmt = select(
            UserMaster, UserLoginType, UserDetail
        ).join(
            UserLoginType, UserMaster.user_id == UserLoginType.user_id
        ).join(
            UserDetail, UserMaster.user_id == UserDetail.user_id
        ).where(
            UserLoginType.enabled_flag == 'Y',
            UserLoginType.login_type == param['type'],
            UserMaster.email == param['email']
        )
        
        results = session.execute(stmt).all()
        
        if results is None :
            return None
        else:
            flattern = []
            for usermaster, userlogintype, userdetail in results:
                flattern.append({**usermaster.to_dict(), **userlogintype.to_dict(), **userdetail.to_dict()})

            return flattern
        
    # select user_id by email (EMAIL 타입)
    # ================================================================
    def select_user_id_by_email(self, session, email: str):
        stmt = select(UserMaster.user_id).where(
            UserMaster.email == email
        )
        return session.execute(stmt).scalar_one_or_none()

    # update password & reset_flag
    # ================================================================
    def update_user_password(self, session, user_id: int, new_salt: str, new_pswd: str):
        """
        user_detail 의 salt / pswd 를 교체하고
        reset_flag 를 'N' 으로 클리어한 뒤 updated_date 를 현재 시각으로 갱신.
        """
        stmt = (
            update(UserDetail)
            .where(UserDetail.user_id == user_id)
            .values(
                salt=new_salt,
                pswd=new_pswd,
                reset_flag='N',
                err_cnt=0,
                updated_date=datetime.utcnow()
            )
        )
        session.execute(stmt)

    def select_user_roleinfo(self, session, param):
        stmt = select(
            UserAuth, UserRole
        ).join(
            UserAuth, UserAuth.auth_id == UserRole.auth_id
        ).where(
            UserAuth.auth_id == UserRole.auth_id,
            UserAuth.user_id == param['user_id'],
            UserAuth.enabled_flag == 'Y'
        )
        
        resultArr = []
        results = session.execute(stmt).all()
        for userAuth, userRole in results:
            resultArr.append({
                'auth_id': userRole.auth_id,
                'auth_nm': userRole.auth_nm
            })
        return resultArr
        