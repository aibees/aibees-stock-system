from app.domains.models.masterInfos import MasterInfos
from sqlalchemy import delete, select, update, and_, func
from sqlalchemy.dialects.mysql import insert
import logging

logging.basicConfig(level=logging.ERROR)

class MasterInfosDao:
    def __init__(self):
        self.__name__ = 'MasterInfosDao'
        
    # select
    # ================================================================
    def select_master_key_by_type(self, session, type_str):
        stmt = select(
            MasterInfos
        ).where(
            MasterInfos.key_type == type_str
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]
    
    # select
    # ================================================================
    def select_master_key_by_category(self, session, category):
        stmt = select(
            MasterInfos
        ).where(
            MasterInfos.category == category
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]
            
    # insert
    # ================================================================
    def insert_master_key(self, session, data):
        insert_stmt = insert(MasterInfos).values(
            key_type=data['key_type'],
            key_value=data['key_value'],
            expired_date=data['expired_date']
        )
        
        # on duplicate key update
        upsert_stmt = insert_stmt.on_duplicate_key_update(
            key_value=data['key_value'],
            expired_date=data['expired_date']
        )
        
        session.execute(upsert_stmt)
        
    # update
    # ================================================================
    def update_master_key(self, session, data):
        stmt = update(
            MasterInfos
        ).where(
            MasterInfos.key_type == data['key_type']
        ).values(
            key_value=data['key_value'],
            expired_date=data['expired_date']
        )
        session.execute(stmt)

    # 관리화면 (MasterInfoSetting.vue, 슈퍼유저 전용)
    # ================================================================
    def select_master_key_all(self, session):
        stmt = select(MasterInfos).order_by(MasterInfos.category, MasterInfos.key_type)
        return [obj.to_dict() for obj in session.execute(stmt).scalars().all()]

    def upsert_master_key_full(self, session, data):
        """key_type 기준 등록/수정. insert_master_key 와 달리 category 까지 바꾼다."""
        values = {k: data[k] for k in ('key_type', 'key_value', 'expired_date', 'category')}
        stmt = insert(MasterInfos).values(**values).on_duplicate_key_update(
            key_value=values['key_value'],
            expired_date=values['expired_date'],
            category=values['category'],
        )
        session.execute(stmt)

    def delete_master_key(self, session, key_type):
        return session.execute(delete(MasterInfos).where(MasterInfos.key_type == key_type)).rowcount
