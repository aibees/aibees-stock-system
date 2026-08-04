from sqlalchemy import Column, Integer, String

from stock_shared.base import Base

class Campaign(Base):
    __tablename__ = 'campaign'

    id            = Column(Integer,    primary_key=True)
    ymd           = Column(String(45), nullable=False)
    campaign      = Column(String(45), nullable=True)
    adv           = Column(String(45), nullable=True)
    card_nm       = Column(String(45), nullable=True)
    keyword       = Column(String(45), nullable=True)
    exposed       = Column(Integer,    nullable=True)
    clicked       = Column(Integer,    nullable=True)
    avg_click_amt = Column(String(45), nullable=True)
    total_amt     = Column(String(45), nullable=True)

    def to_dict(self):
        return {
            'id':            self.id,
            'ymd':           self.ymd,
            'campaign':      self.campaign,
            'adv':           self.adv,
            'card_nm':       self.card_nm,
            'keyword':       self.keyword,
            'exposed':       self.exposed,
            'clicked':       self.clicked,
            'avg_click_amt': self.avg_click_amt,
            'total_amt':     self.total_amt,
        }
