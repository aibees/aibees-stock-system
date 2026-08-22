"""
device_push_token DAO.

upsert_token 은 device_token 의 UNIQUE KEY(uk_device_push_token) 기준
INSERT ... ON DUPLICATE KEY UPDATE 를 쓴다(batchLogDao.py 의 insert 스타일과
동일하게 sqlalchemy.dialects.mysql.insert 사용) — 같은 기기가 앱을 재설치하지
않는 한 토큰은 보통 동일하므로, 로그인/로그아웃을 반복해도 행이 계속
늘어나지 않고 user_id/roles 만 최신으로 갱신된다.
"""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.devicePushToken import DevicePushToken

import logging
logging.basicConfig(level=logging.ERROR)


class DevicePushTokenDao(BaseDao):
    model = DevicePushToken

    def __init__(self):
        self.__name__ = "DevicePushTokenDao"

    # insert / upsert
    # ================================================================
    def upsert_token(self, session, data):
        """device_token 기준 upsert. 존재하면 user_id/roles/platform/enabled_flag
        를 최신값으로 덮어쓴다(재등록·재로그인 시 소유자 정보 갱신 목적)."""
        now = datetime.now()
        stmt = insert(DevicePushToken).values(
            device_token=data["device_token"],
            platform=data["platform"],
            user_id=data.get("user_id"),
            roles=data.get("roles"),
            enabled_flag="Y",
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_duplicate_key_update(
            platform=stmt.inserted.platform,
            user_id=stmt.inserted.user_id,
            roles=stmt.inserted.roles,
            enabled_flag="Y",
            updated_at=now,
        )
        session.execute(stmt)

    # update
    # ================================================================
    def deactivate_token(self, session, device_token):
        """로그아웃/알림 거부 등으로 더 이상 보낼 필요가 없을 때 비활성화.
        행을 지우지 않고 enabled_flag='N' 으로만 바꾼다 — 재등록 시 upsert 로
        다시 살아난다."""
        stmt = (
            update(DevicePushToken)
            .where(DevicePushToken.device_token == device_token)
            .values(enabled_flag="N", updated_at=datetime.now())
        )
        session.execute(stmt)

    # select — 발송 대상 조회 (스코프별)
    # ================================================================
    def select_broadcast_tokens(self, session) -> list:
        """전체 broadcast 대상 — 활성 토큰 전부."""
        stmt = select(DevicePushToken.device_token).where(
            DevicePushToken.enabled_flag == "Y"
        )
        return [row[0] for row in session.execute(stmt).all()]

    def select_tokens_by_user(self, session, user_id) -> list:
        """특정 유저(worker 소유자 등) 소유 디바이스만."""
        stmt = select(DevicePushToken.device_token).where(
            DevicePushToken.enabled_flag == "Y",
            DevicePushToken.user_id == user_id,
        )
        return [row[0] for row in session.execute(stmt).all()]

    def select_tokens_by_role(self, session, role) -> list:
        """특정 role(auth_id) 을 가진 유저의 디바이스만.
        roles 컬럼은 콤마 구분 문자열이라 FIND_IN_SET 으로 정확히 매칭한다
        (LIKE '%role%' 는 'ADMIN2' 가 'ADMIN' 에 잘못 매칭되는 문제가 있음)."""
        stmt = select(DevicePushToken.device_token).where(
            DevicePushToken.enabled_flag == "Y",
            DevicePushToken.roles.isnot(None),
            func_find_in_set(role, DevicePushToken.roles),
        )
        return [row[0] for row in session.execute(stmt).all()]


def func_find_in_set(needle, haystack_column):
    """MySQL FIND_IN_SET(needle, column) — sqlalchemy.func 래핑을 이 파일
    안에서만 쓰므로 지역 헬퍼로 둔다."""
    from sqlalchemy import func
    return func.find_in_set(needle, haystack_column) > 0
