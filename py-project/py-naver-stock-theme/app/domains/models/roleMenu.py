from sqlalchemy import Column, DateTime, String

from stock_shared.base import Base


class RoleMenu(Base):
    """권한(auth_id)별 접근 가능 메뉴. 행이 있어야 보이는 allow-list."""
    __tablename__ = 'role_menu'

    auth_id      = Column(String(64), primary_key=True)
    menu_code    = Column(String(64), primary_key=True)
    enabled_flag = Column(String(1), nullable=False, default='Y')
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)


class RoleFeature(Base):
    """권한(auth_id)별 기능 플래그(AD_FREE 등). ADMIN 자동 허용 없이 명시 매핑만 인정한다."""
    __tablename__ = 'role_feature'

    auth_id      = Column(String(64), primary_key=True)
    feature_code = Column(String(64), primary_key=True)
    enabled_flag = Column(String(1), nullable=False, default='Y')
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)
