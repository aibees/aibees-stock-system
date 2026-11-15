import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.models.userPersona import UserPersona

logging.basicConfig(level=logging.ERROR)


class UserPersonaDao:
    """성향 테스트 결과(user_persona) — 유저당 1행. 양봉상회 API 에서만 사용(테이블은 `yangbong` 스키마에만 있다)."""

    def __init__(self):
        self.__name__ = "UserPersonaDao"

    def select_by_user_id(self, session, user_id: int) -> dict | None:
        row = session.execute(
            select(UserPersona).where(UserPersona.user_id == user_id)
        ).scalars().first()
        return row.to_dict() if row else None

    def upsert(self, session, user_id: int, fields: dict) -> None:
        """보낸 항목(persona_type)만 바꾸고 updated_at 을 지금으로 갱신한다."""
        values = {k: v for k, v in fields.items() if k in ("persona_type",)}
        values["updated_at"] = datetime.now().replace(microsecond=0)
        stmt = insert(UserPersona).values(user_id=user_id, **values)
        session.execute(stmt.on_duplicate_key_update(**values))
