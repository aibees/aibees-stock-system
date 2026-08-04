from sqlalchemy import insert, select, update, and_, or_

from app.domains.models.masterStock import MasterStock
from sqlalchemy.dialects.mysql import insert
import logging

logging.basicConfig(level=logging.ERROR)

class MasterStockDao:
    def __init__(self):
        self.__name__ = 'MasterStockDao'
        
    # select
    # ================================================================
    def select_master_stock(self, session, data):
        param_name = data['stock_name']
        param_flag = data['search_option'] or False
        options = and_(
            MasterStock.stock_name.like(f'%{param_name}%')
        )
        
        if param_flag is True:
            options = or_(
                MasterStock.stock_name.like(f'%{param_name}%'),
                MasterStock.stock_code.like(f'%{param_name}%')
            )
        
        selectStmt = select(MasterStock).where(options)
        
        results = session.execute(selectStmt).scalars().all()
        return [item.to_dict() for item in results]
    
    # select by id
    # ================================================================
    def select_master_stock_by_id(self, session, data):
        param_stock_code = data['stock_code']
        
        stmt = select(
            MasterStock
        ).where(
            MasterStock.stock_code == param_stock_code
        )
        
        result = session.execute(stmt).scalars().first()
        
        if result is None :
            return None
        else:
            return result.to_dict()
        
    
    # select all stocks (배치 ingest / run-all용)
    # ================================================================
    def select_all_stocks(self, session) -> list:
        stmt = select(MasterStock).order_by(MasterStock.stock_code)
        results = session.execute(stmt).scalars().all()
        return [item.to_dict() for item in results]

    # save
    # upsert
    # ================================================================
    def upsert_stock_data(self, session, data):
        stmt = insert(
            MasterStock
        ).values(
            corp_code=data['corp_code'],
            stock_code=data['stock_code'],
            stock_name=data['stock_name'],
            stock_type=data['type']
        )

        upsert_stmt = stmt.on_duplicate_key_update(
            stock_code=data['stock_code']
        )
        session.execute(upsert_stmt)
            