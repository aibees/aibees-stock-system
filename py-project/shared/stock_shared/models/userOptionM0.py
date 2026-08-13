"""
user_option_m0 — M0(추천 1순위) 개인화 옵션.

기존 user_options.s1_* 39개 컬럼을 모드별 테이블로 분리한 것.
컬럼명은 s1_ 접두어를 제거했다(테이블명이 이미 모드를 식별).

  · 모든 값 NULL 허용. NULL = KospiStrategy0 클래스 기본값 사용
  · 행이 없어도 동작해야 한다. row 없음 == 전 항목 NULL

DDL: py-project/sql/02_user_option_mode_ddl.sql
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.dialects.mysql import DECIMAL, TINYINT

from stock_shared.base import Base


class UserOptionM0(Base):
    __tablename__ = "user_option_m0"

    MODE_CODE = "M0"

    user_id = Column(Integer, primary_key=True, nullable=False)

    stop_loss_pct          = Column(DECIMAL(6, 4), nullable=True)  # 손절 비율 (기본 0.05)
    take_profit_pct        = Column(DECIMAL(6, 4), nullable=True)  # 익절 비율 (기본 0.30)
    max_hold_bars          = Column(Integer, nullable=True)  # 최대 보유 봉수 (기본 12)
    rsi_overbought         = Column(Integer, nullable=True)  # RSI 과매수 기준 (기본 70)
    rsi_ideal_low          = Column(Integer, nullable=True)  # RSI 신뢰구간 하한 (기본 40)
    rsi_ideal_high         = Column(Integer, nullable=True)  # RSI 신뢰구간 상한 (기본 65)
    vol_ma_window          = Column(Integer, nullable=True)  # 평균 거래량 산정 기간 (기본 20)
    vol_ma_mult            = Column(DECIMAL(6, 2), nullable=True)  # 진입 최소 거래량 배수 (기본 0.5)
    regime_window          = Column(Integer, nullable=True)  # 국면 분류 봉 길이 (기본 90)
    regime_threshold       = Column(DECIMAL(6, 4), nullable=True)  # 하락국면 판정 임계값 (기본 0.70)
    strict_need_macd_up    = Column(TINYINT(1), nullable=True)  # 하락국면: macd>=signal 요구 (기본 1)
    loose_need_vol_surge   = Column(TINYINT(1), nullable=True)  # 상승국면: 거래량급증 요구 (기본 1)
    surge_relax_mult       = Column(DECIMAL(6, 2), nullable=True)  # 완화 급증 배수 전봉대비 (기본 2.0)
    downtrend_surge_bypass = Column(TINYINT(1), nullable=True)  # 하락국면 거래량급증 우회 (기본 1)
    surge_bypass_mult      = Column(DECIMAL(6, 2), nullable=True)  # 우회 급증 판정 배수 (기본 2.0)
    use_trailing           = Column(TINYINT(1), nullable=True)  # 트레일링 스탑 사용 여부 (기본 1)
    trail_basis            = Column(String(5), nullable=True)  # close/high (기본 close). 미참조 - 롤백 대비 보존
    trail_activate_pct     = Column(DECIMAL(6, 4), nullable=True)  # 트레일링 활성화 수익 기준 (기본 0.08)
    k_trail_atr            = Column(DECIMAL(6, 2), nullable=True)  # 샹들리에 ATR 배수 (기본 3.0)
    trail_floor_pct        = Column(DECIMAL(6, 4), nullable=True)  # ATR 미산출 시 대체 하락폭 (기본 0.10)
    trail_drawdown_pct     = Column(DECIMAL(6, 4), nullable=True)  # 고점 대비 -x% 트레일 (0.0500=-5%). 설정 시 k_trail_atr 대체. NULL=ATR 방식
    trail_giveback_pct     = Column(DECIMAL(6, 4), nullable=True)  # 평가이익 중 x% 반납 시 청산 (0.38=38%). NULL=미사용
    trail_dual             = Column(TINYINT(1), nullable=True)  # 트레일링 이중 라인 사용
    trail_fib_use          = Column(TINYINT(1), nullable=True)  # 피보나치 되돌림 트레일 사용
    trail_fib_level        = Column(DECIMAL(5, 3), nullable=True)  # 피보나치 되돌림 레벨 (0.382/0.5/0.618)
    time_stop_extend       = Column(TINYINT(1), nullable=True)  # 타임스탑 연장 허용 (기본 1)
    time_stop_band         = Column(DECIMAL(6, 4), nullable=True)  # 정체 판정 수익밴드 (기본 0.02)
    time_stop_grace        = Column(Integer, nullable=True)  # 신고가 갱신 허용 봉수 (기본 3)
    max_hold_bars_hard     = Column(Integer, nullable=True)  # 절대 보유 한도 (기본 20)
    obv_dead_min_bars      = Column(Integer, nullable=True)  # OBV 데드크로스 노이즈 무시 봉수 (기본 5)
    enable_macd_filter     = Column(TINYINT(1), nullable=True)  # 매수필터: MACD 조건(macd_ok) 사용
    enable_rsi_filter      = Column(TINYINT(1), nullable=True)  # 매수필터: RSI 과매수 진입차단 사용
    enable_bb_upper_filter = Column(TINYINT(1), nullable=True)  # 매수필터: BB 상단 추격금지 사용
    enable_vol_avg_filter  = Column(TINYINT(1), nullable=True)  # 매수필터: 20일 평균거래량 하한 사용
    enable_regime_gate     = Column(TINYINT(1), nullable=True)  # 매수필터: 적응형 추세국면 게이트 사용
    macd_signal_mode       = Column(String(10), nullable=True)  # core 신호 MACD: off|golden|slope
    obv_signal_mode        = Column(String(10), nullable=True)  # core 신호 OBV: off|golden|slope
    ma20_signal_mode       = Column(String(10), nullable=True)  # MA20(ema20) 기울기 게이트: off|slope
    buy_order              = Column(String(255), nullable=True)  # worker 매수타겟 정렬. score:desc,volume:desc 형식

    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    #: 파라미터 컬럼명 목록. UserOptionMeta 조립·저장 화이트리스트로 쓴다.
    PARAM_KEYS = (
        "stop_loss_pct",
        "take_profit_pct",
        "max_hold_bars",
        "rsi_overbought",
        "rsi_ideal_low",
        "rsi_ideal_high",
        "vol_ma_window",
        "vol_ma_mult",
        "regime_window",
        "regime_threshold",
        "strict_need_macd_up",
        "loose_need_vol_surge",
        "surge_relax_mult",
        "downtrend_surge_bypass",
        "surge_bypass_mult",
        "use_trailing",
        "trail_basis",
        "trail_activate_pct",
        "k_trail_atr",
        "trail_floor_pct",
        "trail_drawdown_pct",
        "trail_giveback_pct",
        "trail_dual",
        "trail_fib_use",
        "trail_fib_level",
        "time_stop_extend",
        "time_stop_band",
        "time_stop_grace",
        "max_hold_bars_hard",
        "obv_dead_min_bars",
        "enable_macd_filter",
        "enable_rsi_filter",
        "enable_bb_upper_filter",
        "enable_vol_avg_filter",
        "enable_regime_gate",
        "macd_signal_mode",
        "obv_signal_mode",
        "ma20_signal_mode",
        "buy_order",
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_hold_bars": self.max_hold_bars,
            "rsi_overbought": self.rsi_overbought,
            "rsi_ideal_low": self.rsi_ideal_low,
            "rsi_ideal_high": self.rsi_ideal_high,
            "vol_ma_window": self.vol_ma_window,
            "vol_ma_mult": self.vol_ma_mult,
            "regime_window": self.regime_window,
            "regime_threshold": self.regime_threshold,
            "strict_need_macd_up": self.strict_need_macd_up,
            "loose_need_vol_surge": self.loose_need_vol_surge,
            "surge_relax_mult": self.surge_relax_mult,
            "downtrend_surge_bypass": self.downtrend_surge_bypass,
            "surge_bypass_mult": self.surge_bypass_mult,
            "use_trailing": self.use_trailing,
            "trail_basis": self.trail_basis,
            "trail_activate_pct": self.trail_activate_pct,
            "k_trail_atr": self.k_trail_atr,
            "trail_floor_pct": self.trail_floor_pct,
            "trail_drawdown_pct": self.trail_drawdown_pct,
            "trail_giveback_pct": self.trail_giveback_pct,
            "trail_dual": self.trail_dual,
            "trail_fib_use": self.trail_fib_use,
            "trail_fib_level": self.trail_fib_level,
            "time_stop_extend": self.time_stop_extend,
            "time_stop_band": self.time_stop_band,
            "time_stop_grace": self.time_stop_grace,
            "max_hold_bars_hard": self.max_hold_bars_hard,
            "obv_dead_min_bars": self.obv_dead_min_bars,
            "enable_macd_filter": self.enable_macd_filter,
            "enable_rsi_filter": self.enable_rsi_filter,
            "enable_bb_upper_filter": self.enable_bb_upper_filter,
            "enable_vol_avg_filter": self.enable_vol_avg_filter,
            "enable_regime_gate": self.enable_regime_gate,
            "macd_signal_mode": self.macd_signal_mode,
            "obv_signal_mode": self.obv_signal_mode,
            "ma20_signal_mode": self.ma20_signal_mode,
            "buy_order": self.buy_order,
        }
