"""
shape_features 9종을 입력받아 "5봉 내 +13% 먼저 도달" 확률을 내는 학습모델 래퍼.

scikit-learn/joblib 은 선택 의존성이다 — 설치 안 된 소비처(예: py-naver-stock-theme)에서
이 모듈을 그냥 import 만 해도 죽지 않도록, 무거운 import 와 모델 로딩을 전부
지연(lazy) + try/except 로 감쌌다. 실패하면 score() 가 None 을 반환할 뿐이고,
호출부(StockBuyCheckJob)는 None 이면 shape_proba 를 그냥 비워 저장한다.

2026-09 세션 리서치 결론(중요, 호출부가 꼭 알아야 함):
  이 점수는 "상단 잠재력이 큰 종목"을 찾는 데는 재현성 있게 검증됐지만,
  실전 손절/익절(OCO -8%/+15%) 백테스트에서는 기존 rank_no(과열최저) 로직보다
  승률·평균손익이 전 구간(-5%~-15% 손절폭)에서 낮았다. 그래서 이 점수를
  1순위 정렬 기준으로 강제하지 않았다 — buy_order.py 의 ORDER_FIELDS 에
  "shape_proba" 로 등록해 옵트인(s1_buy_order 에 명시해야 적용)으로만 노출한다.
  기본 정렬(DEFAULT_BUY_ORDER)은 그대로 둔다.
"""
from __future__ import annotations

import logging
import os

from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS

log = logging.getLogger("stock_shared.ml.shape_model")

_ARTIFACT_PATH = os.path.join(os.path.dirname(__file__), "artifacts", "shape_gbm_v1.joblib")

_model = None          # lazy singleton
_load_attempted = False
_load_error = None


def _load():
    global _model, _load_attempted, _load_error
    if _load_attempted:
        return
    _load_attempted = True
    try:
        import joblib
        _model = joblib.load(_ARTIFACT_PATH)
        log.info("[shape_model] 모델 로드 완료: %s", _ARTIFACT_PATH)
    except Exception as e:  # noqa: BLE001 — sklearn 미설치/아티팩트 없음 등 무엇이든 조용히 degrade
        _load_error = e
        log.warning("[shape_model] 모델 로드 실패(%s) → shape_proba 는 None 으로 처리됨: %s",
                    type(e).__name__, e)


def is_available() -> bool:
    _load()
    return _model is not None


def score(features: dict) -> float | None:
    """features: shape_features.SHAPE_FEATURE_COLUMNS 키를 가진 dict(1건).

    반환: "5봉 내 net_edge(고가기준수익-저가기준손실) >= 15%p" 확률(0~1).
          모델 미로딩/피처 결측이면 None.
    """
    _load()
    if _model is None:
        return None
    try:
        row = [features.get(c) for c in SHAPE_FEATURE_COLUMNS]
        if any(v is None for v in row):
            return None
        import numpy as np
        if any(np.isnan(v) for v in row):
            return None
        proba = _model.predict_proba([row])[0][1]
        return round(float(proba), 4)
    except Exception as e:  # noqa: BLE001
        log.warning("[shape_model] 추론 실패: %s", e)
        return None
