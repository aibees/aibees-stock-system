from sqlalchemy import Column, BigInteger, Integer, DateTime, String

from stock_shared.base import Base

class MasterInfos(Base):
    __tablename__ = 'master_infos'
    
    key_type     = Column(String(10), primary_key=True)
    key_value    = Column(String(256), nullable=False)
    expired_date = Column(DateTime, nullable=False)
    category     = Column(String(45), nullable=False)
    
    def to_dict(self):
        return {
            'key_type': self.key_type,
            'key_value': self.key_value,
            'expired_date': str(self.expired_date),
            'category': self.category
        }