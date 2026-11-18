from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from app.domains.models.stockAiContent import StockAiContent

import logging

logging.basicConfig(level=logging.ERROR)


class StockAiContentDao:
    def __init__(self):
        self.__name__ = 'StockAiContentDao'

    # select
    # ================================================================
    def select_by_stock_section(self, session, stock_code, section):
        stmt = select(StockAiContent).where(
            and_(
                StockAiContent.stock_code == stock_code,
                StockAiContent.section == section,
            )
        )
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # upsert
    # ================================================================
    def upsert(self, session, data):
        insert_stmt = insert(StockAiContent).values(
            stock_code=data['stock_code'],
            section=data['section'],
            content=data['content'],
            model=data.get('model'),
            input_tokens=data.get('input_tokens'),
            output_tokens=data.get('output_tokens'),
        )
        upsert_stmt = insert_stmt.on_duplicate_key_update(
            content=insert_stmt.inserted.content,
            model=insert_stmt.inserted.model,
            input_tokens=insert_stmt.inserted.input_tokens,
            output_tokens=insert_stmt.inserted.output_tokens,
        )
        session.execute(upsert_stmt)
