"""shape 모델 학습 라벨(net_edge_fwd) 정의 — **단일 출처**.

이 식이 여러 곳에 복제돼 있으면 한쪽만 고쳐져서 "학습 라벨과 평가 라벨이 다른"
상태가 된다(app/test/shape_full_universe_scan.py 의 compute_net_edge_fwd 가
원본이고, ShapeLabelJob / eval_shape_proba / 향후 학습 스크립트가 같은 걸 써야 한다).

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
