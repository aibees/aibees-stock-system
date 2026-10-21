"""추세 구조 — 최근 확정 스윙 고점 2개·저점 2개로 상승/하락/횡보 판정 + 지지·저항."""
from app.services.chart_analysis.levels import r


def analyze_structure(swings: list, last_close: float) -> dict | None:
    conf = [p for p in swings if p['confirmed']]
    highs = [p for p in conf if p['kind'] == 'H']
    lows = [p for p in conf if p['kind'] == 'L']
    if len(highs) < 2 or len(lows) < 2:
        return None

    h1, h2 = highs[-2]['price'], highs[-1]['price']
    l1, l2 = lows[-2]['price'], lows[-1]['price']
    if h2 > h1 and l2 > l1:
        trend, label = 'up', '상승'
    elif h2 < h1 and l2 < l1:
        trend, label = 'down', '하락'
    else:
        trend, label = 'range', '횡보'

    res, sup = highs[-1], lows[-1]
    # 구조가 바뀌는 가격: 상승 구조는 직전 저점 이탈, 하락 구조는 직전 고점 돌파, 횡보는 둘 중 먼저
    if trend == 'up':
        pivot = {'price': r(sup['price']), 'label': '직전 저점 아래 마감 시 상승 구조 훼손'}
    elif trend == 'down':
        pivot = {'price': r(res['price']), 'label': '직전 고점 위 마감 시 하락 구조 전환'}
    else:
        pivot = None

    return {
        'trend': trend,
        'trend_label': label,
        'resistance': {'date': res['date'], 'price': r(res['price'])},
        'support': {'date': sup['date'], 'price': r(sup['price'])},
        'pivot': pivot,
        'close': r(last_close),
    }
