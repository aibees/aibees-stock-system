"""
trade_candle_30m — M3 30분봉 캔들. DB(stock) 스키마 기준 자동 생성 모델.

trade_candle_data(일봉) 와 컬럼 구성이 100% 동일하다.
  → DDL 이 `CREATE TABLE trade_candle_30m LIKE trade_candle_data` 이기 때문.
  → compute_indicator_df 결과를 타임프레임과 무관하게 그대로 적재할 수 있다.

datetime 은 봉의 **시작 시각** ('YYYY-MM-DD HH:MM:SS').
  09:00:00 = 09:00~09:29 구간. 정규장 기준 하루 13봉.

※ 스키마 변경 시 trade_candle_data 와 **함께** 재생성할 것.
   두 파일이 어긋나면 지표 적재가 조용히 깨진다.
"""
from sqlalchemy import Column, PrimaryKeyConstraint, String
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base
from stock_shared.models.tradeCandleData import TradeCandleData


class TradeCandle30m(Base):
    __tablename__ = "trade_candle_30m"

    __table_args__ = (PrimaryKeyConstraint("coin", "datetime"),)

    coin = Column(String(10), nullable=False)
    datetime = Column(String(19), nullable=False)
    open = Column(DECIMAL(18, 8), nullable=False)
    high = Column(DECIMAL(18, 8), nullable=False)
    low = Column(DECIMAL(18, 8), nullable=False)
    close = Column(DECIMAL(18, 8), nullable=False)
    volume = Column(DECIMAL(18, 8), nullable=False)
    ema20 = Column(DECIMAL(18, 8), nullable=True)
    ema60 = Column(DECIMAL(18, 8), nullable=True)
    ema120 = Column(DECIMAL(18, 8), nullable=True)
    bb_mid = Column(DECIMAL(18, 8), nullable=True)
    bb_lower = Column(DECIMAL(18, 8), nullable=True)
    bb_lower_chk = Column(DECIMAL(1, 0), nullable=True)
    bb_upper = Column(DECIMAL(18, 8), nullable=True)
    bb_upper_chk = Column(DECIMAL(1, 0), nullable=True)
    bb_width = Column(DECIMAL(18, 8), nullable=True)
    bb_width_avg = Column(DECIMAL(18, 8), nullable=True)
    macd = Column(DECIMAL(18, 8), nullable=True)
    macd_s = Column(DECIMAL(18, 8), nullable=True)
    macd_lower_mean = Column(DECIMAL(18, 8), nullable=True)
    macd_upper_mean = Column(DECIMAL(18, 8), nullable=True)
    macd_recent_min = Column(DECIMAL(18, 8), nullable=True)
    macd_recent_max = Column(DECIMAL(18, 8), nullable=True)
    fs_k = Column(DECIMAL(18, 8), nullable=True)
    fs_d = Column(DECIMAL(18, 8), nullable=True)
    roc = Column(DECIMAL(18, 8), nullable=True)
    atr = Column(DECIMAL(18, 8), nullable=True)
    obv = Column(DECIMAL(18, 8), nullable=True)
    obv_signal = Column(DECIMAL(18, 8), nullable=True)
    obv_cross = Column(String(1), nullable=True)
    obv_recent_min = Column(DECIMAL(18, 8), nullable=True)
    obv_recent_max = Column(DECIMAL(18, 8), nullable=True)
    rsi = Column(DECIMAL(18, 8), nullable=True)
    rsi_signal = Column(DECIMAL(18, 8), nullable=True)
    rsi_cross = Column(String(1), nullable=True)
    score_trend = Column(DECIMAL(18, 8), nullable=True)
    score_momentum = Column(DECIMAL(18, 8), nullable=True)
    score_volatility = Column(DECIMAL(18, 8), nullable=True)
    score_volume = Column(DECIMAL(18, 8), nullable=True)
    score_total = Column(DECIMAL(18, 8), nullable=True)
    watch_action = Column(String(45), nullable=True)
    active_action = Column(String(45), nullable=True)
    regime = Column(String(45), nullable=True)
    bb_mid_breakout = Column(DECIMAL(18, 8), nullable=True)
    macd_g_cross_n = Column(String(1), nullable=True)
    macd_d_cross_n = Column(String(1), nullable=True)
    obv_g_cross_n = Column(String(1), nullable=True)
    obv_d_cross_n = Column(String(1), nullable=True)
    vol_surge_n = Column(DECIMAL(18, 8), nullable=True)
    recent_high = Column(DECIMAL(18, 8), nullable=True)

    # 컬럼 구성이 동일하므로 직렬화 로직을 재사용한다.
    # (별도 구현하면 컬럼 추가 시 한쪽만 고치는 사고가 난다)
    to_dict = TradeCandleData.to_dict
