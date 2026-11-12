"""
user_option_reco DAO — 추천매수(RECO) 개인화 옵션.

UserOptionEtfSwitchDao 와 같은 계약을 따른다. 모드별 옵션은 **행이 없을 수 있고**,
행 없음 == 전 항목 NULL == RecoStrategy 클래스 기본값 사용 이므로,
조회 결과가 없으면 빈 dict 를 돌려준다.

DTO(UserOptionMeta)는 여러 모드의 값을 한 객체에 flat 하게 담으므로
select_prefixed 로 읽을 때만 `reco_` 접두어를 붙인다. 테이블·API 키에는 접두어가 없다.
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.userOptionReco import UserOptionReco

logging.basicConfig(level=logging.ERROR)

#: UserOptionMeta 에 얹을 때 붙이는 접두어
META_PREFIX = "reco_"


class UserOptionRecoDao(BaseDao):
    model = UserOptionReco

    def __init__(self):
        self.__name__ = "UserOptionRecoDao"

    def select_by_user(self, session, user_id: int) -> dict:
        """user_id 의 추천매수 옵션. 행이 없으면 빈 dict."""
        stmt = select(UserOptionReco).where(UserOptionReco.user_id == user_id)
        row = session.execute(stmt).scalars().first()
        return row.to_dict() if row else {}

    def select_prefixed(self, session, user_id: int, prefix: str = META_PREFIX) -> dict:
        """UserOptionMeta 조립용. PARAM_KEYS 만 뽑아 prefix 를 붙인다.

        user_id 는 제외한다(메타에 이미 있고, 접두어가 붙으면 혼란스럽다).
        """
        row = self.select_by_user(session, user_id)
        if not row:
            return {}
        return {f"{prefix}{k}": row.get(k) for k in UserOptionReco.PARAM_KEYS}

    def upsert(self, session, user_id: int, values: dict) -> None:
        """PARAM_KEYS 화이트리스트만 저장. 없는 키는 무시한다.

        created_date 는 행을 처음 만들 때만, updated_date 는 저장할 때마다 채운다.
        """
        params = {k: v for k, v in values.items() if k in UserOptionReco.PARAM_KEYS}
        if not params:
            return
        now = datetime.now()
        stmt = mysql_insert(UserOptionReco).values(
            user_id=user_id, created_date=now, updated_date=now, **params)
        stmt = stmt.on_duplicate_key_update(
            updated_date=stmt.inserted.updated_date,
            **{k: stmt.inserted[k] for k in params},
        )
        session.execute(stmt)
