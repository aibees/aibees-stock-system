"""피보나치 — 지금 되돌리고 있는 주요 파동의 되돌림·확장 레벨과 눌림/반등 타점.

마지막 스윙은 진행 중인 극값(되돌림이 간 곳)이다. 기준 파동은 "시작점이 아직 깨지지 않은
가장 최근 스윙 a" 에서 "a 이후의 최고가(최저가) b" 까지로 잡는다. 바로 앞 작은 파동만 쓰면
급락 한 번에 시작점이 깨져 곧바로 무효가 되기 때문에, 깨지지 않은 더 큰 파동으로 거슬러 올라간다.
"""
from app.services.chart_analysis.levels import plan, r

RETRACE = (0.236, 0.382, 0.5, 0.618, 0.786)
EXTEND = (1.272, 1.618)
ZONE = (0.5, 0.618)      # 눌림(반등) 타점 구간


def _major_leg(swings: list):
    """(a, b) — b 가 마지막(진행 중) 스윙이면 아직 되돌림이 아니라 파동 진행 중이라 고르지 않는다."""
    last = len(swings) - 1
    for k in range(last - 1, -1, -1):
        a = swings[k]
        later = swings[k + 1:]
        if a['kind'] == 'L':
            if any(p['kind'] == 'L' and p['price'] <= a['price'] for p in later):
                continue
            b = max((p for p in later if p['kind'] == 'H'), key=lambda p: p['price'], default=None)
        else:
            if any(p['kind'] == 'H' and p['price'] >= a['price'] for p in later):
                continue
            b = min((p for p in later if p['kind'] == 'L'), key=lambda p: p['price'], default=None)
        if b is None or b is swings[last]:
            continue
        return a, b
    return None


def analyze_fib(swings: list, last_close: float) -> dict | None:
    if len(swings) < 3:
        return None
    leg = _major_leg(swings)
    if leg is None:
        return None
    a, b = leg
    # 되돌림이 b 이후 지금까지 간 가장 깊은 가격
    after = [p['price'] for p in swings if p['i'] > b['i'] and p['kind'] != b['kind']]
    ext = (min(after) if b['kind'] == 'H' else max(after)) if after else b['price']
    start, end = a['price'], b['price']
    move = end - start
    if move == 0:
        return None
    up = move > 0

    levels = [{'ratio': k, 'price': r(end - move * k), 'kind': 'retrace'} for k in RETRACE]
    levels += [{'ratio': k, 'price': r(start + move * k), 'kind': 'extend'} for k in EXTEND]

    z1, z2 = end - move * ZONE[0], end - move * ZONE[1]
    zone_lo, zone_hi = min(z1, z2), max(z1, z2)
    stop = end - move * 0.786
    entry = (z1 + z2) / 2

    if up:
        # 상승 파동 되돌림 → 매수 후보. 파동 시작점(저점) 아래 마감이면 파동 해석 무효
        p = plan('buy', entry, stop, end, target2=start + move * 1.272,
                 zone=[r(zone_lo), r(zone_hi)], invalid=r(start))
        if last_close < start:
            status, status_label = 'invalid', '무효 · 파동 시작점 이탈'
        elif ext < stop:
            status, status_label = 'stopped', '손절 기준 이탈'
        elif ext <= zone_hi:
            status, status_label = 'in_zone', '매수 후보 구간 진입'
        else:
            status, status_label = 'waiting', '눌림 대기'
    else:
        # 하락 파동 반등 → 매도(보유분 정리) 후보. 파동 시작점(고점) 위 마감이면 무효
        p = plan('sell', entry, stop, end, target2=start + move * 1.272,
                 zone=[r(zone_lo), r(zone_hi)], invalid=r(start))
        if last_close > start:
            status, status_label = 'invalid', '무효 · 파동 시작점 돌파'
        elif ext > stop:
            status, status_label = 'stopped', '손절 기준 돌파'
        elif ext >= zone_lo:
            status, status_label = 'in_zone', '매도 후보 구간 진입'
        else:
            status, status_label = 'waiting', '반등 대기'

    return {
        'direction': 'up' if up else 'down',
        'from': {'date': a['date'], 'price': r(start)},
        'to': {'date': b['date'], 'price': r(end)},
        'levels': levels,
        'plan': p,
        'status': status,
        'status_label': status_label,
    }
