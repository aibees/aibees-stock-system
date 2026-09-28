import logging

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.models.tradeBuyTargetPriority import TradeBuyTargetPriority

logging.basicConfig(level=logging.ERROR)


class TradeBuyTargetPriorityDao:
    """최우선타겟(trade_buy_target_priority) — 유저당 1행. API 서버(조회/설정/해제)에서 사용.
    worker 쪽(trade_worker.repository) 은 raw SQL 로 별도 접근한다(기존 repository.py 관례)."""

    def __init__(self):
        self.__name__ = "TradeBuyTargetPriorityDao"

    def select_by_user_id(self, session, user_id: int) -> dict | None:
        row = session.execute(
            select(TradeBuyTargetPriority).where(TradeBuyTargetPriority.user_id == user_id)
        ).scalars().first()
        return row.to_dict() if row else None

    def upsert(self, session, user_id: int, stock_code: str, stock_name: str, set_ymd: str) -> None:
        """지정 — 유저당 1행만 유지(PK=user_id)이므로 이미 있으면 덮어쓴다."""
        values = {"stock_code": stock_code, "stock_name": stock_name, "set_ymd": set_ymd}
        stmt = insert(TradeBuyTargetPriority).values(user_id=user_id, **values)
        session.execute(stmt.on_duplicate_key_update(**values))

    def clear(self, session, user_id: int) -> None:
        """해제 — 행 자체는 지우지 않고 stock_code/stock_name 을 NULL 로 되돌린다
        (worker 가 1회성 소비 후 리셋하는 것과 동일한 규약)."""
        row = session.execute(
            select(TradeBuyTargetPriority).where(TradeBuyTargetPriority.user_id == user_id)
        ).scalars().first()
        if not row:
            return
        row.stock_code = None
        row.stock_name = None
