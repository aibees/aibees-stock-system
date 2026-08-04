from sqlalchemy import Column, BigInteger, Integer, DateTime, String, PrimaryKeyConstraint
from app.domain.model.base import Base


class MasterThemeCode(Base):
    __tablename__ = 'master_themes_code'

    theme_code = Column(String(5), nullable=False)
    stock_code = Column(String(6), nullable=False)
    created_date = Column(DateTime)

    __table_args__ = (
        PrimaryKeyConstraint('theme_code', 'stock_code'),
    )

    def to_dict(self):
        return {
            'theme_code': self.theme_code,
            'stock_code': self.stock_code,
            'created_date': self.created_date
        }