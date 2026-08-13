"""
scoring.py — 매수추천 스코어 계산 (단일 진실원).

원래 StockService(py-stock-batch) 안에 있던 _tech_score / _fund_score 를
여기로 옮겼다. StockService 는 이제 이 모듈에 위임한다.

옮긴 이유:
    M3 교대매매 시뮬레이터가 "두 종목 중 score 높은 쪽" 을 골라야 하는데,
    shared 계층에서 py-stock-batch 의 StockService 를 import 할 수는 없다
    (의존 방향이 거꾸로). 복붙하면 가중치가 두 곳에서 갈라진다.
    → 순수 함수라 shared 로 올리는 게 맞다.

스코어 구성 (assign_ranks 기준)
    score = 100 * (0.5*tech + 0.3*fund + 0.2*liq)

    tech : 기술적 지표. indicator dict 하나로 계산되는 순수 함수.
    fund : 재무지표(eps/per/pbr/roe/peg).
    liq  : 거래대금 log 정규화. **후보군 전체를 봐야 하는 단면 연산**이라
           함수 하나로 안 떨어진다 → normalize_liquidity() 로 따로 둔다.

근거: 매수추천_성공패턴_대조군분석.xlsx (2026-08-08, WIN 34건 vs CONTROL 470건)
"""
import math

__all__ = [
    "ATR_RATIO_LO", "ATR_RATIO_HI", "DIP_LO_PCT", "DIP_HI_PCT",
    "TECH_WEIGHTS", "to_float", "tech_score", "fund_score",
    "normalize_liquidity", "total_score",
]

# kospi1.atr_ratio_min ~ atr_ratio_full_score 와 동일 구간
ATR_RATIO_LO, ATR_RATIO_HI = 0.05, 0.12
# kospi1.dip_from_high_min_pct ~ full_pct 와 동일 구간
DIP_LO_PCT, DIP_HI_PCT = 0.03, 0.15

# tech 하위 항목 가중치. 합계 1.0.
#   macd 0.30 · bb중심선돌파 0.15 · 거래량하한 0.20 · 변동성(ATR) 0.20 · 눌림목 0.15
TECH_WEIGHTS = {
    "macd": 0.30,
    "bb":   0.15,
    "vol":  0.20,
    "atr":  0.20,
    "dip":  0.15,
}


def to_float(v):
    """'12.5%' / '1,234' / None / 'N/A' 를 float | None 으로."""
    try:
        if v is None:
            return None
        s = str(v).replace('%', '').replace(',', '').strip()
        if s in ('', '-', 'N/A'):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _ramp(v, lo, hi):
    """lo 이하 0.0, hi 이상 1.0, 사이는 선형."""
    if v is None:
        return 0.0
    if v <= lo:
        return 0.0
    if v >= hi:
        return 1.0
    return (v - lo) / (hi - lo)


def tech_score(ind: dict, weights: dict = None,
               atr_lo: float = ATR_RATIO_LO, atr_hi: float = ATR_RATIO_HI,
               dip_lo: float = DIP_LO_PCT, dip_hi: float = DIP_HI_PCT) -> float:
    """기술적 스코어 0.0~1.0.

    ind: KospiStrategy1.get_action_in_watch 가 돌려주는 result['indicator'] dict.

    weights 를 넘기면 하위 가중치를 바꿀 수 있다(M3 최적화용).
    안 넘기면 운영 기본값(TECH_WEIGHTS).
    """
    w = weights or TECH_WEIGHTS

    # MACD: 'macd_slope_up'(기울기 상승) 우선. 구버전 indicator dict 면 골든크로스로 폴백.
    #   대조군 분석: macd_cross='G' 비율은 WIN 44.1% < CONTROL 65.3% (역상관)
    #   → raw 골든크로스 대신 기울기로 바꾸고 비중을 낮췄다.
    macd_slope_up = ind.get('macd_slope_up')
    if macd_slope_up is None:
        macd_slope_up = 'Y' if ind.get('macd_cross') == 'G' else 'N'
    macd = 1.0 if macd_slope_up == 'Y' else 0.4

    bb = 1.0 if ind.get('is_bb_mid_breakout') == 'Y' else 0.0
    vl = 1.0 if ind.get('is_vol_limit') == 'Y' else 0.0

    # ATR/종가(변동성): WIN 평균 11.8% vs CONTROL 8.9% — 가장 유의한 차이
    atr = _ramp(to_float(ind.get('atr_ratio')), atr_lo, atr_hi)

    # 고점 대비 눌림: WIN -19.3% vs CONTROL -12.1% (깊게 눌릴수록 유리). 값이 음수라 abs.
    dip_raw = to_float(ind.get('dip_from_high'))
    dip = _ramp(abs(dip_raw) if dip_raw is not None else None, dip_lo, dip_hi)

    return (w.get('macd', 0.0) * macd + w.get('bb', 0.0) * bb
            + w.get('vol', 0.0) * vl + w.get('atr', 0.0) * atr
            + w.get('dip', 0.0) * dip)


def fund_score(fin: dict) -> float:
    """재무 스코어 0.0~1.0. eps/per/pbr/roe/peg 5항목 평균.

    ※ ETF 는 이 지표들이 없어 전 항목 0점이 된다(M3 는 사실상 미사용).
    """
    eps = to_float(fin.get('eps'))
    per = to_float(fin.get('per'))
    pbr = to_float(fin.get('pbr'))
    roe = to_float(fin.get('roe'))
    peg = to_float(fin.get('peg'))

    prof = (eps is not None and eps > 0)
    eps_s = 1.0 if prof else 0.0

    # PER: 적자/None 0점, 0~10 우량, ~20 보통
    if not prof or per is None:
        per_s = 0.0
    elif 0 < per <= 10:
        per_s = 1.0
    elif per <= 20:
        per_s = 0.5
    else:
        per_s = 0.0

    # PBR
    if pbr is None:
        pbr_s = 0.0
    elif pbr <= 1.0:
        pbr_s = 1.0
    elif pbr <= 2.0:
        pbr_s = 0.5
    else:
        pbr_s = 0.0

    # ROE: 분수(0.14=14%) 가정, %로 들어오면 보정
    if roe is None:
        roe_s = 0.0
    else:
        if abs(roe) > 1.5:
            roe = roe / 100.0
        roe_s = 1.0 if roe >= 0.12 else (0.5 if roe >= 0.05 else 0.0)

    # PEG: 적자 0점, 0이하(데이터없음) 중립, 0~1 우량
    if not prof:
        peg_s = 0.0
    elif peg is None or peg <= 0:
        peg_s = 0.5
    elif peg <= 1:
        peg_s = 1.0
    else:
        peg_s = 0.5

    return (eps_s + per_s + pbr_s + roe_s + peg_s) / 5.0


def normalize_liquidity(turnovers: list) -> list:
    """거래대금(close*volume) 리스트 → 0~1 정규화 리스트.

    log10 후 min-max. 후보가 1개거나 전부 동일하면 전원 1.0.

    ⚠ 단면(cross-sectional) 연산이다. 후보가 2개뿐이면 항상 한쪽 1.0 / 한쪽 0.0
      이 되어 사실상 '거래대금 큰 쪽에 +가중' 이상의 의미가 없다.
      M3(2종목 교대)에서는 liq 가중치를 0으로 두는 걸 권장한다.
    """
    if not turnovers:
        return []
    logs = [math.log10(max(float(t or 0.0), 1.0)) for t in turnovers]
    lo, hi = min(logs), max(logs)
    span = (hi - lo) if hi > lo else 0.0
    if span <= 0:
        return [1.0] * len(logs)
    return [(x - lo) / span for x in logs]


def total_score(tech: float, fund: float, liq: float,
                w_tech: float = 0.5, w_fund: float = 0.3,
                w_liq: float = 0.2) -> float:
    """0~100 종합 스코어. 운영 기본 가중치 = tech .5 / fund .3 / liq .2."""
    return 100.0 * (w_tech * tech + w_fund * fund + w_liq * liq)
