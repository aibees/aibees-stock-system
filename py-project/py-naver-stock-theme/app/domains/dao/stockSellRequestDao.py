from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.stockSellRequest import StockSellRequest

import logging
logging.basicConfig(level=logging.ERROR)


class StockSellRequestDao(BaseDao):
    """
    stock_sell_request DAO.

    보안 핵심:
        모든 조회/수정/삭제 메서드는 반드시 user_id(JWT 추출값)로 필터링한다.
        클라이언트가 보낸 user_id 는 절대 신뢰하지 않으며,
        라우터에서 g.current_user_id 만을 인자로 전달한다.
    """

    model = StockSellRequest

    def __init__(self):
        self.__name__ = 'StockSellRequestDao'

    # 1. 본인 데이터 전체 조회 — WHERE user_id = :uid
    # ================================================================
    def select_all_by_user(self, session, user_id: int):
        stmt = (
            select(StockSellRequest)
            .where(StockSellRequest.user_id == user_id)
            .order_by(StockSellRequest.stock_code)
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # 2. 본인 단건 조회 (PK = user_id + stock_code)
    # ================================================================
    def select_by_pk(self, session, user_id: int, stock_code: str):
        stmt = select(StockSellRequest).where(
            StockSellRequest.user_id == user_id,
            StockSellRequest.stock_code == stock_code,
        )
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # 3. 본인 보유 건수 카운트 (5개 초과 차단용)
    # ================================================================
    def count_by_user(self, session, user_id: int) -> int:
        stmt = select(func.count()).select_from(StockSellRequest).where(
            StockSellRequest.user_id == user_id
        )
        return session.execute(stmt).scalar() or 0

    # 4. 신규 등록 — user_id 는 서버가 주입
    # ================================================================
    def insert(self, session, user_id: int, data: dict) -> None:
        stmt = insert(StockSellRequest).values(
            user_id=user_id,
            stock_code=data['stock_code'],
            stock_name=data.get('stock_name'),
            entry_date=data.get('entry_date'),
            entry_price=data.get('entry_price'),
            hold_qty=data.get('hold_qty'),
            memo=data.get('memo'),
            enabled_flag=data.get('enabled_flag') or 'Y',
        )
        session.execute(stmt)

    # 5. 수정 — WHERE user_id = :uid AND stock_code = :code
    #    (PK 외 모든 필드 갱신)
    # ================================================================
    def update_by_user_key(self, session, user_id: int, stock_code: str, data: dict) -> None:
        values = {
            'stock_name': data.get('stock_name'),
            'entry_date': data.get('entry_date'),
            'entry_price': data.get('entry_price'),
            'hold_qty': data.get('hold_qty'),
            'memo': data.get('memo'),
            'enabled_flag': data.get('enabled_flag') or 'Y',
        }
        stmt = (
            update(StockSellRequest)
            .where(
                StockSellRequest.user_id == user_id,
                StockSellRequest.stock_code == stock_code,
            )
            .values(**values)
        )
        session.execute(stmt)

    # 6. 사용/미사용 토글 — enabled_flag 만 변경
    # ================================================================
    def update_enabled_flag(self, session, user_id: int, stock_code: str, enabled_flag: str) -> None:
        stmt = (
            update(StockSellRequest)
            .where(
                StockSellRequest.user_id == user_id,
                StockSellRequest.stock_code == stock_code,
            )
            .values(enabled_flag=enabled_flag)
        )
        session.execute(stmt)

    # 7. 삭제 — WHERE user_id = :uid AND stock_code = :code
    # ================================================================
    def delete_by_user_key(self, session, user_id: int, stock_code: str) -> None:
        stmt = delete(StockSellRequest).where(
            StockSellRequest.user_id == user_id,
            StockSellRequest.stock_code == stock_code,
        )
        session.execute(stmt)
