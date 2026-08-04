from sqlalchemy import Column, BigInteger, Integer, DateTime, String

from stock_shared.base import Base

class MasterMenu(Base):
    __tablename__ = 'master_menu'
    
    menu_code    = Column(String(64), primary_key=True)
    menu_parents = Column(String(45), nullable=False)
    menu_name    = Column(String(45), nullable=False)
    menu_path    = Column(String(45), nullable=False)
    enabled_flag = Column(String(1), nullable=False)
    display_flag = Column(String(1), nullable=False)
    menu_component = Column(String(45), nullable=False)
    menu_title   = Column(String(200), nullable=True)
    sort         = Column(Integer, nullable=False)
    admin_only   = Column(String(1), nullable=False)
    
    def to_dict(self):
        return {
            'menu_code': self.menu_code,
            'menu_parents': self.menu_parents,
            'menu_name': self.menu_name,
            'menu_path': self.menu_path,
            'enabled_flag': self.enabled_flag,
            'display_flag': self.display_flag,
            'menu_component': self.menu_component,
            'menu_title': self.menu_title,
            'sort': self.sort,
            'admin_only': self.admin_only,
        }