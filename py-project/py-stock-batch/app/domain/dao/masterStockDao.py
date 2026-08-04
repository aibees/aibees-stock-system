from app.domain.model.masterStock import MasterStock
from app.domain.model.nStockBatchLog import NStockBatchLog
from sqlalchemy import select, update, and_, or_, func
from sqlalchemy.dialects.mysql import insert
from datetime import datetime
import logging

logging.basicConfig(level=logging.ERROR)


class MasterStockDao:
    def __init__(self):
        self.__name__ = 'MasterStockDao'

    def select_stock_list(self, session, param) -> list:
        conditions = []

        if param['in_market_stop']:
            conditions.append(MasterStock.market_stop.in_(param['in_market_stop']))

        # 현물(그룹코드) OR 코스피200·인버스 ETF(EF) 를 합집합으로 조회.
        # ETF 는 group_code='EF' 이며, (코스피200 '%200' or 인버스) and 선물 제외.
        etf_target = and_(
            MasterStock.group_code == 'EF',
            or_(
                MasterStock.stock_name.like('%200'),
                MasterStock.stock_name.like('%인버스'),
            ),
            MasterStock.stock_name.notlike('%선물%'),
        )

        if param['in_group_code']:
            conditions.append(
                or_(
                    MasterStock.group_code.in_(param['in_group_code']),
                    etf_target,
                )
            )
        else:
            conditions.append(etf_target)

        stmt = select(
            MasterStock
        ).where(*conditions).order_by(MasterStock.stock_code.asc())

        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]


    def clean_stock_list_all(self, session):
        session.query(MasterStock).delete()


    def update_stock_list(self, session, data:list) -> int:
        # dict에 있는 내용 : 'corp_code', 'stock_code', 'stock_name', 'stock_type', 'stock_type_yf', 'group_code', 'market_stop'
        if not data:
            return 0

        session.bulk_insert_mappings(MasterStock, data)
        return len(data)

    def update_stock_nxt_flag(self, session, data:list) -> None:
        if not data:
            return None

        stmt = update(MasterStock).where(
            MasterStock.stock_code.in_(data)
        ).values(
            nxt_flag='Y'
        )

        session.execute(stmt)

    def update_stock_finance_info(self, session, param) -> None:
        stmt = update(MasterStock).where(
            MasterStock.stock_code == param['stock_code']
        ).values(
            per=param['per'],
            pbr=param['pbr'],
            roe=param['roe']
        )

        session.execute(stmt)
