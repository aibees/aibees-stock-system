from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from app.domain.model.stockSellRequest import StockSellRequest


class StockSellRequestDao:
    def __init__(self):
        self.__name__ = 'StockSellRequestDao'

    def select_enabled_list(self, session, user_id: int) -> list:
        """user_id 기준 enabled_flag='Y'인 매도 체크 대상 종목 조회"""
        stmt = select(StockSellRequest).where(
            StockSellRequest.user_id == user_id,
            StockSellRequest.enabled_flag == 'Y'
        ).order_by(StockSellRequest.stock_code.asc())

        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    def select_all(self, session) -> list:
        """전체 목록 조회 (Vue 관리 화면용)"""
        stmt = select(StockSellRequest).order_by(StockSellRequest.created_at.desc())
        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    def upsert(self, session, data: dict) -> None:
        """
        등록 또는 수정 (user_id + stock_code 복합 PK 기준).
        data 필수 키: user_id, stock_code
        선택 키: stock_name, entry_date, entry_price, hold_qty, memo, enabled_flag
        """
        now = datetime.now()
        row = {
            'user_id':      data['user_id'],
            'stock_code':   data['stock_code'],
            'stock_name':   data.get('stock_name', ''),
            'entry_date':   data.get('entry_date', ''),
            'entry_price':  data.get('entry_price', 0),
            'hold_qty':     data.get('hold_qty', 0),
            'memo':         data.get('memo', ''),
            'enabled_flag': data.get('enabled_flag', 'Y'),
            'created_at':   now,
            'updated_at':   now,
        }
        stmt = insert(StockSellRequest).values(row)
        stmt = stmt.on_duplicate_key_update(
            stock_name=stmt.inserted['stock_name'],
            entry_date=stmt.inserted['entry_date'],
            entry_price=stmt.inserted['entry_price'],
            hold_qty=stmt.inserted['hold_qty'],
            memo=stmt.inserted['memo'],
            enabled_flag=stmt.inserted['enabled_flag'],
            updated_at=stmt.inserted['updated_at'],
        )
        session.execute(stmt)

    def update_enabled_flag(self, session, user_id: int, stock_code: str, enabled_flag: str) -> None:
        """활성화/비활성화 토글 (복합 PK: user_id + stock_code 기준)"""
        stmt = update(StockSellRequest).where(
            StockSellRequest.user_id == user_id,
            StockSellRequest.stock_code == stock_code
        ).values(enabled_flag=enabled_flag, updated_at=datetime.now())
        session.execute(stmt)
