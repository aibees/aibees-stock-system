from decimal import Decimal
from typing import Dict, Any


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


class UserCoinInfo:
    def __init__(self) -> None:
        self.division = ''
        self.group_id = -1
        self.coin_code = ''
        self.status = ''
        self.enabled_flag = 'Y'
        self.curr_balance = 0.0
        self.added_at = 0
        self.updated_at = 0

        self.datetime = ''
        self.open = 0.0
        self.high = 0.0
        self.low = 0.0
        self.close = 0.0
        self.volume = 0.0
        self.vol_surge_n = 0.0
        self.vol_avg = 0.0
        self.vol_low_th = 0.0
        self.vol_high_th = 0.0
        self.vol_ratio = 0.0
        self.last_close = 0.0

        self.ema20 = 0.0
        self.ema60 = 0.0
        self.ema120 = 0.0
        self.ema120_slope = 0.0

        # HMA (Hull Moving Average) — KospiStrategy2 추세 코어. from_dict 자동매핑.
        self.hma = 0.0
        self.hma_slope = 0.0

        # 체결강도(100=균형). live=KIS inquire-ccnl 값, backtest=OHLCV proxy 주입.
        self.chegyul_strength = 0.0

        # 추세국면 분류기 (최근 N봉 중 close<ema60 비율). from_dict 자동매핑.
        self.downtrend_ratio = 0.0

        self.bb_mid = 0.0
        self.bb_lower = 0.0
        self.bb_lower_chk = 0
        self.bb_upper = 0.0
        self.bb_upper_chk = 0
        self.bb_width = 0.0
        self.bb_width_avg = 0.0
        self.bb_mid_breakout = 0.0
        self.recent_high = 0.0

        self.macd = 0.0
        self.macd_s = 0.0
        self.macd_recent_min = 0.0
        self.macd_recent_max = 0.0
        self.macd_lower_mean = 0.0
        self.macd_upper_mean = 0.0
        self.macd_g_cross_n = ''
        self.macd_d_cross_n = ''

        self.fs_k = 0.0
        self.fs_d = 0.0

        self.roc = 0.0
        self.atr = 0.0
        self.atr_pct = 0.0
        self.obv = 0.0
        self.obv_signal = 0.0
        self.obv_cross = ''
        self.obv_ema_slow = 0.0
        self.obv_recent_min = 0.0
        self.obv_recent_max = 0.0
        self.obv_g_cross_n = ''
        self.obv_d_cross_n = ''

        self.rsi = 0.0
        self.rsi_signal = 0.0
        self.rsi_cross = ''

        self.score = 0.0

        self.score_trend = 0.0
        self.sign_trend = 0.0

        self.score_momentum = 0.0
        self.overheat_penalty = 0.0

        self.score_volatility = 0.0
        self.state_volatility = ''

        self.score_volume = 0.0

        self.regime = ''
        self.action = ''

        # for test
        self.watch_action = ''
        self.active_action = ''

        self.entry_gate = { }

    def to_dict(self) -> Dict[str, Any]:
        return {k: _to_plain(v) for k, v in self.__dict__.items()}


    @staticmethod
    def _coerce(default: Any, val: Any) -> Any:
        """default(= __init__ 기본값)의 타입에 맞춰 val 을 정규화한다.

        DB(trade_candle_data 등)에서 온 값은 SQLAlchemy DECIMAL 컬럼이라
        decimal.Decimal 로 넘어오고, 라이브 경로(pandas)는 float 로 넘어온다.
        이 둘이 전략 코드(kospi1/kospi3.py) 안에서 섞여 연산되면
        "unsupported operand type(s) for -: 'decimal.Decimal' and 'float'" 로
        터진다. 여기서 한 번에 float 로 통일해서 호출부 어디서든 안전하게 만든다.
        문자열 플래그(macd_g_cross_n 등)나 dict(entry_gate) 는 그대로 둔다.
        """
        if val is None:
            return default
        if isinstance(default, bool):
            return val
        if isinstance(default, (int, float)):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default
        return val

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserCoinInfo':
        """
        TradeCandleData.to_dict()의 결과(dict)를 받아
        UserCoinInfo 인스턴스를 생성하고 데이터를 매핑합니다.

        숫자 필드(open/close/macd/atr/rsi ... )는 원본이 Decimal 이든 float 든
        항상 float 로 정규화해서 저장한다(위 _coerce 참고). 문자열/플래그 필드는 그대로.
        """
        instance = cls()

        # 1. 필드명이 일치하는 항목들 자동 매핑 (+ 타입 정규화)
        # __init__에 정의된 self.__dict__의 키들을 기준으로 data에서 값을 가져옴
        for key, default in list(instance.__dict__.items()):
            if key in data:
                setattr(instance, key, cls._coerce(default, data[key]))

        # 2. 필드명이 다르거나 별도 처리가 필요한 항목들 수동 매핑
        # TradeCandleData의 'coin' -> UserCoinInfo의 'coin_code'
        if 'coin' in data:
            instance.coin_code = data['coin']

        # TradeCandleData의 'score_total' -> UserCoinInfo의 'score'
        if 'score_total' in data:
            instance.score = cls._coerce(instance.score, data.get('score_total', 0.0))

        # 3. 추가적인 기본값 설정이나 로직이 필요한 경우
        # 예: status나 enabled_flag 등은 DB 데이터에 없으므로 기본값 유지 혹은 별도 로직

        return instance