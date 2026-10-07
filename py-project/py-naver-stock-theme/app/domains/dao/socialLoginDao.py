"""
소셜 로그인(네이버) 계정 연결 / 신규 가입 DAO.

user_login_type(user_id, login_type, enabled_flag, provider_uid, linked_date) 가 연결의 정본이다
(sql/26_naver_login_link.sql). 한 사용자당 로그인 방식별 1행, 한 소셜 계정(provider_uid)은 한 사용자에게만.
트랜잭션은 호출측(요청 종료 시 commit, 실패 시 라우터가 rollback)이 관리한다.
"""
import hashlib
import secrets
from datetime import datetime

from sqlalchemy import func, select

from stock_shared.models.userAuth import UserAuth
from stock_shared.models.userDetail import UserDetail
from stock_shared.models.userLoginType import UserLoginType
from stock_shared.models.userMaster import UserMaster


class SocialLoginDao:
    def __init__(self):
        self.name = 'SocialLoginDao'

    # 조회
    # ================================================================
    def select_by_provider_uid(self, session, login_type, provider_uid):
        """이 소셜 계정이 연결된 행(UserLoginType) 또는 None."""
        return session.execute(
            select(UserLoginType).where(
                UserLoginType.login_type == login_type,
                UserLoginType.provider_uid == provider_uid,
            )
        ).scalars().first()

    def select_login_type(self, session, user_id, login_type):
        return session.execute(
            select(UserLoginType).where(
                UserLoginType.user_id == user_id,
                UserLoginType.login_type == login_type,
            )
        ).scalars().first()

    def select_users_by_email(self, session, email):
        """이메일 일치 사용자(대소문자 무시). 자동 연결은 정확히 1명일 때만 한다."""
        return session.execute(
            select(UserMaster).where(func.lower(UserMaster.email) == email.lower())
        ).scalars().all()

    def select_user(self, session, user_id):
        return session.execute(
            select(UserMaster).where(UserMaster.user_id == user_id)
        ).scalars().first()

    def phone_in_use(self, session, phone):
        return session.execute(
            select(UserMaster.user_id).where(UserMaster.user_phone == phone)
        ).first() is not None

    # 연결 / 가입
    # ================================================================
    def link(self, session, user_id, login_type, provider_uid):
        """기존 사용자에 소셜 계정을 연결(행이 있으면 갱신, 없으면 생성)."""
        now = datetime.now()
        row = self.select_login_type(session, user_id, login_type)
        if row is None:
            session.add(UserLoginType(user_id=user_id, login_type=login_type, enabled_flag='Y',
                                      provider_uid=provider_uid, linked_date=now))
        else:
            row.provider_uid = provider_uid
            row.linked_date = now
        session.flush()

    def create_user(self, session, *, user_name, email, phone, login_type, provider_uid, auth_id):
        """소셜 계정으로 신규 가입. 반환: 새 user_id.

        user_master.user_id 는 AUTO_INCREMENT 가 아니라 MAX+1 로 채번한다(기존 사용자 생성 관례).
        user_detail 은 salt/pswd 가 NOT NULL 이라 추측 불가능한 임의 값을 넣는다 — EMAIL 로그인 행을
        만들지 않으므로 이 값으로 로그인할 수는 없다.
        """
        now = datetime.now()
        new_id = (session.execute(select(func.max(UserMaster.user_id))).scalar() or 0) + 1

        session.add(UserMaster(user_id=new_id, user_name=user_name, email=email, user_phone=phone))
        salt = secrets.token_hex(8)  # 16자 (user_detail.salt VARCHAR(16))
        session.add(UserDetail(user_id=new_id, salt=salt,
                               pswd=hashlib.sha256((salt + secrets.token_hex(32)).encode()).hexdigest(),
                               created_date=now, updated_date=now))
        session.add(UserLoginType(user_id=new_id, login_type=login_type, enabled_flag='Y',
                                  provider_uid=provider_uid, linked_date=now))
        session.add(UserAuth(user_id=new_id, auth_id=auth_id, enabled_flag='Y',
                             created_date=now, updated_date=now))
        session.flush()
        return new_id
