import logging

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.masterStock import MasterStock

logging.basicConfig(level=logging.ERROR)


class MasterStockDao(BaseDao):
    model = MasterStock

    def __init__(self):
        self.__name__ = "MasterStockDao"

    # ------------------------------------------------------------------
    # select
    # ------------------------------------------------------------------
    def select_master_stock(self, session, data):
        """종목명(옵션: 종목코드 포함) LIKE 검색."""
        param_name = data["stock_name"]
        param_flag = data["search_option"] or False

        options = and_(MasterStock.stock_name.like(f"%{param_name}%"))
        if param_flag is True:
            options = or_(
                MasterStock.stock_name.like(f"%{param_name}%"),
                MasterStock.stock_code.like(f"%{param_name}%"),
            )

        stmt = select(MasterStock).where(options)
        results = session.execute(stmt).scalars().all()
        return [item.to_dict() for item in results]

    def select_master_stock_by_id(self, session, data):
        """종목코드 단건 조회."""
        stmt = select(MasterStock).where(MasterStock.stock_code == data["stock_code"])
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    def select_all_stocks(self, session) -> list:
        """전체 종목 조회 (stock_code 오름차순)."""
        stmt = select(MasterStock).order_by(MasterStock.stock_code)
        results = session.execute(stmt).scalars().all()
        return [item.to_dict() for item in results]

    def select_stock_list(self, session, param) -> list:
        """
        배치용 종목 조회.

        현물(group_code) OR 코스피200·인버스 ETF(EF) 를 합집합으로 조회한다.
        ETF 는 group_code='EF' 이며, (코스피200 '%200' or 인버스) and 선물 제외.
        """
        conditions = []

        if param["in_market_stop"]:
            conditions.append(MasterStock.market_stop.in_(param["in_market_stop"]))

        etf_target = and_(
            MasterStock.group_code == "EF",
            or_(
                MasterStock.stock_name.like("%200"),
                MasterStock.stock_name.like("%인버스"),
            ),
            MasterStock.stock_name.notlike("%선물%"),
        )

        if param["in_group_code"]:
            conditions.append(
                or_(MasterStock.group_code.in_(param["in_group_code"]), etf_target)
            )
        else:
            conditions.append(etf_target)

        stmt = (
            select(MasterStock)
            .where(*conditions)
            .order_by(MasterStock.stock_code.asc())
        )
        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    # ------------------------------------------------------------------
    # insert / update
    # ------------------------------------------------------------------
    def clean_stock_list_all(self, session):
        """전체 삭제 (전량 재적재용)."""
        session.query(MasterStock).delete()

    def update_stock_list(self, session, data: list) -> int:
        """
        bulk insert.
        dict 키: corp_code, stock_code, stock_name, stock_type,
                 stock_type_yf, group_code, market_stop
        """
        if not data:
            return 0

        session.bulk_insert_mappings(MasterStock, data)
        return len(data)

    def update_stock_nxt_flag(self, session, data: list) -> None:
        """전달된 종목코드들의 nxt_flag 를 'Y' 로 설정."""
        if not data:
            return None

        stmt = (
            update(MasterStock)
            .where(MasterStock.stock_code.in_(data))
            .values(nxt_flag="Y")
        )
        session.execute(stmt)

    def upsert_stock_data(self, session, data):
        """단건 upsert."""
        stmt = insert(MasterStock).values(
            corp_code=data["corp_code"],
            stock_code=data["stock_code"],
            stock_name=data["stock_name"],
            stock_type=data["type"],
        )
        upsert_stmt = stmt.on_duplicate_key_update(stock_code=data["stock_code"])
        session.execute(upsert_stmt)

    # ------------------------------------------------------------------
    # 제외된 메서드
    # ------------------------------------------------------------------
    # update_stock_finance_info(session, param)
    #   py-stock-batch 에 있었으나 master_stock 테이블에 존재하지 않는
    #   per / pbr / roe 컬럼을 참조하여 호출 시 반드시 실패하는 코드였고,
    #   호출처도 없어 shared 로 옮기지 않았다.
    #   재무지표는 trade_buy_target_stock(per/pbr/roe/eps/peg) 에 존재한다.
