from sqlalchemy import Column, String, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MasterCodes(Base):
    __tablename__ = 'master_codes'

    system = Column(String(64), nullable=False)
    source = Column(String(64), nullable=False)
    category = Column(String(64), nullable=False)
    code = Column(String(45), nullable=False)
    desc = Column(String(64))

    __table_args__ = (
        PrimaryKeyConstraint('system', 'source', 'category', 'code'),
    )

    def to_dict(self):
        return {
            "system": self.system,
            "source": self.source,
            "category": self.category,
            "code": self.code,
            "desc": self.desc,
        }
