from app.domains.models.masterMenu import MasterMenu
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
import logging

logging.basicConfig(level=logging.ERROR)

class MasterInfosDao:
    def __init__(self):
        self.__name__ = 'MasterMenuDao'
        
    # select all
    # ================================================================
    def select_master_menu_all(self, session, params):
        
        search_enabled = params['enabled_flag']
        search_display = params['display_flag']
        stmt = select(
            MasterMenu
        ).where(
            MasterMenu.enabled_flag.like(f'%{search_enabled}%'),
            MasterMenu.display_flag.like(f'%{search_display}%')
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]
    
    # select root for setting
    # ================================================================
    def select_master_menu_root(self, session, param):
        param_code = param['menu_code'] if 'menu_code' in param else ''
        param_title = param['menu_title'] if 'menu_title' in param else ''
        
        stmt = select(
            MasterMenu
        ).where(
            MasterMenu.menu_parents == 'root',
            func.upper(MasterMenu.menu_code).like(f'%{param_code}%'),
            MasterMenu.menu_title.like(f'%{param_title}%')
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    def fetch_menu_enabled(self, session, param):
        menu_code = param['menu_code'] if 'menu_code' in param else ''

        menu = session.execute(
            select(MasterMenu).where(MasterMenu.menu_code == menu_code)
        ).scalars().first()

        if menu is None:
            return None

        new_flag = 'N' if menu.enabled_flag == 'Y' else 'Y'

        session.execute(
            update(MasterMenu)
            .where(MasterMenu.menu_code == menu_code)
            .values(enabled_flag=new_flag)
        )
        return new_flag

    # select sub for setting
    # ================================================================
    def select_master_menu_sub(self, session, param):
        param_parents = param['menu_parents'] if 'menu_parents' in param else ''
    
        stmt = select(
            MasterMenu
        ).where(
            MasterMenu.menu_parents == param_parents
        )
        
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]
    
    # select menu detail by id
    def select_master_menu_by_id(self, session, param):
        
        stmt = select(
            MasterMenu
        ).where(MasterMenu.menu_code == param['menu_code']);
        
        return session.execute(stmt).scalars().first().to_dict()
    
    # insert
    # ================================================================
    def insert_master_menu(self, session, data):
        insert_stmt = insert(MasterMenu).values(
            menu_code=data['menu_code'],
            menu_parents=data['menu_parents'],
            menu_name=data['menu_name'],
            menu_path=data['menu_path'],
            menu_title=data.get('menu_title', ''),
            menu_component=data.get('menu_component', ''),
            sort=data.get('sort', 0),
            enabled_flag=data.get('enabled_flag', 'Y'),
            display_flag=data.get('display_flag', 'Y'),
            admin_only=data.get('admin_only', 'N')
        )

        session.execute(insert_stmt)

    # update
    # ================================================================
    def update_master_key(self, session, data):
        stmt = update(
            MasterMenu
        ).where(
            MasterMenu.menu_code == data['menu_code']
        ).values(
            menu_parents=data['menu_parents'],
            menu_name=data['menu_name'],
            menu_path=data['menu_path'],
            menu_title=data.get('menu_title', ''),
            menu_component=data.get('menu_component', ''),
            sort=data.get('sort', 0),
            enabled_flag=data.get('enabled_flag', 'Y'),
            display_flag=data.get('display_flag', 'Y'),
            admin_only=data.get('admin_only', 'N')
        )
        session.execute(stmt)