"""
14봉 정규화 가격패턴(shape) 피처.

배경(2026-09 세션 리서치): 매수추천 당일 하루치 스냅샷 지표(rsi/macd 등)만으로는
승패 예측력이 fold 마다 뒤집혀 못 믿을 수준이었다. 대신 "당일부터 -14봉 전까지의
가격 흐름을 시작가 기준으로 정규화한 경로"로 피처를 바꾸니 walk-forward 두 구간
모두에서 상위 5% 스코어가 기준선 대비 1.75~1.9배 적중률을 보였다(재현 확인됨).

반대로, 이 피처들로 "손실 회피"까지 일반화하려는 시도는 실패했다 — 정규화 모델은
상단 잠재력엔 강하지만 하방 예측엔 약하고, 오히려 변동성 큰(=손절도 잦은) 종목을
더 잘 찾아낸다. 그래서 실전에는 예측모델을 있는 그대로 쓰지 않고, 이 리서치에서
가장 재현성 높게 나온 실패 패턴 하나만 하드 게이트(exhaustion)로 승격했다:
"14봉 내내 눌림 없이 이미 크게 올랐고, 오늘도 또 크게 오른" 종목은 다음날 급반전
확률이 눈에 띄게 높았다(사례: 유티아이 2026-09-01, 다음날 -25%).

이 모듈은 numpy/pandas 만 쓴다(scikit-learn 의존성 없음) — exhaustion 게이트는
모델 없이도 항상 동작해야 하기 때문이다. 모델 추론(shape_proba)은 shape_model.py 참고.

2026-09 세션 후속 리서치: shape_* 9종만으로는 "당일 상승분 중 어떤 패턴이 다음날도
이어지는지" 를 구분하는 힘이 부족했다(k-means 로 PC1=크기 축을 제거해도 남는 3개
아키타입 확인). rsi/macd/거래량 같은 전통 지표를 모델 입력에 "그대로" 추가했더니
walk-forward top5%/top10% 구간에서 일관된 개선이 나왔다(재현 확인, 두 fold 모두).
당시엔 OBV 파생(obv_gap_norm)이 기여도가 거의 없어 제외했었다.

2026-09 세션 재차 후속 리서치(편향 없는 전종목 스캔 이후): 실제 상한가(≥29%) 741건을
전종목/대조군으로 비교해보니 OBV 매집 신호(obv_gap_norm/obv_slope3)가 재현성 있게
유의미했다(p<0.001). shape9+ind3 모델에 OBV 파생 2종을 다시 추가해 top10 후보를
추린 뒤, 같은 계열 지표(OBV/MACD/RSI/거래량)로 재정렬하는 2단계 방식이 여러 학습
cutoff에서 일관되게 단독 top1 픽보다 우수했다(승률 +5~9%p). 이번엔 채택한다.
이 2개도 ind_* 와 마찬가지로 lookback 이 obv/obv_signal/vol_avg 롤링 계산에만 있고
(compute_indicator_df/enrich_rows 가 이미 obv/obv_signal/vol_avg 를 채워둔 뒤 호출된다는
전제), for-loop 없이 벡터 연산으로 채운다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 컬럼명은 문자열 리터럴을 직접 쓴다(py-stock-batch 의 app.common.constants.Literal 은
# 이 공용 패키지가 의존할 수 없는 상위 프로젝트 모듈이라 가져올 수 없다).
# 값 자체는 Literal.CLOSE='close', Literal.VOLUME='volume' 과 동일하다.
COL_CLOSE = "close"
COL_VOLUME = "volume"

# rsi/macd/macd_s/vol_avg 는 compute_shape_features 호출 전에 이미 채워져 있다고 가정
# (KisStockService.compute_indicator_df, KisBacktester.enrich_rows 둘 다 순서 보장).
COL_RSI = "rsi"
COL_MACD = "macd"
COL_MACD_S = "macd_s"
COL_VOL_AVG = "vol_avg"
COL_OBV = "obv"
COL_OBV_SIGNAL = "obv_signal"

WINDOW = 14  # 정규화 lookback 봉수. 리서치에서 검증된 고정값 — 바꾸면 재검증 필요.

# 소진(exhaustion) 게이트 임계값. 전부 동시에 만족해야 발동한다.
#   - bars_since_min : 14(=WINDOW)면 "창 전체에서 가장 낮은 값이 시작일"=한 번도 안 눌림.
#   - total_ret_14   : 14봉간 이미 +25% 이상 올랐음.
#   - ret_1d_today   : 오늘 하루만 +10% 이상(당일도 급등 중).
#   근거: 2026-09-01 유티아이 사례(총 +36.6%, bars_since_min=14, 당일 +17.1%) → 익일 -25.3%.
EXHAUSTION_BARS_SINCE_MIN_MIN = WINDOW - 1     # 13 이상(사실상 눌림 없음)
EXHAUSTION_TOTAL_RET_14_MIN = 0.25             # +25%p 이상
EXHAUSTION_RET_1D_TODAY_MIN = 0.10             # 당일 +10%p 이상

# 2026-09 세션 후속 리서치로 추가된 전통 지표 파생 피처(당일 스냅샷, lookback 불필요).
IND_FEATURE_COLUMNS = [
    "ind_rsi14",
    "ind_macd_hist_norm",
    "ind_vol_ratio_today",
]

# OBV 매집 신호 파생(상한가 741건 대조군 분석으로 재검증, p<0.001). 당일 스냅샷값.
OBV_FEATURE_COLUMNS = [
    "obv_gap_norm",
    "obv_slope3",
]

SHAPE_FEATURE_COLUMNS = [
    "shape_total_ret_14",
    "shape_min_ret_14",
    "shape_bars_since_min",
    "shape_recovery_from_min",
    "shape_early_ret_9",
    "shape_late_ret_5",
    "shape_down_ratio_14",
    "shape_path_std_14",
    "shape_vol_trend",
] + IND_FEATURE_COLUMNS + OBV_FEATURE_COLUMNS


def compute_shape_features(data: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    """data(datetime 오름차순 OHLCV DataFrame)에 shape_* 컬럼을 추가해 반환(in-place).

    최근 window 봉의 lookback 이 없는 앞부분 행은 NaN 으로 남는다(호출부가 fillna 처리).
    compute_indicator_df() 와 같은 스레드/프로세스에서 반복 호출되는 걸 감안해
    벡터 연산 대신 단순 for-loop 를 쓴다(종목 1개 = 수백 행 수준이라 성능상 문제 없음).
    """
    n = len(data)
    closes = data[COL_CLOSE].astype(float).values
    volumes = data[COL_VOLUME].astype(float).values

    total_ret = np.full(n, np.nan)
    min_ret = np.full(n, np.nan)
    bars_since_min = np.full(n, np.nan)
    recovery_from_min = np.full(n, np.nan)
    early_ret = np.full(n, np.nan)
    late_ret = np.full(n, np.nan)
    down_ratio = np.full(n, np.nan)
    path_std = np.full(n, np.nan)
    vol_trend = np.full(n, np.nan)
    ret_1d_today = np.full(n, np.nan)

    for i in range(window, n):
        base = closes[i - window]
        if base <= 0 or np.isnan(base):
            continue
        w = closes[i - window:i + 1]
        if np.any(np.isnan(w)) or np.any(w <= 0):
            continue

        path = (w - base) / base
        t_ret = path[-1]
        m_ret = path[1:].min()
        m_idx = int(np.argmin(path))       # index 0(=시작일, path=0)도 후보 → 창 전체 미하락 시 0
        bsm = window - m_idx
        rec = path[-1] - m_ret
        e_ret = path[window - 5]
        l_ret = path[-1] - path[window - 5]

        daily = np.diff(w) / w[:-1]
        d_ratio = float((daily < 0).mean())
        p_std = float(daily.std())
        r1d = float(daily[-1])

        vw = volumes[i - window:i + 1]
        early_v = vw[:window - 5].mean()
        late_v = vw[window - 5:].mean()
        v_trend = (late_v / early_v) if early_v > 0 else np.nan

        total_ret[i] = t_ret
        min_ret[i] = m_ret
        bars_since_min[i] = bsm
        recovery_from_min[i] = rec
        early_ret[i] = e_ret
        late_ret[i] = l_ret
        down_ratio[i] = d_ratio
        path_std[i] = p_std
        vol_trend[i] = v_trend
        ret_1d_today[i] = r1d

    data["shape_total_ret_14"] = total_ret
    data["shape_min_ret_14"] = min_ret
    data["shape_bars_since_min"] = bars_since_min
    data["shape_recovery_from_min"] = recovery_from_min
    data["shape_early_ret_9"] = early_ret
    data["shape_late_ret_5"] = late_ret
    data["shape_down_ratio_14"] = down_ratio
    data["shape_path_std_14"] = path_std
    data["shape_vol_trend"] = vol_trend
    data["shape_ret_1d_today"] = ret_1d_today

    # ── ind_* (전통 지표 파생, 당일 스냅샷) ────────────────────────────
    # 호출부가 rsi/macd/macd_s/vol_avg 컬럼을 미리 채워두지 않은 경우(예: 다른
    # 프로젝트의 임시 스크립트)를 대비해 컬럼 부재 시 NaN 으로 안전 처리한다.
    if COL_RSI in data.columns:
        data["ind_rsi14"] = data[COL_RSI].astype(float)
    else:
        data["ind_rsi14"] = np.nan

    if COL_MACD in data.columns and COL_MACD_S in data.columns:
        macd = data[COL_MACD].astype(float)
        macd_s = data[COL_MACD_S].astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            data["ind_macd_hist_norm"] = (macd - macd_s) / closes
    else:
        data["ind_macd_hist_norm"] = np.nan

    if COL_VOL_AVG in data.columns:
        vol_avg = data[COL_VOL_AVG].astype(float)
        data["ind_vol_ratio_today"] = volumes / (vol_avg + 1e-9)
    else:
        data["ind_vol_ratio_today"] = np.nan

    # ── obv_* (매집 신호, 당일 스냅샷) ─────────────────────────────────
    if COL_OBV in data.columns and COL_OBV_SIGNAL in data.columns and COL_VOL_AVG in data.columns:
        obv = data[COL_OBV].astype(float)
        obv_signal = data[COL_OBV_SIGNAL].astype(float)
        vol_avg = data[COL_VOL_AVG].astype(float)
        data["obv_gap_norm"] = (obv - obv_signal) / (vol_avg + 1e-9)
        data["obv_slope3"] = (obv - obv.shift(3)) / (vol_avg * 3 + 1e-9)
    else:
        data["obv_gap_norm"] = np.nan
        data["obv_slope3"] = np.nan

    return data


def is_exhaustion_risk(
    bars_since_min,
    total_ret_14,
    ret_1d_today,
) -> bool:
    """소진(과열 연장) 패턴 하드 게이트. 셋 다 동시에 만족해야 True.

    입력값이 None/NaN 이면 판단 불가로 보고 False(=차단 안 함) — 신규 상장 등
    lookback 부족 구간에서 매수 자체를 막아버리지 않기 위함.
    """
    for v in (bars_since_min, total_ret_14, ret_1d_today):
        if v is None:
            return False
        try:
            if pd.isna(v):
                return False
        except TypeError:
            return False

    return (
        bars_since_min >= EXHAUSTION_BARS_SINCE_MIN_MIN
        and total_ret_14 >= EXHAUSTION_TOTAL_RET_14_MIN
        and ret_1d_today >= EXHAUSTION_RET_1D_TODAY_MIN
    )
