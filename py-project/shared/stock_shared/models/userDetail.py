"""
user_detail — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, DateTime, Integer, String, text

from stock_shared.base import Base


class UserDetail(Base):
    __tablename__ = "user_detail"

    user_id = Column(Integer, primary_key=True, nullable=False)
    salt = Column(String(16), nullable=False)
    pswd = Column(String(255), nullable=False)
    err_cnt = Column(Integer, nullable=True, server_default=text("0"))
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)
    upbit_access_key = Column(String(200), nullable=True)
    upbit_secret_key = Column(String(200), nullable=True)
    reset_flag = Column(String(1), nullable=True)
    kis_access_key = Column(String(200), nullable=True)
    kis_secret_key = Column(String(200), nullable=True)
    tele_bot_id = Column(String(200), nullable=True)
    tele_chat_id = Column(String(200), nullable=True)
    kis_id = Column(String(45), nullable=True)
    kis_account = Column(String(45), nullable=True)
    kis_app_key = Column(String(200), nullable=True)
    kis_sec_key = Column(String(500), nullable=True)
    kis_virtual_id = Column(String(50), nullable=True)
    kis_virtual_account = Column(String(50), nullable=True)
    kis_vir_app_key = Column(String(200), nullable=True)
    kis_vir_sec_key = Column(String(500), nullable=True)

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "salt": self.salt,
            "pswd": self.pswd,
            "err_cnt": self.err_cnt,
            "created_date": self.created_date,
            "updated_date": self.updated_date,
            "upbit_access_key": self.upbit_access_key,
            "upbit_secret_key": self.upbit_secret_key,
            "reset_flag": self.reset_flag,
            "kis_access_key": self.kis_access_key,
            "kis_secret_key": self.kis_secret_key,
            "tele_bot_id": self.tele_bot_id,
            "tele_chat_id": self.tele_chat_id,
            "kis_id": self.kis_id,
            "kis_account": self.kis_account,
            "kis_app_key": self.kis_app_key,
            "kis_sec_key": self.kis_sec_key,
            "kis_virtual_id": self.kis_virtual_id,
            "kis_virtual_account": self.kis_virtual_account,
            "kis_vir_app_key": self.kis_vir_app_key,
            "kis_vir_sec_key": self.kis_vir_sec_key,
        }
