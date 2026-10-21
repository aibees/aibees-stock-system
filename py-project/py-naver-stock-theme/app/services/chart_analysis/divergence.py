"""RSI 다이버전스 — 연속한 스윙 고점끼리, 저점끼리 가격과 RSI 방향을 비교한다.

  일반 하락: 가격 고점↑ · RSI 고점↓   (상승 탄력 약화)
  히든 하락: 가격 고점↓ · RSI 고점↑   (하락 추세 지속)
  일반 상승: 가격 저점↓ · RSI 저점↑   (하락 탄력 약화)
  히든 상승: 가격 저점↑ · RSI 저점↓   (상승 추세 지속)
"""
import math

from app.services.chart_analysis.levels import r

MIN_RSI_GAP = 2.0      # RSI 차이가 이보다 작으면 같은 높이로 보고 버린다
MAX_BARS = 80          # 두 스윙 사이가 이보다 멀면 비교하지 않는다
KEEP = 4               # 최근 것 몇 개만 낸다

LABELS = {
    'regular_bear': '일반 하락',
    'hidden_bear': '히든 하락',
    'regular_bull': '일반 상승',
    'hidden_bull': '히든 상승',
}


def analyze_divergence(swings: list, rsi_values: list) -> list:
    out = []
    for kind in ('H', 'L'):
        pts = [p for p in swings if p['kind'] == kind]
        for p1, p2 in zip(pts, pts[1:]):
            if p2['i'] - p1['i'] > MAX_BARS:
                continue
            r1, r2 = rsi_values[p1['i']], rsi_values[p2['i']]
            if r1 is None or r2 is None or math.isnan(r1) or math.isnan(r2) or abs(r2 - r1) < MIN_RSI_GAP:
                continue
            price_up, rsi_up = p2['price'] > p1['price'], r2 > r1
            if price_up == rsi_up:
                continue
            if kind == 'H':
                key = 'regular_bear' if price_up else 'hidden_bear'
            else:
                key = 'hidden_bull' if price_up else 'regular_bull'
            out.append({
                'kind': key,
                'label': LABELS[key],
                'bias': 'bear' if key.endswith('bear') else 'bull',
                'confirmed': p2['confirmed'],
                'from': {'date': p1['date'], 'price': r(p1['price']), 'rsi': r(r1)},
                'to': {'date': p2['date'], 'price': r(p2['price']), 'rsi': r(r2)},
            })
    out.sort(key=lambda d: d['to']['date'])
    return out[-KEEP:]
