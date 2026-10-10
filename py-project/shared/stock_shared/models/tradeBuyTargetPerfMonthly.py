"""
trade_buy_target_perf_monthly — DB(stock) 스키마 기준 모델 (sql/30_buy_target_perf_monthly.sql).
월별 추천 성과(홈 '전월 추천 성과') 계산 결과. 화면 응답 그대로를 JSON 문자열로 저장한다(컬럼화하지 않음).
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import CHAR, Column, DateTime, Text

from stock_shared.base import Base


class TradeBuyTargetPerfMonthly(Base):
    __tablename__ = "trade_buy_target_perf_monthly"

    ym = Column(CHAR(6), primary_key=True, nullable=False)     # 대상 월 YYYYMM
    payload = Column(Text, nullable=False)                     # API 응답 JSON
    final_flag = Column(CHAR(1), nullable=False)               # 'Y' 확정(더 이상 재계산 안 함) / 'N'
    calculated_at = Column(DateTime, nullable=False)           # 마지막 계산 시각

    def to_dict(self):
        return {
            "ym": self.ym,
            "payload": self.payload,
            "final_flag": self.final_flag,
            "calculated_at": self.calculated_at,
        }
