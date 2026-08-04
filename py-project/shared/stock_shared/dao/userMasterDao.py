import logging
from datetime import datetime

from sqlalchemy import or_, select, update

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.userAuth import UserAuth
from stock_shared.models.userDetail import UserDetail
from stock_shared.models.userInterestGroups import UserInterestGroups
from stock_shared.models.userInterestStocks import UserInterestStocks
from stock_shared.models.userLoginType import UserLoginType
from stock_shared.models.userMaster import UserMaster
from stock_shared.models.userOptions import UserOptions
from stock_shared.models.userRole import UserRole

logging.basicConfig(level=logging.ERROR)


class UserMasterDao(BaseDao):
    model = UserMaster

    def __init__(self):
        self.__name__ = "UserMasterDao"

    # ------------------------------------------------------------------
    # 인증 / 계정
    # ------------------------------------------------------------------
    def select_user_authinfo(self, session, param):
        """이메일 + 로그인타입 기준 인증 정보 조회 (UserMaster + LoginType + Detail)."""
        stmt = (
            select(UserMaster, UserLoginType, UserDetail)
            .join(UserLoginType, UserMaster.user_id == UserLoginType.user_id)
            .join(UserDetail, UserMaster.user_id == UserDetail.user_id)
            .where(
                UserLoginType.enabled_flag == "Y",
                UserLoginType.login_type == param["type"],
                UserMaster.email == param["email"],
            )
        )
        results = session.execute(stmt).all()
        if not results:
            return []

        return [
            {**um.to_dict(), **ult.to_dict(), **ud.to_dict()}
            for um, ult, ud in results
        ]

    def select_user_id_by_email(self, session, email: str):
        """이메일로 user_id 단건 조회."""
        stmt = select(UserMaster.user_id).where(UserMaster.email == email)
        return session.execute(stmt).scalar_one_or_none()

    def select_user_roleinfo(self, session, param):
        """사용자 권한 목록 조회."""
        stmt = (
            select(UserAuth, UserRole)
            .join(UserRole, UserAuth.auth_id == UserRole.auth_id)
            .where(
                UserAuth.user_id == param["user_id"],
                UserAuth.enabled_flag == "Y",
            )
        )
        results = session.execute(stmt).all()
        return [
            {"auth_id": user_role.auth_id, "auth_nm": user_role.auth_nm}
            for _user_auth, user_role in results
        ]

    def update_user_password(
        self, session, user_id: int, new_salt: str, new_pswd: str
    ):
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
                reset_flag="N",
                err_cnt=0,
                updated_date=datetime.now(),
            )
        )
        session.execute(stmt)

    # ------------------------------------------------------------------
    # 옵션 / 알림 대상
    # ------------------------------------------------------------------
    def select_user_stock_options(self, session, data):
        """user_id 기준 UserMaster + UserOptions 병합 단건 반환."""
        stmt = (
            select(UserMaster, UserOptions)
            .join(UserOptions, UserMaster.user_id == UserOptions.user_id)
            .where(UserMaster.user_id == data["user_id"])
        )
        result = session.execute(stmt).mappings().all()
        if not result:
            return None

        row = result[0]
        return {**row["UserMaster"].to_dict(), **row["UserOptions"].to_dict()}

    def select_target_emails(self, session):
        """stock_buy_target_mail_flag='Y' 인 사용자 이메일 리스트."""
        stmt = (
            select(UserMaster.email)
            .join(UserOptions, UserMaster.user_id == UserOptions.user_id)
            .where(UserOptions.stock_buy_target_mail_flag == "Y")
        )
        return session.execute(stmt).scalars().all()

    def select_sell_target_users(self, session) -> list:
        """
        매도 알림 대상 유저 전체 조회.
        stock_sell_mail_flag='Y' 또는 stock_sell_tele_flag='Y' 인 유저를
        UserMaster + UserOptions + UserDetail 조인하여 반환.
        """
        stmt = (
            select(UserMaster, UserOptions, UserDetail)
            .join(UserOptions, UserMaster.user_id == UserOptions.user_id)
            .join(UserDetail, UserMaster.user_id == UserDetail.user_id)
            .where(
                or_(
                    UserOptions.stock_sell_mail_flag == "Y",
                    UserOptions.stock_sell_tele_flag == "Y",
                )
            )
        )
        result = session.execute(stmt).mappings().all()
        return [
            {
                **row["UserMaster"].to_dict(),
                **row["UserOptions"].to_dict(),
                "tele_bot_id": row["UserDetail"].tele_bot_id,
                "tele_chat_id": row["UserDetail"].tele_chat_id,
            }
            for row in result
        ]

    def select_user_upbit_options(self, session, data):
        """upbit_push_flag 기준 유저 + 업비트 키 조회."""
        stmt = (
            select(
                UserMaster,
                UserOptions,
                UserDetail.upbit_access_key,
                UserDetail.upbit_secret_key,
            )
            .join(UserMaster, UserMaster.user_id == UserOptions.user_id)
            .join(UserDetail, UserOptions.user_id == UserDetail.user_id)
            .where(UserOptions.upbit_push_flag == data["upbit_options"])
        )
        result = session.execute(stmt).mappings().all()
        return [
            {
                **row["UserMaster"].to_dict(),
                **row["UserOptions"].to_dict(),
                # 주의: 키는 암호화 저장 정책에 따라 호출측에서 복호화한다.
                "upbit_access_key": row["upbit_access_key"],
                "upbit_secret_key": row["upbit_secret_key"],
            }
            for row in result
        ]

    # ------------------------------------------------------------------
    # 관심종목
    # ------------------------------------------------------------------
    def select_user_target_code(self, session, data):
        """사용자/구분 기준 활성 관심종목 목록."""
        stmt = (
            select(UserInterestGroups, UserInterestStocks)
            .join(
                UserInterestStocks,
                UserInterestGroups.group_id == UserInterestStocks.group_id,
            )
            .where(
                UserInterestGroups.user_id == data["user_id"],
                UserInterestGroups.division == data["division"],
                UserInterestStocks.enabled_flag == "Y",
            )
        )
        result = session.execute(stmt).mappings().all()
        return [
            {
                **row["UserInterestGroups"].to_dict(),
                **row["UserInterestStocks"].to_dict(),
            }
            for row in result
        ]

    def update_interest_stock(self, session, data):
        """
        관심종목 상태 갱신.

        주의: 원본(py-stock-batch)은 내부에서 session.commit() 을 호출했으나,
        DAO 가 트랜잭션 경계를 결정하지 않도록 commit 을 제거했다.
        호출측에서 트랜잭션을 커밋할 것.
        """
        stmt = (
            update(UserInterestStocks)
            .where(
                UserInterestStocks.group_id == data["group_id"],
                UserInterestStocks.stock_code == data["stock_code"],
            )
            .values(status=data["status"])
        )
        session.execute(stmt)

    # ------------------------------------------------------------------
    # 제외된 메서드
    # ------------------------------------------------------------------
    # select_user_by_phone(session, param)
    #   py-naver-stock-theme 에 있었으나 user_master 에 존재하지 않는
    #   `type` 컬럼(UserMaster.type)을 참조해 호출 시 AttributeError 가 난다.
    #   로그인 타입은 user_login_type.login_type 이므로
    #   select_user_authinfo() 를 사용하거나, 전화번호 기반이 필요하면
    #   UserLoginType 을 조인하는 형태로 새로 구현할 것.
