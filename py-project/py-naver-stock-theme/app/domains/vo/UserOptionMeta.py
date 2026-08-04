from __future__ import annotations
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.domains.vo.UserCoinInfo import UserCoinInfo


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

    def to_dict(self) -> Dict[str, Any]:
        return {k: _to_plain(v) for k, v in self.__dict__.items()}
