"""
trade_sell_target_stock — 매도 체크 결과(배치 출력) 모델.

py-stock-batch/app/domain/model 에 있던 것을 shared 로 이관.
(같은 metadata 를 쓰는 공용 Base 아래로 모으고, 두 프로젝트에서 재사용 가능하게 함)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL

from stock_shared.base import Base


class TradeSellTargetStock(Base):
    """
    매도 체크 결과 저장 테이블 (배치 출력).
    - StockSellCheckJob이 stock_sell_request(입력)를 읽어 체크 후 여기에 upsert
    - 진입 정보는 stock_sell_request에서 복사되어 스냅샷으로 보관 (조인 없이 조회 가능)
    - 포지션 추적값(bars_held, peak_close 등)은 배치 실행마다 갱신
    """
    __tablename__ = 'trade_sell_target_stock'

    # ── PK (복합 PK: user_id + stock_code) ──────────────
    user_id    = Column(Integer, primary_key=True, nullable=False)
    stock_code = Column(String(45), primary_key=True, nullable=False)
    stock_name = Column(String(45))

    # ── 진입 정보 (매수 시 세팅, 이후 변경 없음) ──────────
    entry_date  = Column(String(8))            # 매수 체결일 YYYYMMDD
    entry_price = Column(DECIMAL(18, 8))       # 진입 평균단가
    entry_atr   = Column(DECIMAL(18, 8))       # 진입 시점 ATR (초기 손절 고정용)
    hold_qty    = Column(DECIMAL(18, 8))       # 보유 수량

    # ── 포지션 추적 (배치 실행마다 갱신) ─────────────────
    bars_held       = Column(Integer, default=0)    # 보유 봉수(일봉 기준)
    peak_close      = Column(DECIMAL(18, 8))        # 진입 후 종가 최고가
    peak_high       = Column(DECIMAL(18, 8))        # 진입 후 장중 최고가
    bars_since_peak = Column(Integer, default=0)    # 신고가 갱신 후 경과 봉수
    last_check_ymd  = Column(String(8))             # 마지막으로 bars_held를 증가시킨 날짜

    # ── 현재 시세 (매 체크마다 갱신) ─────────────────────
    curr_open   = Column(DECIMAL(18, 8))
    curr_high   = Column(DECIMAL(18, 8))
    curr_low    = Column(DECIMAL(18, 8))
    curr_close  = Column(DECIMAL(18, 8))
    curr_volume = Column(DECIMAL(18, 8))
    curr_rate   = Column(String(45))           # 전일 대비 등락률

    # ── 매도 판단 결과 (매 체크마다 갱신) ────────────────
    # action_type: HOLD / SELL_STOP_LOSS / SELL_PROFIT / SELL_TRAIL / SELL_TIME
    action_type  = Column(String(45), default='HOLD')
    profit_pct   = Column(String(45))          # 수익률 ex) "12.34%"
    stop_price   = Column(DECIMAL(18, 8))      # 현재 손절가
    target_price = Column(DECIMAL(18, 8))      # 익절가
    trail_line   = Column(DECIMAL(18, 8))      # 트레일링 스탑 라인
    sell_reason  = Column(String(255))         # 매도 근거 메모

    # ── 상태 / 타임스탬프 ─────────────────────────────────
    status     = Column(String(20), default='active')  # active / sold
    checked_at = Column(DateTime)                       # 마지막 체크 시각
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        def f(v):
            return float(v) if v is not None else None

        return {
            'user_id':         self.user_id,
            'stock_code':      self.stock_code,
            'stock_name':      self.stock_name,
            'entry_date':      self.entry_date,
            'entry_price':     f(self.entry_price),
            'entry_atr':       f(self.entry_atr),
            'hold_qty':        f(self.hold_qty),
            'bars_held':       self.bars_held,
            'peak_close':      f(self.peak_close),
            'peak_high':       f(self.peak_high),
            'bars_since_peak': self.bars_since_peak,
            'last_check_ymd':  self.last_check_ymd,
            'curr_open':       f(self.curr_open),
            'curr_high':       f(self.curr_high),
            'curr_low':        f(self.curr_low),
            'curr_close':      f(self.curr_close),
            'curr_volume':     f(self.curr_volume),
            'curr_rate':       self.curr_rate,
            'action_type':     self.action_type,
            'profit_pct':      self.profit_pct,
            'stop_price':      f(self.stop_price),
            'target_price':    f(self.target_price),
            'trail_line':      f(self.trail_line),
            'sell_reason':     self.sell_reason,
            'status':          self.status,
            'checked_at':      self.checked_at.isoformat() if self.checked_at else None,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
            'updated_at':      self.updated_at.isoformat() if self.updated_at else None,
        }
