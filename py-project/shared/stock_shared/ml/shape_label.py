"""shape 모델 학습 라벨(net_edge_fwd) 정의 — **단일 출처**.

이 식이 여러 곳에 복제돼 있으면 한쪽만 고쳐져서 "학습 라벨과 평가 라벨이 다른"
상태가 된다(app/test/shape_full_universe_scan.py 의 compute_net_edge_fwd 가
원본이고, ShapeLabelJob / eval_shape_proba / 향후 학습 스크립트가 같은 걸 써야 한다).

타임프레임: 이 식 자체는 봉 단위와 무관하다(주봉/월봉에 그대로 쓴다).
forward 봉수만 LABEL_TIMEFRAME_SPEC 에서 골라 window 로 넘기면 된다.

라벨 정의(shape_model.py docstring 과 동일):
    base = 당일 종가
    향후 LABEL_FORWARD_BARS 거래일의
        gain = (기간 내 high 최대 - base) / base * 100
        loss = (base - 기간 내 low 최소) / base * 100
    net_edge_fwd = gain - loss        (단위: %p)
    "승리" = net_edge_fwd >= LABEL_WIN_THRESHOLD_PCT

주의: 향후 봉이 필요하므로 **엠바고 LABEL_FORWARD_BARS 봉**이 있다. 당일 피처는
LABEL_FORWARD_BARS 거래일 뒤에야 라벨링 가능하다 — 이걸 무시하면 look-ahead 누수.

numpy 만 쓴다(pandas/sklearn 의존성 없음).
"""
from __future__ import annotations

import numpy as np

# 라벨 산출에 쓰는 향후 거래일 수. 바꾸면 기존 라벨 전체 재계산 필요(재검증도).
LABEL_FORWARD_BARS = 5

# 학습 타깃 이진화 임계값(%p). shape_model.score() 가 내는 확률의 정의.
LABEL_WIN_THRESHOLD_PCT = 15.0

# 라벨 계산 시 허용하는 최대 캘린더 경과일.
#   적재(StockBuyCheckJob)가 며칠 빠지면 "다음 5개 저장봉"이 실제 5거래일이 아니라
#   훨씬 먼 미래가 된다. 그 경우 라벨이 조용히 틀려지므로 아예 건너뛴다.
#   5거래일 = 보통 7캘린더일, 연휴를 넉넉히 감안해 15일.
LABEL_MAX_SPAN_DAYS = 15


# ============================================================================
# 타임프레임별 라벨 지평 (일/주/월 shape_proba 앙상블용)
#
# 왜 forward 봉수가 타임프레임마다 다른가
#   일봉 모델은 forward 5봉 = 5거래일이다. 주봉/월봉에 같은 5봉을 쓰면 각각
#   5주 / 5개월 예측이 되어, 실제 보유기간(s1_max_hold_bars≈30거래일)과 어긋난다.
#   앙상블로 합산하려면 세 모델이 '비슷한 미래'를 봐야 하므로 지평을 맞춘다:
#
#     D: forward 5봉  = 5거래일
#     W: forward 1봉  = 1주   = 5거래일    ← 일봉과 사실상 동일 지평
#     M: forward 1봉  = 1개월 ≈ 21거래일   ← 보유기간 상한에 근접
#
#   주봉 1봉의 high/low 는 그 주 5거래일의 high/low 와 같으므로, 주봉 라벨은
#   일봉 5봉 라벨과 거의 같은 타깃이 된다 — 같은 타깃을 다른 피처 시각(14주 구조)
#   으로 예측하는 구조라 앙상블 다양성 확보에 이상적이다.
#
# max_span_days 는 "봉 사이가 이보다 벌어지면 적재 누락으로 보고 건너뛴다" 가드다.
#   주봉 1봉=7일, 월봉 1봉≈31일이라 일봉 기준 15일을 그대로 쓰면 전부 버려진다.
# ============================================================================
LABEL_TIMEFRAME_SPEC = {
    "D": {"forward_bars": 5, "max_span_days": 15},
    "W": {"forward_bars": 1, "max_span_days": 14},
    "M": {"forward_bars": 1, "max_span_days": 45},
}


def timeframe_spec(period: str) -> dict:
    """타임프레임별 라벨 파라미터. 미지원 period 는 ValueError."""
    try:
        return LABEL_TIMEFRAME_SPEC[period]
    except KeyError:
        raise ValueError(f"지원하지 않는 period: {period!r} (D/W/M 만 가능)") from None


def compute_net_edge_fwd(close, high, low, window: int = LABEL_FORWARD_BARS) -> np.ndarray:
    """종목 하나의 시계열(오름차순)에 대해 net_edge_fwd 배열을 반환한다.

    입력은 같은 길이의 close/high/low(array-like). 향후 window 봉이 없는 뒤쪽
    인덱스와 base<=0 인 봉은 NaN 으로 남는다.
    """
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(close)
    out = np.full(n, np.nan)

    for i in range(n - window):
        base = close[i]
        if not np.isfinite(base) or base <= 0:
            continue
        fwd_high = high[i + 1:i + 1 + window]
        fwd_low = low[i + 1:i + 1 + window]
        if len(fwd_high) < window:
            continue
        if not (np.isfinite(fwd_high).all() and np.isfinite(fwd_low).all()):
            continue
        gain_pct = (fwd_high.max() - base) / base * 100
        loss_pct = (base - fwd_low.min()) / base * 100
        out[i] = gain_pct - loss_pct

    return out


def is_label_win(net_edge_fwd) -> bool | None:
    """라벨 이진화. None/NaN 이면 판단 불가(None)."""
    if net_edge_fwd is None:
        return None
    v = float(net_edge_fwd)
    if not np.isfinite(v):
        return None
    return v >= LABEL_WIN_THRESHOLD_PCT
