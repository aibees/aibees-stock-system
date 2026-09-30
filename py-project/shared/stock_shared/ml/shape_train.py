"""shape_proba 모델 재학습 + 승격 게이트 — **순수 로직 단일 출처**.

이 모듈은 DB/KIS/배치에 의존하지 않는다(입력은 dict 리스트, 출력은 모델+지표 dict).
ShapeTrainJob 이 얇은 껍데기로 감싸고, 오프라인 실험은 같은 함수를 직접 호출한다.
그래야 "배치가 학습한 모델"과 "손으로 검증한 모델"이 갈리지 않는다.

────────────────────────────────────────────────────────────────────────────
왜 게이트가 이 파일의 핵심인가
────────────────────────────────────────────────────────────────────────────
sql/17_shape_train_job_register.sql 이 학습 배치를 일부러 빼둔 이유가 그대로 유효하다:
승격 판정 없이 자동 재학습을 켜면 **성능이 떨어진 모델이 조용히 라이브로 간다**.
자동 승격을 쓰기로 했으므로(2026-10-01) 게이트가 유일한 방어선이다.

게이트가 막아야 하는 실패 4종:
  1) 데이터 부족      — 적재 초기엔 몇 백 행뿐이라 어떤 지표도 신뢰할 수 없다.
  2) 라벨 붕괴        — 양성률이 0 이나 1 에 가까우면 AUC 가 무의미하다.
  3) 우연한 개선      — holdout 이 좁으면 AUC 가 노이즈로 흔들린다. 절대하한 + 상대개선
                        **둘 다** 요구하고, 상대개선에는 최소 마진을 둔다.
  4) 경계 라벨 누수   — train 마지막 날의 라벨은 향후 5봉(=holdout 구간)을 본다.
                        엠바고 없이 자르면 holdout 성능이 실제보다 좋게 나온다.

────────────────────────────────────────────────────────────────────────────
현행(라이브) 모델 비교의 한계 — 알고 쓸 것
────────────────────────────────────────────────────────────────────────────
라이브 shape_gbm_v1.joblib 은 2026-09 세션에 trade_shape_scan_stock(2026-06~09)로
ad-hoc 학습된 산출물이다. 즉 **holdout 기간을 이미 학습에 봤을 가능성**이 있고,
그 경우 라이브 쪽 holdout 지표는 낙관적으로 편향된다 → 게이트가 과도하게 보수적이
된다(승격이 안 됨). 이건 "조용히 나빠지는" 실패보다 안전한 방향이므로 그대로 둔다.
대신 절대하한(ABS_*)만으로도 승격되는 경로는 **라이브 모델을 못 채점할 때만** 열어둔다.
데이터가 충분히 쌓여 라이브 모델이 확실히 구식이 되면(학습셋 시작일이 라이브 학습
시점 이후) 이 편향은 자연히 사라진다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
from stock_shared.ml.shape_label import LABEL_MAX_SPAN_DAYS, LABEL_WIN_THRESHOLD_PCT

log = logging.getLogger("stock_shared.ml.shape_train")

# ── 하이퍼파라미터 ────────────────────────────────────────────────────────────
#   라이브 shape_gbm_v1.joblib 과 **동일**하게 고정한다. 재학습의 변수는 데이터뿐이어야
#   한다 — 데이터와 하이퍼파라미터를 같이 바꾸면 성능 변화의 원인을 못 가린다.
#   (아티팩트 실측: HistGradientBoostingClassifier(l2_regularization=1.0,
#    learning_rate=0.05, max_depth=4, max_iter=200, random_state=42))
MODEL_PARAMS = {
    "learning_rate": 0.05,
    "max_depth": 4,
    "max_iter": 200,
    "l2_regularization": 1.0,
    "random_state": 42,
}

# ── 분할 ─────────────────────────────────────────────────────────────────────
# holdout 은 **가장 최근 구간**을 캘린더 일수로 떼낸다(랜덤 분할은 시계열에서 누수).
HOLDOUT_DAYS = 30
# train 과 holdout 사이 엠바고. 라벨이 향후 5봉을 보므로 그만큼 비워야 경계 누수가 없다.
# LABEL_MAX_SPAN_DAYS(15일)를 쓰면 라벨 계산이 허용하는 최대 창까지 안전하게 덮는다.
EMBARGO_DAYS = LABEL_MAX_SPAN_DAYS

# ── 게이트 임계값 ────────────────────────────────────────────────────────────
MIN_TRAIN_ROWS = 20000        # 전종목 2,700개 × 약 8거래일치. 이보다 적으면 판정 보류.
MIN_HOLDOUT_ROWS = 3000
MIN_TRAIN_DAYS = 20           # 거래일 수. 행수만 보면 한 날짜에 몰려도 통과해버린다.
MIN_HOLDOUT_DAYS = 5
MIN_POS_RATE = 0.02           # 양성률 하한/상한. 벗어나면 라벨이 무너진 것으로 본다.
MAX_POS_RATE = 0.60

ABS_AUC_MIN = 0.55            # 절대하한. 동전던지기보다 의미있게 나아야 한다.
ABS_LIFT_MIN = 1.30           # top-k 정밀도가 기준선(양성률)의 1.3배 이상.
MIN_AUC_GAIN = 0.005          # 라이브 대비 최소 AUC 개선폭(노이즈 마진).
PREC_REGRESSION_TOL = 0.01    # top-k 정밀도는 이 폭 이상 나빠지면 안 된다.

# 운영이 실제로 쓰는 개수 — StockBuyCheckJob._compute_composite_top10 의 top10.
# "그날 상위 k개를 집었을 때의 적중률"이 AUC 보다 운영 손익에 가깝다.
PREC_AT_K = 10


@dataclass
class Dataset:
    """학습에 바로 넣을 수 있는 형태. X 는 NaN 없음(완전행만 남김)."""

    X: np.ndarray
    y: np.ndarray
    dates: np.ndarray           # 각 행의 일봉 날짜(YYYY-MM-DD)
    coins: np.ndarray
    dropped_incomplete: int = 0  # 피처 결측으로 버린 행수
    dropped_unlabeled: int = 0   # 라벨 미확정으로 버린 행수


@dataclass
class Metrics:
    n: int = 0
    pos_rate: float = float("nan")
    auc: float = float("nan")
    prec_at_k: float = float("nan")   # 날짜별 top-k 평균 정밀도
    lift_at_k: float = float("nan")   # prec_at_k / pos_rate
    n_days: int = 0

    def to_dict(self) -> dict:
        return {
            "n": self.n, "pos_rate": _r(self.pos_rate), "auc": _r(self.auc),
            "prec_at_k": _r(self.prec_at_k), "lift_at_k": _r(self.lift_at_k),
            "n_days": self.n_days,
        }


@dataclass
class GateResult:
    promote: bool
    reasons: list[str] = field(default_factory=list)   # 판정 근거(통과/탈락 모두)

    @property
    def reason_text(self) -> str:
        return " / ".join(self.reasons)


def round_or_none(v, nd: int = 4):
    """NaN/inf 를 None 으로 바꿔 DB/JSON 에 넣을 수 있게 한다.

    지표는 NaN 이 정상적으로 나온다(한 클래스뿐인 holdout, 라이브 채점불가 등).
    그걸 DECIMAL 컬럼에 그대로 넣으면 INSERT 가 터지므로 여기서 한 번에 막는다.
    """
    if v is None:
        return None
    v = float(v)
    return None if not np.isfinite(v) else round(v, nd)


_r = round_or_none   # 모듈 내부 표기 축약


# ============================================================================
# 데이터셋
# ============================================================================
def build_dataset(rows: list[dict]) -> Dataset:
    """trade_shape_train_daily 행 리스트 → Dataset.

    **완전행만 학습에 쓴다.** HistGBM 은 NaN 을 네이티브 처리할 수 있지만,
    추론부 shape_model.score() 가 "피처 하나라도 None/NaN 이면 None 반환"이므로
    결측행은 라이브에서 애초에 점수가 안 나간다. 학습에만 넣으면 학습분포와
    추론분포가 어긋난다 — 그래서 여기서도 같은 규칙으로 버린다.
    (적재를 raw NULL 로 하는 이유는 여전히 유효하다: 0 으로 채워 쌓으면 이 판정
     자체가 불가능해지고 "결측"이 "관측값 0"으로 학습된다.)
    """
    X, y, dates, coins = [], [], [], []
    dropped_incomplete = 0
    dropped_unlabeled = 0

    for r in rows:
        label = r.get("net_edge_fwd")
        if label is None:
            dropped_unlabeled += 1
            continue
        vals = []
        ok = True
        for c in SHAPE_FEATURE_COLUMNS:
            v = r.get(c)
            if v is None:
                ok = False
                break
            v = float(v)
            if not np.isfinite(v):
                ok = False
                break
            vals.append(v)
        if not ok:
            dropped_incomplete += 1
            continue
        lv = float(label)
        if not np.isfinite(lv):
            dropped_unlabeled += 1
            continue
        X.append(vals)
        y.append(1 if lv >= LABEL_WIN_THRESHOLD_PCT else 0)
        dates.append(str(r["datetime"]))
        coins.append(str(r["coin"]))

    return Dataset(
        X=np.asarray(X, dtype=float).reshape(-1, len(SHAPE_FEATURE_COLUMNS)),
        y=np.asarray(y, dtype=int),
        dates=np.asarray(dates, dtype=object),
        coins=np.asarray(coins, dtype=object),
        dropped_incomplete=dropped_incomplete,
        dropped_unlabeled=dropped_unlabeled,
    )


def time_split(ds: Dataset, holdout_days: int = HOLDOUT_DAYS,
               embargo_days: int = EMBARGO_DAYS) -> tuple[np.ndarray, np.ndarray, dict]:
    """시간순 분할. 반환: (train_idx, holdout_idx, 경계정보).

    holdout = 마지막 관측일로부터 holdout_days 캘린더일.
    train   = holdout 시작일보다 embargo_days 이상 **이전**인 행만.
              (그 사이 구간은 라벨이 holdout 을 들여다보므로 양쪽에서 버린다)
    """
    from datetime import datetime, timedelta

    if len(ds.y) == 0:
        return np.array([], dtype=int), np.array([], dtype=int), {}

    def _d(s):
        return datetime.strptime(s, "%Y-%m-%d")

    uniq = sorted(set(ds.dates))
    last = _d(uniq[-1])
    holdout_start = last - timedelta(days=holdout_days - 1)
    train_end = holdout_start - timedelta(days=embargo_days)

    dt = np.array([_d(s) for s in ds.dates], dtype=object)
    holdout_idx = np.where(dt >= holdout_start)[0]
    train_idx = np.where(dt < train_end)[0]

    info = {
        "train_end": train_end.strftime("%Y-%m-%d"),
        "holdout_start": holdout_start.strftime("%Y-%m-%d"),
        "holdout_end": last.strftime("%Y-%m-%d"),
        "embargo_days": embargo_days,
        "embargo_dropped": int(len(ds.y) - len(train_idx) - len(holdout_idx)),
    }
    return train_idx, holdout_idx, info


# ============================================================================
# 학습 / 평가
# ============================================================================
def train_model(X: np.ndarray, y: np.ndarray):
    """HistGradientBoostingClassifier 학습. sklearn 미설치면 ImportError 그대로 올린다
    (학습 배치는 sklearn 이 **필수**다 — 추론부처럼 조용히 degrade 하면 안 된다)."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    model = HistGradientBoostingClassifier(**MODEL_PARAMS)
    model.fit(X, y)
    return model


def _predict_proba(model, X: np.ndarray) -> np.ndarray | None:
    """모델이 이 피처셋과 호환되지 않으면 None(게이트가 '라이브 채점불가'로 처리)."""
    try:
        n_in = getattr(model, "n_features_in_", None)
        if n_in is not None and int(n_in) != X.shape[1]:
            log.warning("[shape_train] 모델 피처수 불일치: %s != %s", n_in, X.shape[1])
            return None
        return model.predict_proba(X)[:, 1]
    except Exception as e:  # noqa: BLE001
        log.warning("[shape_train] 채점 실패: %s", e)
        return None


def _roc_auc(y: np.ndarray, p: np.ndarray) -> float:
    """sklearn 없이도 계산 가능한 rank 기반 AUC(동점은 평균순위). 한 클래스뿐이면 NaN."""
    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(len(p), dtype=float)
    sp = p[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0     # 1-based 평균순위
        i = j + 1
    return (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _precision_at_k(y: np.ndarray, p: np.ndarray, dates: np.ndarray,
                    k: int = PREC_AT_K) -> tuple[float, int]:
    """날짜별로 proba 상위 k개를 집었을 때의 평균 정밀도. 반환: (정밀도, 날짜수).

    운영(StockBuyCheckJob)이 "그날 pool 에서 top10"을 고르므로 이 지표가 AUC 보다
    손익에 가깝다. 후보가 k개 미만인 날은 있는 만큼만 센다.
    """
    hits = 0
    picks = 0
    days = 0
    for d in np.unique(dates):
        m = dates == d
        if not m.any():
            continue
        pd_, yd = p[m], y[m]
        kk = min(k, len(pd_))
        top = np.argsort(-pd_, kind="mergesort")[:kk]
        hits += int(yd[top].sum())
        picks += kk
        days += 1
    if picks == 0:
        return float("nan"), 0
    return hits / picks, days


def evaluate(model, ds: Dataset, idx: np.ndarray, k: int = PREC_AT_K) -> Metrics:
    """주어진 인덱스 구간에서 모델 지표 산출. 채점 불가면 n/pos_rate 만 채워 반환."""
    m = Metrics()
    if len(idx) == 0:
        return m
    y = ds.y[idx]
    m.n = int(len(idx))
    m.pos_rate = float(y.mean())
    # 거래일수는 모델과 무관한 데이터 속성이다 — 채점 실패해도 게이트가 쓸 수 있게
    # 항상 채운다(게이트의 데이터 충분성 검사가 이 값에 의존한다).
    m.n_days = int(len(np.unique(ds.dates[idx])))

    p = _predict_proba(model, ds.X[idx]) if model is not None else None
    if p is None:
        return m

    m.auc = _roc_auc(y, p)
    m.prec_at_k, _ = _precision_at_k(y, p, ds.dates[idx], k)
    if np.isfinite(m.prec_at_k) and m.pos_rate > 0:
        m.lift_at_k = m.prec_at_k / m.pos_rate
    return m


# ============================================================================
# 승격 게이트
# ============================================================================
def evaluate_gate(cand: Metrics, live: Metrics, train_m: Metrics,
                  split_info: dict | None = None) -> GateResult:
    """후보 모델을 라이브로 승격할지 판정한다.

    순서가 중요하다 — 데이터 충분성을 먼저 보고, 그 다음 절대하한, 마지막에 상대비교.
    데이터가 모자란 단계에서 AUC 를 논하는 게 제일 위험하다(적재 초기).
    """
    reasons: list[str] = []

    # ── 1) 데이터 충분성 ────────────────────────────────────────────────────
    if train_m.n < MIN_TRAIN_ROWS:
        reasons.append(f"학습 행수 부족({train_m.n} < {MIN_TRAIN_ROWS})")
    if cand.n < MIN_HOLDOUT_ROWS:
        reasons.append(f"holdout 행수 부족({cand.n} < {MIN_HOLDOUT_ROWS})")
    if train_m.n_days < MIN_TRAIN_DAYS:
        reasons.append(f"학습 거래일 부족({train_m.n_days} < {MIN_TRAIN_DAYS})")
    if cand.n_days < MIN_HOLDOUT_DAYS:
        reasons.append(f"holdout 거래일 부족({cand.n_days} < {MIN_HOLDOUT_DAYS})")
    if reasons:
        return GateResult(False, reasons)

    # ── 2) 라벨 건전성 ──────────────────────────────────────────────────────
    for nm, pr in (("학습", train_m.pos_rate), ("holdout", cand.pos_rate)):
        if not np.isfinite(pr) or not (MIN_POS_RATE <= pr <= MAX_POS_RATE):
            reasons.append(f"{nm} 양성률 이상({_r(pr)} ∉ [{MIN_POS_RATE},{MAX_POS_RATE}])")
    if reasons:
        return GateResult(False, reasons)

    # ── 3) 후보 절대하한 ────────────────────────────────────────────────────
    if not np.isfinite(cand.auc):
        return GateResult(False, ["후보 AUC 산출 불가(holdout 이 한 클래스뿐)"])
    if cand.auc < ABS_AUC_MIN:
        reasons.append(f"후보 AUC 하한 미달({_r(cand.auc)} < {ABS_AUC_MIN})")
    if not np.isfinite(cand.lift_at_k) or cand.lift_at_k < ABS_LIFT_MIN:
        reasons.append(f"후보 top{PREC_AT_K} lift 하한 미달"
                       f"({_r(cand.lift_at_k)} < {ABS_LIFT_MIN})")
    if reasons:
        return GateResult(False, reasons)

    ok = [f"후보 AUC {_r(cand.auc)} ≥ {ABS_AUC_MIN}",
          f"top{PREC_AT_K} lift {_r(cand.lift_at_k)} ≥ {ABS_LIFT_MIN}"]

    # ── 4) 라이브 대비 상대비교 ─────────────────────────────────────────────
    if not np.isfinite(live.auc):
        # 라이브를 같은 holdout 으로 채점할 수 없는 경우(아티팩트 없음/피처셋 불일치).
        # 비교 대상이 없으니 절대하한만으로 승격한다 — 첫 배포/피처 변경 직후 경로.
        ok.append("라이브 모델 채점 불가 → 절대하한만으로 승격")
        return GateResult(True, ok)

    if cand.auc < live.auc + MIN_AUC_GAIN:
        reasons.append(f"라이브 대비 AUC 개선 부족(후보 {_r(cand.auc)} vs "
                       f"라이브 {_r(live.auc)}, 필요 +{MIN_AUC_GAIN})")
    if np.isfinite(live.prec_at_k) and np.isfinite(cand.prec_at_k) \
            and cand.prec_at_k < live.prec_at_k - PREC_REGRESSION_TOL:
        reasons.append(f"top{PREC_AT_K} 정밀도 후퇴(후보 {_r(cand.prec_at_k)} vs "
                       f"라이브 {_r(live.prec_at_k)}, 허용 -{PREC_REGRESSION_TOL})")
    if reasons:
        return GateResult(False, reasons)

    ok.append(f"라이브 대비 AUC +{_r(cand.auc - live.auc)} / "
              f"top{PREC_AT_K} 정밀도 {_r(live.prec_at_k)}→{_r(cand.prec_at_k)}")
    return GateResult(True, ok)
