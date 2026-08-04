from app.domains.models.userInterestGroups import UserInterestGroups

from sqlalchemy import select, update, and_, func, delete
from sqlalchemy.dialects.mysql import insert
import logging

logging.basicConfig(level=logging.ERROR)

class FavoriteGroupDao:
    def __init__(self):
        self.name = 'FavoriteGroupDao'
        
    #select
    # ================================================================
    def select_favorite_user_group(self, session, param):
        user_id_param = param['user_id']
        stmt = select(
            UserInterestGroups
        ).where(
            UserInterestGroups.user_id == user_id_param
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]
    
    #insert
    # ================================================================
    def insert_favorite_user_group(self, session, data):
        insert_stmt = insert(
            UserInterestGroups
        ).values(
            group_id=data['group_id'],
            user_id=data['user_id'],
            group_name=data['group_name']
        )
        
        session.execute(insert_stmt)
    
    
    #update
    # ================================================================
    def update_favorite_user_group(self, session, data):
        stmt = update(
            UserInterestGroups
        ).where(
            UserInterestGroups.group_id == data['group_id'],
            UserInterestGroups.user_id  == data['user_id']
        ).values(
            group_name = data['group_name']
        )
    
        session.execute(stmt)
    
    #delete
    # ================================================================
    def delete_favorite_user_group(self, session, data):
        stmt = delete(
            UserInterestGroups
        ).where(
            UserInterestGroups.group_id == data['group_id'],
            UserInterestGroups.user_id  == data['user_id']
        )
    
        session.execute(stmt)