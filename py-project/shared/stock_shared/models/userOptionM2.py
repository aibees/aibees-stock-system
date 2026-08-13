"""
user_option_m2 — M2(단일 종목 고정) 개인화 옵션.

  · 모든 값 NULL 허용. NULL = KospiStrategy2 클래스 기본값 사용
  · 행이 없어도 동작해야 한다. row 없음 == 전 항목 NULL

DDL: py-project/sql/02_user_option_mode_ddl.sql
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT

from stock_shared.base import Base


class UserOptionM2(Base):
    __tablename__ = "user_option_m2"

    MODE_CODE = "M2"

    user_id = Column(Integer, primary_key=True, nullable=False)

    # ── 대상 종목 ─────────────────────────────────────────────────────
    stock_code         = Column(String(20), nullable=True)
    stock_name         = Column(String(100), nullable=True)   # 표시용 스냅샷

    # ── 진입 ──────────────────────────────────────────────────────────
    entry_rule         = Column(String(10), nullable=True)    # IMMEDIATE | SIGNAL (기본 SIGNAL)
    invest_ratio       = Column(DECIMAL(5, 4), nullable=True)  # 예수금 대비 투입 비율 (기본 1.0)

    # ── 매도 판정 ─────────────────────────────────────────────────────
    stop_loss_pct      = Column(DECIMAL(6, 4), nullable=True)
    take_profit_pct    = Column(DECIMAL(6, 4), nullable=True)
    use_trailing       = Column(TINYINT(1), nullable=True)
    trail_activate_pct = Column(DECIMAL(6, 4), nullable=True)
    trail_drawdown_pct = Column(DECIMAL(6, 4), nullable=True)
    k_trail_atr        = Column(DECIMAL(6, 2), nullable=True)
    max_hold_bars      = Column(Integer, nullable=True)

    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    #: 파라미터 컬럼명 목록. UserOptionMeta 조립·저장 화이트리스트로 쓴다.
    PARAM_KEYS = (
        "stock_code", "stock_name", "entry_rule", "invest_ratio",
        "stop_loss_pct", "take_profit_pct", "use_trailing",
        "trail_activate_pct", "trail_drawdown_pct", "k_trail_atr",
        "max_hold_bars",
    )

    def to_dict(self):
        d = {"user_id": self.user_id}
        d.update({k: getattr(self, k) for k in self.PARAM_KEYS})
        return d
