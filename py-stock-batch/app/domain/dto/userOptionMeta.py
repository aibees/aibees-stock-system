from __future__ import annotations
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from app.domain.dto.userCoinInfo import UserCoinInfo


def _to_plain(obj: Any) -> Any:
    """
    객체를 JSON 직렬화-friendly 한 형태(dict/list/primitive)로 변환합니다.
    - to_dict()가 있으면 사용
    - __dict__가 있으면 dict로 변환
    - list/tuple/set은 list로 변환 후 재귀
    - dict는 value를 재귀
    - 그 외는 그대로 반환 (json.dumps에서 실패하면 default=str 등으로 처리)
    """
    if obj is None:
        return None

    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(v) for v in obj]

    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in obj.__dict__.items()}

    return obj


class UserOptionMeta:
    def __init__(self) -> None:
        self.email = ''
        self.user_name = ''
        self.user_id = ''
        self.access_key = ''
        self.secret_key = ''

        # 메신저 설정
        self.tele_bot_id          = ''
        self.tele_chat_id         = ''
        self.stock_sell_mail_flag = 'N'
        self.stock_sell_tele_flag = 'N'

        self.krw_balance = 0.0
        self.coin_amount = 0.0
        self.has_position = False
        self.avg_price = 0.0

        self.coin_list: Optional[List[UserCoinInfo]] = None

        self.time_frame = ''

        self.delay_date = 3 # 몇 일 전 데이터까지 검토해볼지
        self.cooldown_bars = 0
        self.regime_bull_only_flag = True
        self.adx_threshold = 0.0
        self.bb_width_threshold = 0.0
        self.breakout_n = 0

        self.macd_recent_day = 0
        self.bb_over_recent_day = 0
        self.vol_limit = 0
        self.vol_surge = 3.0

        self.thresholds_buy_entry = 0.0
        self.thresholds_buy_confirm = 0.0
        self.thresholds_sell_entry = 0.0
        self.thresholds_sell_confirm = 0.0

        self.ratio_trend = 0.0
        self.ratio_momentum = 0.0
        self.ratio_volatility = 0.0
        self.ratio_volume = 0.0

        # volume memory
        self.max_volume = 0.0
        self.max_volume_open = 0.0
        self.max_volume_close = 0.0

        # 포지션 상태 (매도 판별용 — 진입 시 세팅, 보유 중 매 봉 갱신)
        self.entry_price = 0.0   # 진입 평균단가
        self.entry_atr = 0.0     # 진입 시점 ATR (초기 손절/목표 고정용)
        self.peak_high = 0.0     # 진입 이후 장중 최고가 (트레일링 기준)
        self.peak_close = 0.0    # 진입 이후 종가 최고가 (꼬리 노이즈에 둔감한 트레일링 기준)
        self.bars_since_peak = 0 # 신고가(peak_high) 갱신 후 경과 봉수 (#4 동적 타임스탑용)
        self.bars_held = 0       # 보유 봉수

        self.upper_check_history = False

        # ── KospiStrategy1 파라미터 (None이면 전략 클래스 기본값 사용) ────────
        self.s1_stop_loss_pct         = None
        self.s1_take_profit_pct       = None
        self.s1_max_hold_bars         = None
        self.s1_rsi_overbought        = None
        self.s1_rsi_ideal_low         = None
        self.s1_rsi_ideal_high        = None
        self.s1_vol_ma_window         = None
        self.s1_vol_ma_mult           = None
        self.s1_regime_window         = None
        self.s1_regime_threshold      = None
        self.s1_strict_need_macd_up   = None
        self.s1_loose_need_vol_surge  = None
        self.s1_surge_relax_mult      = None
        self.s1_downtrend_surge_bypass = None
        self.s1_surge_bypass_mult     = None
        self.s1_use_trailing          = None
        self.s1_trail_basis           = None
        self.s1_trail_activate_pct    = None
        self.s1_k_trail_atr           = None
        self.s1_trail_floor_pct       = None
        self.s1_time_stop_extend      = None
        self.s1_time_stop_band        = None
        self.s1_time_stop_grace       = None
        self.s1_max_hold_bars_hard    = None
        self.s1_obv_dead_min_bars     = None

        # ── KospiStrategy1 매수 필터 on/off 스위치 (None이면 기본값 True 사용) ──
        self.s1_enable_macd_filter      = None
        self.s1_enable_rsi_filter       = None
        self.s1_enable_bb_upper_filter  = None
        self.s1_enable_vol_avg_filter   = None
        self.s1_enable_regime_gate      = None

        # ── core 진입 신호 mode (None이면 기본값 'golden' 사용) ──
        # 'off'(사용안함) / 'golden'(골든크로스 여부) / 'slope'(기울기 상승여부)
        self.s1_macd_signal_mode        = None
        self.s1_obv_signal_mode         = None

        # ── KospiStrategy2 파라미터 (None이면 전략 클래스 기본값 사용) ────────
        # HMA + MACD + OBV core AND + 체결강도 필터 전략
        self.s2_stop_loss_pct          = None
        self.s2_take_profit_pct        = None
        self.s2_max_hold_bars          = None
        self.s2_max_hold_bars_hard     = None
        self.s2_hma_period             = None   # HMA 기간 (기본 20)
        self.s2_hma_signal_mode        = None   # 'off'|'slope'|'above'
        self.s2_macd_signal_mode       = None   # 'off'|'golden'|'slope'
        self.s2_obv_signal_mode        = None   # 'off'|'golden'|'slope'
        # 컨펌 층: 거래량 실린 양봉 + 종가 상단 마감
        self.s2_confirm_body_up        = None   # 양봉 요구
        self.s2_confirm_vol_mult       = None   # 거래량 >= 평균 * 배수 (기본 1.0)
        self.s2_confirm_clv_min        = None   # 종가 상단마감 CLV 하한 (기본 0.6)
        self.s2_chegyul_threshold      = None   # 체결강도 하한 (기본 110)
        # 적응형 추세국면 게이트
        self.s2_regime_window          = None   # 분류기 봉 길이 (기본 90)
        self.s2_regime_threshold       = None   # 하락국면 임계 (기본 0.70)
        self.s2_regime_strict_need_macd = None  # 하락국면 통과에 macd>=signal 요구
        self.s2_rsi_overbought         = None
        self.s2_vol_ma_mult            = None
        self.s2_use_trailing           = None
        self.s2_trail_activate_pct     = None
        self.s2_k_trail_atr            = None
        self.s2_trail_floor_pct        = None
        self.s2_obv_dead_min_bars      = None
        # 매수 필터 on/off 스위치
        self.s2_enable_hma_filter      = None
        self.s2_enable_macd_filter     = None
        self.s2_enable_obv_filter      = None
        self.s2_enable_confirm_candle  = None
        self.s2_enable_chegyul_filter  = None
        self.s2_enable_regime_gate     = None
        self.s2_enable_rsi_filter      = None
        self.s2_enable_bb_upper_filter = None
        self.s2_enable_vol_avg_filter  = None
        # 매도: HMA 청산 사용 여부 + 방식('break'|'inflection'|'off')
        self.s2_use_hma_exit           = None
        self.s2_hma_exit_mode          = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: _to_plain(v) for k, v in self.__dict__.items()}
