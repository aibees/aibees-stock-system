"""
user_option_m2 — M2(KOSPI100 ETF ↔ 인버스 교대) 개인화 옵션.

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

    # ── ETF 페어 ──────────────────────────────────────────────────────
    long_code            = Column(String(20), nullable=True)    # 정방향 ETF
    long_name            = Column(String(100), nullable=True)
    short_code           = Column(String(20), nullable=True)    # 인버스 ETF
    short_name           = Column(String(100), nullable=True)

    # ── 추세 판정 ─────────────────────────────────────────────────────
    trend_symbol         = Column(String(20), nullable=True)    # NULL 이면 long_code 일봉
    ma_short             = Column(Integer, nullable=True)       # 기본 5
    ma_long              = Column(Integer, nullable=True)       # 기본 20
    threshold_long       = Column(Integer, nullable=True)       # 기본 2
    threshold_short      = Column(Integer, nullable=True)       # 기본 2
    flip_cooldown_bars   = Column(Integer, nullable=True)       # 기본 0

    # ── 매도 판정 ─────────────────────────────────────────────────────
    stop_loss_pct        = Column(DECIMAL(6, 4), nullable=True)
    take_profit_pct      = Column(DECIMAL(6, 4), nullable=True)
    use_trailing         = Column(TINYINT(1), nullable=True)
    trail_activate_pct   = Column(DECIMAL(6, 4), nullable=True)
    trail_drawdown_pct   = Column(DECIMAL(6, 4), nullable=True)
    use_regime_flip_exit = Column(TINYINT(1), nullable=True)    # 반대 신호 강제 청산 (기본 1)

    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    #: 파라미터 컬럼명 목록. UserOptionMeta 조립·저장 화이트리스트로 쓴다.
    PARAM_KEYS = (
        "long_code", "long_name", "short_code", "short_name",
        "trend_symbol", "ma_short", "ma_long",
        "threshold_long", "threshold_short", "flip_cooldown_bars",
        "stop_loss_pct", "take_profit_pct", "use_trailing",
        "trail_activate_pct", "trail_drawdown_pct", "use_regime_flip_exit",
    )

    def to_dict(self):
        d = {"user_id": self.user_id}
        d.update({k: getattr(self, k) for k in self.PARAM_KEYS})
        return d
