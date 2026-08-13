"""
user_option_m3 — M3(지정가 감시) 개인화 옵션.

  · 모든 값 NULL 허용. NULL = KospiStrategy3 클래스 기본값 사용
  · 행이 없어도 동작해야 한다. row 없음 == 전 항목 NULL

체결 상태는 이 테이블에 두지 않는다:
    WAIT_BUY == user_trade_mode.run_state 'ARMED'
    BOUGHT   == trade_worker_position.status 'HOLDING'
→ 설계문서(auto-trade-design.md §5-3)의 user_limit_order 를 대체한다.

DDL: py-project/sql/02_user_option_mode_ddl.sql
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT

from stock_shared.base import Base


class UserOptionM3(Base):
    __tablename__ = "user_option_m3"

    MODE_CODE = "M3"

    user_id = Column(Integer, primary_key=True, nullable=False)

    # ── 감시 종목 ─────────────────────────────────────────────────────
    stock_code    = Column(String(20), nullable=True)
    stock_name    = Column(String(100), nullable=True)     # 표시용 스냅샷

    # ── 지정가 ────────────────────────────────────────────────────────
    buy_price     = Column(DECIMAL(18, 4), nullable=True)  # 현재가 <= 이 값이면 매수
    sell_price    = Column(DECIMAL(18, 4), nullable=True)  # 현재가 >= 이 값이면 매도
    qty           = Column(Integer, nullable=True)         # NULL 이면 예수금 전량

    # ── 손절 병행 ─────────────────────────────────────────────────────
    use_stop_loss = Column(TINYINT(1), nullable=True)      # 기본 0
    stop_price    = Column(DECIMAL(18, 4), nullable=True)

    # ── 반복 / ON·OFF ─────────────────────────────────────────────────
    loop_flag     = Column(TINYINT(1), nullable=True)      # 매도 후 재감시 (기본 0)
    enabled_flag  = Column(String(1), nullable=True)       # Y/N (기본 Y)

    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    #: 파라미터 컬럼명 목록. UserOptionMeta 조립·저장 화이트리스트로 쓴다.
    PARAM_KEYS = (
        "stock_code", "stock_name", "buy_price", "sell_price", "qty",
        "use_stop_loss", "stop_price", "loop_flag", "enabled_flag",
    )

    def to_dict(self):
        d = {"user_id": self.user_id}
        d.update({k: getattr(self, k) for k in self.PARAM_KEYS})
        return d
