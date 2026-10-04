import os
from datetime import datetime

from sqlalchemy import delete, select

from app.domains.models.masterMenu import MasterMenu
from app.domains.models.roleMenu import RoleFeature, RoleMenu
from stock_shared.models.userAuth import UserAuth
from stock_shared.models.userMaster import UserMaster
from stock_shared.models.userRole import UserRole

ADMIN_AUTH_ID = 'ADMIN'

# 슈퍼유저(사용자 권한 부여 화면을 쓸 수 있는 사람). role 이 아니라 user_id 로 못박는다 —
# ADMIN 이 늘어나도 "사용자에게 권한 부여"는 소유자 본인만 하게 하기 위해서다.
# 환경변수 SUPER_USER_IDS="1,7" 로 바꿀 수 있고 기본은 1.
SUPER_USER_IDS = {
    int(x) for x in os.environ.get('SUPER_USER_IDS', '1').split(',') if x.strip().isdigit()
}
# 슈퍼유저에게만 보이는 메뉴. ADMIN 전체 허용·role_menu 매핑이 있어도 슈퍼유저가 아니면 제외한다.
SUPER_ONLY_MENU_CODES = {'UserAuthSetting'}


def is_super_user(user_id):
    return user_id is not None and int(user_id) in SUPER_USER_IDS


class RoleMenuDao:
    def __init__(self):
        self.__name__ = 'RoleMenuDao'

    # 사용자 권한
    # ================================================================
    def select_user_auth_ids(self, session, user_id):
        """사용자의 유효 권한(auth_id) 목록. user_role 에 없는 auth_id 는 제외한다."""
        stmt = (
            select(UserAuth.auth_id)
            .join(UserRole, UserAuth.auth_id == UserRole.auth_id)
            .where(UserAuth.user_id == user_id, UserAuth.enabled_flag == 'Y')
        )
        return list(session.execute(stmt).scalars().all())

    # 사용자별 접근 가능 메뉴 / 기능
    # ================================================================
    def select_menus_for_user(self, session, user_id, auth_ids, search_params):
        """접근 가능한 메뉴 평면 목록.

        - ADMIN 은 enabled/display 조건만 맞으면 전체.
        - user_id=None(게스트): public_flag='Y' 인 메뉴만.
        - 그 외: common/public_flag='Y' 이거나 role_menu(enabled Y)에 매핑된 메뉴.
        부모 파생은 호출측(라우터)에서 한다.
        """
        stmt = select(MasterMenu).where(
            MasterMenu.enabled_flag.like(f"%{search_params.get('enabled_flag') or ''}%"),
            MasterMenu.display_flag.like(f"%{search_params.get('display_flag') or ''}%"),
        )
        rows = [m.to_dict() for m in session.execute(stmt).scalars().all()]
        if user_id is None:
            # 게스트(비로그인): 공개 메뉴만. public_flag 는 common 을 포함하는 개념이다.
            return [r for r in rows if r['public_flag'] == 'Y']
        if not is_super_user(user_id):
            rows = [r for r in rows if r['menu_code'] not in SUPER_ONLY_MENU_CODES]
        if ADMIN_AUTH_ID in auth_ids:
            return rows

        if auth_ids:
            granted = set(session.execute(
                select(RoleMenu.menu_code).where(
                    RoleMenu.auth_id.in_(auth_ids),
                    RoleMenu.enabled_flag == 'Y',
                )
            ).scalars().all())
        else:
            granted = set()
        return [r for r in rows
                if r['common_flag'] == 'Y' or r['public_flag'] == 'Y' or r['menu_code'] in granted]

    def select_features_for_user(self, session, auth_ids):
        """기능 플래그. ADMIN 도 우회 없이 role_feature 에 명시된 것만 인정한다."""
        if not auth_ids:
            return []
        stmt = select(RoleFeature.feature_code).where(
            RoleFeature.auth_id.in_(auth_ids),
            RoleFeature.enabled_flag == 'Y',
        ).distinct()
        return sorted(session.execute(stmt).scalars().all())

    # 관리 화면용
    # ================================================================
    def select_role_list(self, session):
        stmt = select(UserRole).order_by(UserRole.auth_id)
        return [r.to_dict() for r in session.execute(stmt).scalars().all()]

    def role_exists(self, session, auth_id):
        return session.execute(
            select(UserRole.auth_id).where(UserRole.auth_id == auth_id)
        ).first() is not None

    def select_role_menu_codes(self, session, auth_id):
        stmt = select(RoleMenu.menu_code).where(
            RoleMenu.auth_id == auth_id, RoleMenu.enabled_flag == 'Y'
        )
        return sorted(session.execute(stmt).scalars().all())

    def replace_role_menus(self, session, auth_id, menu_codes):
        """매핑 전체 교체. 호출측 트랜잭션(요청 종료 시 commit)에 포함된다."""
        valid = set(session.execute(select(MasterMenu.menu_code)).scalars().all())
        codes = sorted({c for c in menu_codes if c in valid})
        now = datetime.now()
        session.execute(delete(RoleMenu).where(RoleMenu.auth_id == auth_id))
        session.add_all([
            RoleMenu(auth_id=auth_id, menu_code=c, enabled_flag='Y',
                     created_date=now, updated_date=now)
            for c in codes
        ])
        return codes

    def select_role_feature_codes(self, session, auth_id):
        stmt = select(RoleFeature.feature_code).where(
            RoleFeature.auth_id == auth_id, RoleFeature.enabled_flag == 'Y'
        )
        return sorted(session.execute(stmt).scalars().all())

    def replace_role_features(self, session, auth_id, feature_codes):
        codes = sorted({str(c).strip() for c in feature_codes if str(c).strip()})
        now = datetime.now()
        session.execute(delete(RoleFeature).where(RoleFeature.auth_id == auth_id))
        session.add_all([
            RoleFeature(auth_id=auth_id, feature_code=c, enabled_flag='Y',
                        created_date=now, updated_date=now)
            for c in codes
        ])
        return codes

    # 사용자별 권한 부여 (슈퍼유저 화면)
    # ================================================================
    def select_users_with_roles(self, session, keyword=''):
        """사용자 목록 + 각자의 유효 권한(auth_id 배열)."""
        stmt = select(UserMaster).order_by(UserMaster.user_id)
        kw = (keyword or '').strip()
        if kw:
            like = f'%{kw}%'
            stmt = stmt.where(UserMaster.user_name.like(like) | UserMaster.email.like(like))
        users = session.execute(stmt).scalars().all()
        ids = [u.user_id for u in users]

        roles_of = {}
        if ids:
            rows = session.execute(
                select(UserAuth.user_id, UserAuth.auth_id).where(
                    UserAuth.user_id.in_(ids), UserAuth.enabled_flag == 'Y')
            ).all()
            for uid, aid in rows:
                roles_of.setdefault(uid, []).append(aid)

        return [
            {
                'user_id': u.user_id,
                'user_name': u.user_name,
                'email': u.email,
                'auth_ids': sorted(roles_of.get(u.user_id, [])),
            }
            for u in users
        ]

    def user_exists(self, session, user_id):
        return session.execute(
            select(UserMaster.user_id).where(UserMaster.user_id == user_id)
        ).first() is not None

    def set_user_role(self, session, user_id, auth_id, enabled):
        """권한 부여/회수. 행을 지우지 않고 enabled_flag 로 토글한다(user_auth 의 기존 관례)."""
        now = datetime.now()
        row = session.execute(
            select(UserAuth).where(UserAuth.user_id == user_id, UserAuth.auth_id == auth_id)
        ).scalars().first()
        flag = 'Y' if enabled else 'N'
        if row is None:
            if enabled:
                session.add(UserAuth(user_id=user_id, auth_id=auth_id, enabled_flag='Y',
                                     created_date=now, updated_date=now))
        else:
            row.enabled_flag = flag
            row.updated_date = now
