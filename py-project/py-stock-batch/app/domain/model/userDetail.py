from sqlalchemy import Column, Integer, String, DateTime
from app.domain.model.base import Base

class UserDetail(Base):
    __tablename__ = 'user_detail'

    user_id = Column(Integer, primary_key=True, nullable=False)
    salt = Column(String(16), nullable=False)
    pswd = Column(String(255), nullable=False)
    err_cnt = Column(Integer, default=0)
    created_date = Column(DateTime)
    updated_date = Column(DateTime)
    upbit_access_key = Column(String(200))
    upbit_secret_key = Column(String(200))
    tele_bot_id      = Column(String(200))
    tele_chat_id     = Column(String(200))

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "salt": self.salt,
            "pswd": self.pswd,
            "err_cnt": self.err_cnt,
            "created_date": self.created_date.isoformat() if self.created_date else None,
            "updated_date": self.updated_date.isoformat() if self.updated_date else None,
            "upbit_access_key": self.upbit_access_key,
            "upbit_secret_key": self.upbit_secret_key,
            "tele_bot_id": self.tele_bot_id,
            "tele_chat_id": self.tele_chat_id,
        }
