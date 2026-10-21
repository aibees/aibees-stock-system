"""엘리엇 파동 후보 해석 — 표시용(백테스트로 가중치를 맞추지 않은 상태).

1) 스윙을 세 단위(ATR 2.5/4/6배)로 뽑아 파동 단위(degree)를 대신한다.
2) 각 단위에서 "지금까지 이어지는" 연속 스윙으로 후보를 만든다.
   - 충격파: 0-1-2(-3-4-5), 5파 뒤 A 까지. 마지막 스윙은 진행 중인 파동이다.
   - 조정파: 0-A-B(-C), 지그재그(B 되돌림 ≤0.886) / 플랫(0.9~1.38).
3) 절대 규칙(2파는 1파 시작점 유지, 3파는 1파 끝 돌파·최단 금지, 4파는 1파와 비중첩, 5파는 3파 끝 돌파)을
   어기면 버리고, 남은 후보를 가이드라인 점수로 줄 세운다.
     피보 적합도 45 · 완성된 파동 수 20 · 2·4파 교대 10 · 시작점이 직전 극값인가 15 · 파동별 최소 봉수 10
   점수 가중치는 경험값이라 순위는 "가능성 높은 순"이 아니라 "규칙·비율에 잘 맞는 순"으로 읽는다.

가격 계산은 산술 가격이 기본이고, 목표·예상 경로가 현재가의 10% 이하로 나오는 해석만 로그 가격
(파동 길이 = 등락률)으로 다시 계산한다. 예) -70% 하락 1파에 1.618배를 산술로 곱하면 3파 목표가 0 아래.
반대로 큰 상승 파동을 처음부터 로그로 하면 연장 목표가 과하게 커져서 둘을 섞는다.
방향도 맞춰(norm) 상승형처럼 계산한 뒤 되돌린다 — 하락형은 x = -가격(로그면 -ln 가격).
"""
import math

from app.services.chart_analysis.swings import find_swings
from app.services.chart_analysis.levels import r

DEGREES = (2.5, 4.0, 6.0)
TOP_N = 4
MIN_SCORE = 30
MIN_WAVE_BARS = 3


def _close(v, ideals):
    """비율 v 가 이상값들 중 가장 가까운 것에 얼마나 붙어 있나(0~1)."""
    return max(math.exp(-((v - i) / (0.12 * i + 0.05)) ** 2) for i in ideals)


class _Norm:
    def __init__(self, up: bool, log: bool = False):
        self.s = 1 if up else -1
        self.log = log

    def x(self, price):
        return self.s * (math.log(price) if self.log else price)

    def p(self, x):
        v = self.s * x
        return r(math.exp(v) if self.log else v)


def _start_extreme(P, s, norm):
    """시작 스윙이 그 앞의 같은 종류 스윙보다 극단(상승형이면 가장 낮은 저점)인가."""
    before = [p for p in P[:s] if p['kind'] == P[s]['kind']]
    if not before:
        return 0.5
    x0 = norm.x(P[s]['price'])
    return 1.0 if all(norm.x(p['price']) > x0 for p in before) else 0.0


def _bars_ok(bars, complete):
    return 1.0 if all(bars[k] - bars[k - 1] >= MIN_WAVE_BARS for k in range(1, complete + 1)) else 0.0


def _pick_now(x_now, basic, ext, rising):
    """진행 중 파동의 도착 예상: 기본 목표 → 이미 넘었으면 확장 목표 → 그것도 넘었으면 현재 극값."""
    if rising:
        return basic if x_now < basic else ext if x_now < ext else x_now
    return basic if x_now > basic else ext if x_now > ext else x_now


def _avg_bars(bars, complete):
    lens = [bars[k] - bars[k - 1] for k in range(1, complete + 1)]
    return max(sum(lens) / len(lens), MIN_WAVE_BARS) if lens else 8


def _projection(norm, steps, first_bars, avg):
    out, ahead = [], first_bars
    for k, (label, x) in enumerate(steps):
        if k:
            ahead += max(int(round(avg)), MIN_WAVE_BARS)
        out.append({'bars': int(ahead), 'price': norm.p(x), 'label': label})
    return out


def _impulse(P, s, last_i, log=False):
    seq = P[s:]
    n = len(seq) - 1
    if not 2 <= n <= 6:
        return None
    up = seq[0]['kind'] == 'L'
    N = _Norm(up, log)
    x = [N.x(p['price']) for p in seq]
    bars = [p['i'] for p in seq]
    w = [None] + [abs(x[k] - x[k - 1]) for k in range(1, n + 1)]

    # ── 절대 규칙 ──
    if x[2] <= x[0]:
        return None                                  # 2파가 1파 시작점을 깸
    if n >= 4 and x[3] <= x[1]:
        return None                                  # 3파가 1파 끝을 못 넘음
    if n >= 4 and x[4] <= x[1]:
        return None                                  # 4파가 1파 구간과 겹침
    if n >= 6:
        if x[5] <= x[3]:
            return None                              # 5파가 3파 끝을 못 넘음(절단형은 다루지 않는다)
        if w[3] < w[1] and w[3] < w[5]:
            return None                              # 3파 최단
    if n == 5 and w[3] < w[1] and w[5] >= w[3]:
        return None                                  # 진행 중 5파가 이미 3파보다 길어짐 → 3파 최단

    # ── 가이드라인 점수 ──
    fits, ratios = [], []
    if n >= 3:
        v = w[2] / w[1]; fits.append(_close(v, (0.5, 0.618))); ratios.append({'label': '2파 / 1파', 'value': r(v)})
    if n >= 4:
        v = w[3] / w[1]; fits.append(_close(v, (1.618, 2.618, 1.0))); ratios.append({'label': '3파 / 1파', 'value': r(v)})
    if n >= 5:
        v = w[4] / w[3]; fits.append(_close(v, (0.382, 0.236, 0.5))); ratios.append({'label': '4파 / 3파', 'value': r(v)})
    if n >= 6:
        v = w[5] / w[1]; fits.append(_close(v, (1.0, 0.618, 1.618))); ratios.append({'label': '5파 / 1파', 'value': r(v)})
    fib = sum(fits) / len(fits) if fits else 0.4
    complete = n - 1
    if n >= 5:
        d2, d4 = w[2] / w[1], w[4] / w[3]
        t2, t4 = bars[2] - bars[1], max(bars[4] - bars[3], 1)
        alt = 1.0 if abs(d2 - d4) > 0.15 or not (0.625 < t2 / t4 < 1.6) else 0.0
    else:
        alt = 0.5
    score = 45 * fib + 20 * min(complete, 5) / 5 + 10 * alt + 15 * _start_extreme(P, s, N) + 10 * _bars_ok(bars, complete)

    # ── 현재 파동 기준 목표·확인·무효 ──
    cur = n
    xn = x[n]
    confirm = None
    if cur == 2:
        basic, ext = x[1] - 0.5 * w[1], x[1] - 0.618 * w[1]
        bl, el = '1파의 0.5 되돌림', '1파의 0.618 되돌림'
        confirm = (x[1], '1파 끝 돌파 시 3파 확인')
        invalid = (x[0], '1파 시작점 이탈')
    elif cur == 3:
        basic, ext = x[2] + 1.618 * w[1], x[2] + 2.618 * w[1]
        bl, el = '1파 길이의 1.618배', '1파 길이의 2.618배'
        if xn < x[1]:
            confirm = (x[1], '1파 끝 돌파 시 3파 확인')
        invalid = (x[2], '2파 끝 이탈')
    elif cur == 4:
        basic, ext = x[3] - 0.382 * w[3], x[3] - 0.5 * w[3]
        bl, el = '3파의 0.382 되돌림', '3파의 0.5 되돌림'
        invalid = (x[1], '1파 끝과 겹침')
    elif cur == 5:
        basic, ext = x[4] + w[1], x[4] + 1.618 * w[1]
        bl, el = '1파와 같은 길이', '1파 길이의 1.618배'
        if xn < x[3]:
            confirm = (x[3], '3파 끝 돌파 시 5파 확인')
        invalid = (x[4], '4파 끝 이탈')
    else:  # 5파 뒤 A
        whole = x[5] - x[0]
        basic, ext = x[5] - 0.382 * whole, x[5] - 0.5 * whole
        bl, el = '전체 파동의 0.382 되돌림', '전체 파동의 0.5 되돌림'
        if xn > x[4]:
            confirm = (x[4], '4파 끝 이탈 시 조정 확인')
        invalid = (x[5], '5파 끝 돌파 시 5파 연장')

    rising = cur % 2 == 1
    end_now = _pick_now(xn, basic, ext, rising)

    # 예상 경로(기본 비율) — 현재 파동 끝 → 이어지는 파동들
    if cur == 2:
        p3 = end_now + 1.618 * w[1]; p4 = p3 - 0.382 * (p3 - end_now)
        steps = [('2', end_now), ('3', p3), ('4', p4), ('5', p4 + w[1])]
    elif cur == 3:
        p4 = end_now - 0.382 * (end_now - x[2])
        steps = [('3', end_now), ('4', p4), ('5', p4 + w[1])]
    elif cur == 4:
        steps = [('4', end_now), ('5', end_now + w[1])]
    elif cur == 5:
        steps = [('5', end_now), ('A', end_now - 0.382 * (end_now - x[0]))]
    else:
        pa = end_now; pb = pa + 0.5 * (x[5] - pa)
        steps = [('A', pa), ('B', pb), ('C', pb - (x[5] - pa))]
    avg = _avg_bars(bars, complete)
    elapsed = last_i - bars[n - 1]
    first = max(int(round(avg - elapsed)), 1) if end_now != xn else bars[n] - last_i   # 이미 끝났으면 현재 극값 자리(과거 봉)

    labels = ['0', '1', '2', '3', '4', '5', 'A']
    dname = '상승' if up else '하락'
    title = f"{dname} 5파 완료 · A파 조정" if n == 6 else f"{dname} {n}파 진행"
    return {
        'type': 'impulse',
        'direction': 'up' if up else 'down',
        'title': title,
        'subtitle': '충격파',
        'current': labels[n],
        'score': score,
        'points': [{'date': p['date'], 'kind': p['kind'], 'price': r(p['price']), 'label': labels[k]} for k, p in enumerate(seq)],
        'ratios': ratios,
        'target': {'basic': N.p(basic), 'basic_label': bl, 'extended': N.p(ext), 'extended_label': el},
        'confirm': {'price': N.p(confirm[0]), 'label': confirm[1]} if confirm else None,
        'invalid': {'price': N.p(invalid[0]), 'label': invalid[1]},
        'projection': _projection(N, steps, first, avg),
        'scale': 'log' if log else 'linear',
    }


def _correction(P, s, last_i, log=False):
    seq = P[s:]
    n = len(seq) - 1
    if n not in (2, 3):
        return None
    a_up = seq[0]['kind'] == 'L'          # A 파가 오르는 조정(=하락 추세 속 반등)
    N = _Norm(a_up, log)
    x = [N.x(p['price']) for p in seq]
    bars = [p['i'] for p in seq]
    a = x[1] - x[0]
    if a <= 0:
        return None
    b = (x[1] - x[2]) / a
    if not 0 < b <= 1.38:
        return None
    zigzag = b <= 0.886
    fits = [_close(b, (0.5, 0.618, 0.382)) if zigzag else _close(b, (1.0,))]
    ratios = [{'label': 'B파 / A파', 'value': r(b)}]
    if n == 3:
        c = (x[3] - x[2]) / a
        ratios.append({'label': 'C파 / A파', 'value': r(c)})
        if c >= 0.5:
            fits.append(_close(c, (1.0, 1.618, 0.618)))
    fib = sum(fits) / len(fits)
    if s >= 1:
        prior = abs(x[0] - N.x(P[s - 1]['price']))
        ctx = 1.0 if prior >= a else 0.0      # 조정은 앞선 파동보다 작아야 자연스럽다
    else:
        ctx = 0.5
    complete = n - 1
    score = 45 * fib + 20 * 0.6 * complete / 3 + 10 * ctx + 15 * _start_extreme(P, s, N) + 10 * _bars_ok(bars, complete)

    xn = x[n]
    confirm = None
    if n == 2:
        basic, ext = x[1] - 0.5 * a, x[1] - 0.618 * a
        bl, el = 'A파의 0.5 되돌림', 'A파의 0.618 되돌림'
        invalid = (x[1] - 1.38 * a, 'A파 1.38배 넘게 되돌림')
        end_now = _pick_now(xn, basic, ext, False)
        steps = [('B', end_now), ('C', end_now + a)]
    else:
        basic, ext = x[2] + a, x[2] + 1.618 * a
        bl, el = 'A파와 같은 길이', 'A파 길이의 1.618배'
        if xn < x[1]:
            confirm = (x[1], 'A파 끝 넘으면 C파 확인')
        invalid = (x[2], 'B파 끝 돌파')
        end_now = _pick_now(xn, basic, ext, True)
        steps = [('C', end_now)]
    avg = _avg_bars(bars, complete)
    elapsed = last_i - bars[n - 1]
    first = max(int(round(avg - elapsed)), 1) if end_now != xn else bars[n] - last_i   # 이미 끝났으면 현재 극값 자리(과거 봉)

    labels = ['0', 'A', 'B', 'C']
    dname = '상승' if a_up else '하락'
    return {
        'type': 'correction',
        'direction': 'up' if a_up else 'down',
        'title': f"{dname} A·B·C 조정 · {labels[n]}파 진행",
        'subtitle': '지그재그' if zigzag else '플랫',
        'current': labels[n],
        'score': score,
        'points': [{'date': p['date'], 'kind': p['kind'], 'price': r(p['price']), 'label': labels[k]} for k, p in enumerate(seq)],
        'ratios': ratios,
        'target': {'basic': N.p(basic), 'basic_label': bl, 'extended': N.p(ext), 'extended_label': el},
        'confirm': {'price': N.p(confirm[0]), 'label': confirm[1]} if confirm else None,
        'invalid': {'price': N.p(invalid[0]), 'label': invalid[1]},
        'projection': _projection(N, steps, first, avg),
        'scale': 'log' if log else 'linear',
    }


def _prices(c):
    t = c['target']
    return [t['basic'], t['extended']] + [p['price'] for p in c['projection']]


def _build(fn, P, s, last_i, floor):
    c = fn(P, s, last_i)
    if c is not None and min(_prices(c)) <= floor:
        c = fn(P, s, last_i, log=True)
    return c


def analyze_elliott(view, atr) -> list:
    last_i = len(view) - 1
    floor = float(view['close'].iloc[-1]) * 0.1
    best = {}
    for mult in DEGREES:
        P = find_swings(view, atr, atr_mult=mult)
        e = len(P) - 1
        if e < 2:
            continue
        for s in range(max(0, e - 6), e - 1):
            for fn in (_impulse, _correction):
                c = _build(fn, P, s, last_i, floor)
                if c is None:
                    continue
                c['degree'] = mult
                # 같은 해석이 여러 단위에서 나오면 점수 높은 쪽만
                key = (c['title'], c['points'][0]['date'])
                if key not in best or c['score'] > best[key]['score']:
                    best[key] = c
    items = sorted(best.values(), key=lambda c: -c['score'])
    # 제목이 같은 해석은 하나만(시작점만 다른 후보가 목록을 채우지 않게)
    seen, out = set(), []
    for c in items:
        if c['title'] in seen or c['score'] < MIN_SCORE:
            continue
        seen.add(c['title'])
        c['score'] = int(round(c['score']))
        out.append(c)
        if len(out) == TOP_N:
            break
    return out
