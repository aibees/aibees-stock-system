"""
stock_shared.ml — 가격 패턴(정규화 shape) 기반 보조 신호.

- shape_features : 순수 numpy/pandas 계산(추가 의존성 없음). exhaustion 판정도 여기 있다.
- shape_model    : scikit-learn 모델 로딩/추론(선택 의존성). shape_features 와 분리한 이유는
                   sklearn 이 없는 소비처(예: py-naver-stock-theme)가 exhaustion 게이트 같은
                   가벼운 기능까지 못 쓰게 되는 걸 막기 위함이다.
"""
