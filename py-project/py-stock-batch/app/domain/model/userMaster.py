from sqlalchemy import Column, Integer, String, UniqueConstraint
from app.domain.model.base import Base

class UserMaster(Base):
    __tablename__ = 'user_master'

    user_id = Column(Integer, primary_key=True, nullable=False)
    user_name = Column(String(45), nullable=False)
    user_phone = Column(String(13), unique=True)
    email = Column(String(200), unique=True)
    gender = Column(String(2))
    age = Column(String(45))

    __table_args__ = (
        UniqueConstraint('user_phone', name='user_phone_UNIQUE'),
        UniqueConstraint('email', name='email_UNIQUE'),
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_phone": self.user_phone,
            "email": self.email,
            "gender": self.gender,
            "age": self.age,
        }