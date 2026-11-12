"""
user_option_etf_switch DAO — ETF 교대(ETF_SWITCH) 개인화 옵션.

user_options(전역) 와 달리 모드별 옵션은 **행이 없을 수 있다**.
행 없음 == 전 항목 NULL == 전략 클래스 기본값 사용 이므로,
조회 실패를 예외로 올리지 않고 빈 dict 를 돌려준다.
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.userOptionEtfSwitch import UserOptionEtfSwitch

logging.basicConfig(level=logging.ERROR)

#: UserOptionMeta 에 얹을 때 붙이는 접두어
META_PREFIX = "etf_switch_"


class UserOptionEtfSwitchDao(BaseDao):
    model = UserOptionEtfSwitch

    def __init__(self):
        self.__name__ = "UserOptionEtfSwitchDao"

    def select_by_user(self, session, user_id: int) -> dict:
        """user_id 의 ETF_SWITCH 옵션. 행이 없으면 빈 dict."""
        stmt = select(UserOptionEtfSwitch).where(UserOptionEtfSwitch.user_id == user_id)
        row = session.execute(stmt).scalars().first()
        return row.to_dict() if row else {}

    def select_prefixed(self, session, user_id: int, prefix: str = META_PREFIX) -> dict:
        """UserOptionMeta 조립용. PARAM_KEYS 만 뽑아 prefix 를 붙인다.

        user_id 는 제외한다(메타에 이미 있고, 접두어가 붙으면 혼란스럽다).
        """
        row = self.select_by_user(session, user_id)
        if not row:
            return {}
        return {f"{prefix}{k}": row.get(k) for k in UserOptionEtfSwitch.PARAM_KEYS}

    def upsert(self, session, user_id: int, values: dict) -> None:
        """PARAM_KEYS 화이트리스트만 저장. 없는 키는 무시한다.

        created_date 는 행을 처음 만들 때만, updated_date 는 저장할 때마다 채운다.
        """
        params = {k: v for k, v in values.items() if k in UserOptionEtfSwitch.PARAM_KEYS}
        if not params:
            return
        now = datetime.now()
        stmt = mysql_insert(UserOptionEtfSwitch).values(
            user_id=user_id, created_date=now, updated_date=now, **params)
        stmt = stmt.on_duplicate_key_update(
            updated_date=stmt.inserted.updated_date,
            **{k: stmt.inserted[k] for k in params},
        )
        session.execute(stmt)
