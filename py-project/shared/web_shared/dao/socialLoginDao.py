"""
소셜 로그인(네이버) 계정 연결 / 신규 가입 DAO.

user_login_type(user_id, login_type, enabled_flag, provider_uid, linked_date) 가 연결의 정본이다
(sql/26_naver_login_link.sql). 한 사용자당 로그인 방식별 1행, 한 소셜 계정(provider_uid)은 한 사용자에게만.
트랜잭션은 호출측(요청 종료 시 commit, 실패 시 라우터가 rollback)이 관리한다.
"""
import hashlib
import secrets
from datetime import datetime

from sqlalchemy import func, select, text

from stock_shared.models.userAuth import UserAuth
from stock_shared.models.userConsent import UserConsent
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

    def select_consent(self, session, user_id, consent_type):
        """동의 기록(UserConsent) 또는 None."""
        return session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type,
            )
        ).scalars().first()

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

    def select_user_by_login_id(self, session, login_id):
        """로그인 아이디(user_master.login_id)로 사용자 1명. 없으면 None."""
        return session.execute(select(UserMaster).where(UserMaster.login_id == login_id)).scalars().first()

    def create_user(self, session, *, user_name, email, phone, login_type, provider_uid, auth_id, password=None,
                    login_id=None):
        """신규 가입(소셜 또는 이메일). 반환: 새 user_id.

        user_master.user_id 는 AUTO_INCREMENT 가 아니라 MAX+1 로 채번한다(기존 사용자 생성 관례).
        password 가 있으면(이메일 가입) salt+password 를 SHA-256 으로 저장한다 — authService.emailProcess 의
        검증 방식과 같다. 없으면(소셜 가입) salt/pswd 가 NOT NULL 이라 추측 불가능한 임의 값을 넣는다 —
        EMAIL 로그인 행을 만들지 않으므로 이 값으로 로그인할 수는 없다.
        """
        now = datetime.now()
        new_id = (session.execute(select(func.max(UserMaster.user_id))).scalar() or 0) + 1

        session.add(UserMaster(user_id=new_id, login_id=login_id, user_name=user_name, email=email, user_phone=phone))
        salt = secrets.token_hex(8)  # 16자 (user_detail.salt VARCHAR(16))
        session.add(UserDetail(user_id=new_id, salt=salt,
                               pswd=hashlib.sha256((salt + (password or secrets.token_hex(32))).encode()).hexdigest(),
                               reset_flag='N',
                               created_date=now, updated_date=now))
        session.add(UserLoginType(user_id=new_id, login_type=login_type, enabled_flag='Y',
                                  provider_uid=provider_uid, linked_date=now))
        session.add(UserAuth(user_id=new_id, auth_id=auth_id, enabled_flag='Y',
                             created_date=now, updated_date=now))
        session.flush()
        return new_id

    # 동의
    # ================================================================
    def save_consent(self, session, user_id, consent_type, version):
        """동의 기록 저장(행이 있으면 version/시각 갱신 — 처리방침 개정 후 재동의)."""
        now = datetime.now()
        row = self.select_consent(session, user_id, consent_type)
        if row is None:
            session.add(UserConsent(user_id=user_id, consent_type=consent_type,
                                    version=version, agreed_date=now))
        else:
            row.version = version
            row.agreed_date = now
        session.flush()
        if self._has_consent_history(session):
            session.execute(text(
                "INSERT INTO user_consent_history (user_id, consent_type, version, agreed_date) "
                "VALUES (:uid, :ctype, :ver, :at)"),
                {"uid": user_id, "ctype": consent_type, "ver": version, "at": now})

    # 동의 이력 테이블(sql/yangbong/010)은 양봉 스키마에만 있다 — 스키마(DATABASE())별로 한 번만 확인한다.
    _consent_history_cache = {}

    def _has_consent_history(self, session) -> bool:
        schema = session.execute(text("SELECT DATABASE()")).scalar()
        if schema not in self._consent_history_cache:
            self._consent_history_cache[schema] = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'user_consent_history'")).scalar() > 0
        return self._consent_history_cache[schema]
