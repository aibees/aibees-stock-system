from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserDetail(Base):
    __tablename__ = 'user_detail'

    user_id = Column(Integer, primary_key=True)
    salt = Column(String(16), nullable=False)
    pswd = Column(String(255), nullable=False)
    err_cnt = Column(Integer, nullable=False)
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)
    reset_flag = Column(String(1), nullable=True)
    kis_id = Column(String(50), nullable=True)
    kis_account = Column(String(50), nullable=True)
    kis_access_key = Column(String(200), nullable=True)
    kis_secret_key = Column(String(200), nullable=True)
    upbit_access_key = Column(String(200), nullable=True)
    upbit_secret_key = Column(String(200), nullable=True)
    tele_bot_id = Column(String(100), nullable=True)
    tele_chat_id = Column(String(100), nullable=True)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'salt': self.salt,
            'pswd': self.pswd,
            'err_cnt': self.err_cnt,
            'created_date': self.created_date,
            'updated_date': self.updated_date,
            'reset_flag': self.reset_flag,
            'kis_id': self.kis_id,
            'kis_account': self.kis_account,
            'kis_access_key': self.kis_access_key,
            'kis_secret_key': self.kis_secret_key,
            'upbit_access_key': self.upbit_access_key,
            'upbit_secret_key': self.upbit_secret_key,
            'tele_bot_id': self.tele_bot_id,
            'tele_chat_id': self.tele_chat_id,
        }
