from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.mysql import DECIMAL
from app.domain.model.base import Base


class StockSellRequest(Base):
    """
    매도 체크 희망 종목 입력 테이블 (Vue 화면에서 사용자가 관리).

    - 사용자가 Vue에서 보유 종목을 직접 등록/수정/비활성화
    - StockSellCheckJob이 enabled_flag='Y' 행을 읽어 매도 판단 수행
    - 판단 결과는 trade_sell_target_stock에 별도 저장
    """
    __tablename__ = 'stock_sell_request'

    # ── PK (복합 PK: user_id + stock_code) ──────────────
    user_id    = Column(Integer, primary_key=True, nullable=False)
    stock_code = Column(String(45), primary_key=True, nullable=False)
    stock_name = Column(String(45))

    # ── 진입 정보 (사용자가 Vue에서 입력) ─────────────────
    entry_date  = Column(String(8))        # 매수 체결일 YYYYMMDD
    entry_price = Column(DECIMAL(18, 8))   # 매수 평균단가
    hold_qty    = Column(DECIMAL(18, 8))   # 보유 수량

    # ── 사용자 메모 ───────────────────────────────────────
    memo = Column(String(255))

    # ── 활성화 여부 (Vue에서 제어) ────────────────────────
    # Y: 배치 체크 대상 / N: 일시 제외 (매도 완료 후 N 처리)
    enabled_flag = Column(String(1), nullable=False, default='Y')

    # ── 타임스탬프 ────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        def f(v):
            return float(v) if v is not None else None

        return {
            'user_id':      self.user_id,
            'stock_code':   self.stock_code,
            'stock_name':   self.stock_name,
            'entry_date':   self.entry_date,
            'entry_price':  f(self.entry_price),
            'hold_qty':     f(self.hold_qty),
            'memo':         self.memo,
            'enabled_flag': self.enabled_flag,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
            'updated_at':   self.updated_at.isoformat() if self.updated_at else None,
        }
