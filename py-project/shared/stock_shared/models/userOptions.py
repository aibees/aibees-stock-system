"""
user_options — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class UserOptions(Base):
    __tablename__ = "user_options"

    user_id = Column(Integer, primary_key=True, nullable=False)
    upbit_push_flag = Column(String(1), nullable=True)
    stock_sell_mail_flag = Column(String(1), nullable=True)
    stock_buy_target_mail_flag = Column(String(1), nullable=True)
    stock_sell_tele_flag = Column(String(1), nullable=True)
    buy_confirm = Column(Integer, nullable=True)
    buy_entry = Column(Integer, nullable=True)
    sell_entry = Column(Integer, nullable=True)
    sell_exit = Column(Integer, nullable=True)
    user_balance = Column(DECIMAL(18, 8), nullable=True)
    ratio_trend = Column(DECIMAL(2, 2), nullable=True)
    ratio_momentum = Column(DECIMAL(2, 2), nullable=True)
    ratio_volatility = Column(DECIMAL(2, 2), nullable=True)
    ratio_volume = Column(DECIMAL(2, 2), nullable=True)
    time_frame = Column(String(45), nullable=True)
    macd_recent_day = Column(Integer, nullable=True)
    bb_over_recent_day = Column(Integer, nullable=True)
    vol_limit = Column(Integer, nullable=True)
    vol_surge = Column(DECIMAL(4, 2), nullable=True)

    # 추천매수(RECO) 전략 파라미터는 user_option_reco 로 옮겼다(sql/54).

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "upbit_push_flag": self.upbit_push_flag,
            "stock_sell_mail_flag": self.stock_sell_mail_flag,
            "stock_buy_target_mail_flag": self.stock_buy_target_mail_flag,
            "stock_sell_tele_flag": self.stock_sell_tele_flag,
            "buy_confirm": self.buy_confirm,
            "buy_entry": self.buy_entry,
            "sell_entry": self.sell_entry,
            "sell_exit": self.sell_exit,
            "user_balance": self.user_balance,
            "ratio_trend": self.ratio_trend,
            "ratio_momentum": self.ratio_momentum,
            "ratio_volatility": self.ratio_volatility,
            "ratio_volume": self.ratio_volume,
            "time_frame": self.time_frame,
            "macd_recent_day": self.macd_recent_day,
            "bb_over_recent_day": self.bb_over_recent_day,
            "vol_limit": self.vol_limit,
            "vol_surge": self.vol_surge,
        }
