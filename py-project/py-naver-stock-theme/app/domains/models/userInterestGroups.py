from sqlalchemy import Column, BigInteger, Integer, DateTime, String, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserInterestGroups(Base):
    __tablename__ = 'user_interest_groups'
    
    group_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    group_name = Column(String(200), nullable=False)
    
    __table_args__ = (
        PrimaryKeyConstraint('group_id', 'user_id')
    )
    
    def to_dict(self):
        return {
            'group_id': self.group_id,
            'user_id': self.user_id,
            'group_name': self.group_name
        }