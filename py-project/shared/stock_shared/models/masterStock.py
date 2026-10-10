"""
master_stock — DB(stock) 스키마 기준 자동 생성 모델.
※ 스키마 변경 시 이 파일을 DB 기준으로 재생성할 것.
"""
from sqlalchemy import BigInteger, Column, DateTime, String, text

from stock_shared.base import Base


class MasterStock(Base):
    __tablename__ = "master_stock"

    corp_code = Column(String(20), primary_key=True, nullable=False)
    stock_code = Column(String(6), nullable=False)
    stock_name = Column(String(100), nullable=False)
    stock_type = Column(String(6), nullable=False)
    stock_type_yf = Column(String(45), nullable=True)
    stock_class = Column(String(1), nullable=True)
    group_code = Column(String(45), nullable=True)
    created_date = Column(DateTime, nullable=True)
    market_stop = Column(String(1), nullable=True)
    nxt_flag = Column(String(1), nullable=True, server_default=text("N"))
    # KRX 종목마스터(.mst) 파일에 이미 포함된 필드. 2026-09 세션: 매수추천이 관리종목/
    # 정리매매 종목에 쏠리는 문제 확인 후, 별도 API 호출 없이 기존 마스터 다운로드에서
    # 바로 채우도록 추가(StockCodeMasterJob.extract_data 참고). 값은 'Y'/'N'.
    admin_issue = Column(String(1), nullable=True)   # 관리종목
    trading_halt = Column(String(1), nullable=True)  # 정리매매
    # 상장주식수(주) — 같은 .mst 의 '상장주수'(천주) ×1000 (sql/31_stock_market_cap_investor.sql).
    # 시가총액은 이 값 × 직전 영업일 종가(stock_investor_daily)로 API 에서 계산한다.
    listed_shares = Column(BigInteger, nullable=True)

    def to_dict(self):
        return {
            "corp_code": self.corp_code,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "stock_type": self.stock_type,
            "stock_type_yf": self.stock_type_yf,
            "stock_class": self.stock_class,
            "group_code": self.group_code,
            "created_date": self.created_date,
            "market_stop": self.market_stop,
            "nxt_flag": self.nxt_flag,
            "admin_issue": self.admin_issue,
            "trading_halt": self.trading_halt,
            "listed_shares": self.listed_shares,
        }
