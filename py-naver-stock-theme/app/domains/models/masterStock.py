from sqlalchemy import Column, BigInteger, Integer, DateTime, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MasterStock(Base):
    __tablename__ = 'master_stock'
    
    corp_code = Column(String(20), primary_key=True)
    stock_code = Column(String(6), nullable=False)
    stock_name = Column(String(100), nullable=False)
    stock_type = Column(String(6), nullable=False)
    stock_type_yf = Column(String(45), nullable=False)
    
    def to_dict(self):
        return {
            'corp_code': self.corp_code,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'stock_type': self.stock_type,
            'stock_type_yf': self.stock_type_yf,
        }