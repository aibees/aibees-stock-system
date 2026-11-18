from sqlalchemy import delete, func, select

from web_shared.models.stockAiGenLog import StockAiGenLog


class StockAiGenLogDao:
    def __init__(self):
        self.__name__ = 'StockAiGenLogDao'

    def count_since(self, session, since, user_id=None) -> int:
        """since 이후 생성 건수. user_id 가 있으면 그 사용자만."""
        stmt = select(func.count()).select_from(StockAiGenLog).where(StockAiGenLog.created_at >= since)
        if user_id is not None:
            stmt = stmt.where(StockAiGenLog.user_id == user_id)
        return int(session.execute(stmt).scalar() or 0)

    def insert(self, session, user_id, stock_code, section, created_at) -> int:
        row = StockAiGenLog(user_id=user_id, stock_code=stock_code, section=section, created_at=created_at)
        session.add(row)
        session.flush()
        return row.log_id

    def delete(self, session, log_id):
        session.execute(delete(StockAiGenLog).where(StockAiGenLog.log_id == log_id))
