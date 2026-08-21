"""
user_option_m3 — M3(KODEX 코스피100 / 인버스 **독립 운용**) 개인화 옵션.

  구 '교대(regime flip)' 시나리오 컬럼은 07_user_option_m3_rebuild.sql 로 제거됐다.
  현행 M3 는 두 ETF 를 각자 신호로만 사고팔고, 신호가 없으면 현금으로 쉰다.

  · 모든 값 NULL 허용. NULL = KospiStrategy3 클래스 기본값 사용
  · 행이 없어도 동작해야 한다. row 없음 == 전 항목 NULL

DDL: py-project/sql/02_user_option_mode_ddl.sql + 07_user_option_m3_rebuild.sql
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT

from stock_shared.base import Base


class UserOptionM3(Base):
    __tablename__ = "user_option_m3"

    MODE_CODE = "M3"

    user_id = Column(Integer, primary_key=True, nullable=False)

    # ── 대상 ETF (각각 독립 운용) ─────────────────────────────────────
    long_code            = Column(String(20), nullable=True)    # 정방향 ETF (기본 237350)
    long_name            = Column(String(100), nullable=True)
    short_code           = Column(String(20), nullable=True)    # 인버스 ETF (기본 114800)
    short_name           = Column(String(100), nullable=True)

    # ── 진입: 4조건(MACD↑ OBV↑ MA20↑ RSI<x) 이 confirm_bars 봉 연속 ────
    confirm_bars         = Column(Integer, nullable=True)       # 기본 3. 1=즉시
    rsi_overbought       = Column(Integer, nullable=True)       # 기본 70
    enable_macd_up       = Column(TINYINT(1), nullable=True)    # 기본 1
    enable_obv_up        = Column(TINYINT(1), nullable=True)    # 기본 1
    enable_ma20_up       = Column(TINYINT(1), nullable=True)    # 기본 1
    enable_rsi_filter    = Column(TINYINT(1), nullable=True)    # 기본 1

    # ── 청산: 모멘텀 이탈 (연속확인 없이 1봉) ─────────────────────────
    exit_on_reverse      = Column(TINYINT(1), nullable=True)    # 기본 1
    exit_macd_down       = Column(TINYINT(1), nullable=True)    # 기본 1
    exit_obv_down        = Column(TINYINT(1), nullable=True)    # 기본 1
    exit_rsi_down        = Column(TINYINT(1), nullable=True)    # 기본 1

    # ── 청산: 가격 라인 (30분봉 스케일. 손절 기본 -2%) ────────────────
    stop_loss_pct        = Column(DECIMAL(6, 4), nullable=True)
    take_profit_pct      = Column(DECIMAL(6, 4), nullable=True)
    use_trailing         = Column(TINYINT(1), nullable=True)
    trail_activate_pct   = Column(DECIMAL(6, 4), nullable=True)
    trail_drawdown_pct   = Column(DECIMAL(6, 4), nullable=True)

    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    #: 파라미터 컬럼명 목록. UserOptionMeta 조립·저장 화이트리스트로 쓴다.
    PARAM_KEYS = (
        "long_code", "long_name", "short_code", "short_name",
        "confirm_bars", "rsi_overbought",
        "enable_macd_up", "enable_obv_up", "enable_ma20_up", "enable_rsi_filter",
        "exit_on_reverse", "exit_macd_down", "exit_obv_down", "exit_rsi_down",
        "stop_loss_pct", "take_profit_pct",
        "use_trailing", "trail_activate_pct", "trail_drawdown_pct",
    )

    def to_dict(self):
        d = {"user_id": self.user_id}
        d.update({k: getattr(self, k) for k in self.PARAM_KEYS})
        return d
