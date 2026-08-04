from sqlalchemy import Column, Integer, String, PrimaryKeyConstraint
from app.domain.model.base import Base

class UserInterestGroups(Base):
    __tablename__ = 'user_interest_groups'

    division = Column(String(45), nullable=False)
    group_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    group_name = Column(String(45), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('division', 'group_id', 'user_id'),
    )

    def to_dict(self):
        return {
            "division": self.division,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "group_name": self.group_name,
        }
