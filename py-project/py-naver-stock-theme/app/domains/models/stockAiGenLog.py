"""
stock_ai_gen_log — AI 분석을 새로 만든(Anthropic 을 부른) 기록. 하루 생성 한도를 세는 데 쓴다.
sql: stock/002_stock_ai_gen_log.sql · yangbong/007_stock_ai_gen_log.sql
"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String

from stock_shared.base import Base


class StockAiGenLog(Base):
    __tablename__ = 'stock_ai_gen_log'

    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    stock_code = Column(String(20), nullable=False)
    section = Column(String(20), nullable=False)      # 'overview' | 'theme' | 'news'
    created_at = Column(DateTime, nullable=False)     # 서버(KST) 시각을 넣는다 — DB 시간대와 무관하게 '오늘'을 센다
