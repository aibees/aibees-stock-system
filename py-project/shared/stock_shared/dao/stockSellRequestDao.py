import logging
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.stockSellRequest import StockSellRequest

logging.basicConfig(level=logging.ERROR)


class StockSellRequestDao(BaseDao):
    """
    stock_sell_request DAO.

    보안 핵심:
        user 스코프 메서드(select_all_by_user / select_by_pk / count_by_user /
        insert / update_by_user_key / update_enabled_flag / delete_by_user_key)는
        반드시 user_id(JWT 추출값)로 필터링한다.
        클라이언트가 보낸 user_id 는 절대 신뢰하지 않으며,
        라우터에서 g.current_user_id 만을 인자로 전달한다.

        select_all() / upsert() 는 배치·관리 화면용으로 user 스코프가 없다.
        웹 요청 경로에서 직접 호출하지 말 것.
    """

    model = StockSellRequest

    def __init__(self):
        self.__name__ = "StockSellRequestDao"

    # ------------------------------------------------------------------
    # 사용자 스코프 조회
    # ------------------------------------------------------------------
    def select_all_by_user(self, session, user_id: int):
        """본인 데이터 전체 조회 — WHERE user_id = :uid"""
        stmt = (
            select(StockSellRequest)
            .where(StockSellRequest.user_id == user_id)
            .order_by(StockSellRequest.stock_code)
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    def select_by_pk(self, session, user_id: int, stock_code: str):
        """본인 단건 조회 (PK = user_id + stock_code)"""
        stmt = select(StockSellRequest).where(
            StockSellRequest.user_id == user_id,
            StockSellRequest.stock_code == stock_code,
        )
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    def count_by_user(self, session, user_id: int) -> int:
        """본인 보유 건수 카운트 (등록 개수 제한용)"""
        stmt = (
            select(func.count())
            .select_from(StockSellRequest)
            .where(StockSellRequest.user_id == user_id)
        )
        return session.execute(stmt).scalar() or 0

    def select_enabled_list(self, session, user_id: int) -> list:
        """user_id 기준 enabled_flag='Y' 인 매도 체크 대상 종목 조회 (배치용)"""
        stmt = (
            select(StockSellRequest)
            .where(
                StockSellRequest.user_id == user_id,
                StockSellRequest.enabled_flag == "Y",
            )
            .order_by(StockSellRequest.stock_code.asc())
        )
        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    # ------------------------------------------------------------------
    # 전체 스코프 조회 (배치·관리 화면 전용)
    # ------------------------------------------------------------------
    def select_all(self, session) -> list:
        """전체 목록 조회 (created_at 내림차순)."""
        stmt = select(StockSellRequest).order_by(StockSellRequest.created_at.desc())
        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    # ------------------------------------------------------------------
    # insert / update / delete
    # ------------------------------------------------------------------
    def insert(self, session, user_id: int, data: dict) -> None:
        """신규 등록 — user_id 는 서버가 주입."""
        stmt = insert(StockSellRequest).values(
            user_id=user_id,
            stock_code=data["stock_code"],
            stock_name=data.get("stock_name"),
            entry_date=data.get("entry_date"),
            entry_price=data.get("entry_price"),
            hold_qty=data.get("hold_qty"),
            memo=data.get("memo"),
            enabled_flag=data.get("enabled_flag") or "Y",
        )
        session.execute(stmt)

    def upsert(self, session, data: dict) -> None:
        """
        등록 또는 수정 (user_id + stock_code 복합 PK 기준).
        data 필수 키: user_id, stock_code
        선택 키: stock_name, entry_date, entry_price, hold_qty, memo, enabled_flag
        """
        now = datetime.now()
        row = {
            "user_id": data["user_id"],
            "stock_code": data["stock_code"],
            "stock_name": data.get("stock_name", ""),
            "entry_date": data.get("entry_date", ""),
            "entry_price": data.get("entry_price", 0),
            "hold_qty": data.get("hold_qty", 0),
            "memo": data.get("memo", ""),
            "enabled_flag": data.get("enabled_flag", "Y"),
            "created_at": now,
            "updated_at": now,
        }
        stmt = insert(StockSellRequest).values(row)
        stmt = stmt.on_duplicate_key_update(
            stock_name=stmt.inserted["stock_name"],
            entry_date=stmt.inserted["entry_date"],
            entry_price=stmt.inserted["entry_price"],
            hold_qty=stmt.inserted["hold_qty"],
            memo=stmt.inserted["memo"],
            enabled_flag=stmt.inserted["enabled_flag"],
            updated_at=stmt.inserted["updated_at"],
        )
        session.execute(stmt)

    def update_by_user_key(
        self, session, user_id: int, stock_code: str, data: dict
    ) -> None:
        """수정 — WHERE user_id = :uid AND stock_code = :code (PK 외 모든 필드 갱신)"""
        values = {
            "stock_name": data.get("stock_name"),
            "entry_date": data.get("entry_date"),
            "entry_price": data.get("entry_price"),
            "hold_qty": data.get("hold_qty"),
            "memo": data.get("memo"),
            "enabled_flag": data.get("enabled_flag") or "Y",
            "updated_at": datetime.now(),
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

    def update_enabled_flag(
        self, session, user_id: int, stock_code: str, enabled_flag: str
    ) -> None:
        """사용/미사용 토글 (복합 PK: user_id + stock_code 기준)"""
        stmt = (
            update(StockSellRequest)
            .where(
                StockSellRequest.user_id == user_id,
                StockSellRequest.stock_code == stock_code,
            )
            .values(enabled_flag=enabled_flag, updated_at=datetime.now())
        )
        session.execute(stmt)

    def delete_by_user_key(self, session, user_id: int, stock_code: str) -> None:
        """삭제 — WHERE user_id = :uid AND stock_code = :code"""
        stmt = delete(StockSellRequest).where(
            StockSellRequest.user_id == user_id,
            StockSellRequest.stock_code == stock_code,
        )
        session.execute(stmt)
