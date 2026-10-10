from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.tradeBuyTargetPerfMonthly import TradeBuyTargetPerfMonthly


class TradeBuyTargetPerfMonthlyDao(BaseDao):
    """월별 추천 성과 저장소. 트랜잭션(commit)은 호출측이 관리한다."""
    model = TradeBuyTargetPerfMonthly

    def __init__(self):
        self.__name__ = "TradeBuyTargetPerfMonthlyDao"

    def select_by_ym(self, session, ym: str) -> dict | None:
        row = session.execute(
            select(TradeBuyTargetPerfMonthly).where(TradeBuyTargetPerfMonthly.ym == ym)
        ).scalars().first()
        return row.to_dict() if row else None

    def upsert(self, session, ym: str, payload_json: str, final: bool) -> None:
        values = {
            "ym": ym,
            "payload": payload_json,
            "final_flag": "Y" if final else "N",
            "calculated_at": datetime.now(),
        }
        stmt = insert(TradeBuyTargetPerfMonthly).values(**values)
        stmt = stmt.on_duplicate_key_update(
            payload=stmt.inserted.payload,
            final_flag=stmt.inserted.final_flag,
            calculated_at=stmt.inserted.calculated_at,
        )
        session.execute(stmt)
        session.flush()
