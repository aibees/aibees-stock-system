from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MasterHoliday(Base):
    __tablename__ = 'master_holiday'

    ymd        = Column(String(8), primary_key=True)
    kind       = Column(String(3), nullable=True)
    name       = Column(String(45), nullable=True)
    is_holiday = Column(String(1), nullable=True)

    def to_dict(self):
        return {
            'ymd':        self.ymd,
            'kind':       self.kind,
            'name':       self.name,
            'is_holiday': self.is_holiday,
        }
