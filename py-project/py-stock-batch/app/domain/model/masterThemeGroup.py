from sqlalchemy import Column, BigInteger, Integer, DateTime, String
from app.domain.model.base import Base


class MasterThemeGroup(Base):
    __tablename__ = 'master_themes_group'

    theme_code = Column(String(5), primary_key=True)
    theme_name = Column(String(100))
    created_date = Column(DateTime)

    def to_dict(self):
        return {
            'theme_code': self.theme_code,
            'theme_name': self.theme_name,
            'created_date': self.created_date
        }