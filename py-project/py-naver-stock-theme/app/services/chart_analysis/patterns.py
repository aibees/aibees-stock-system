"""차트 패턴 — 쌍봉·쌍바닥, AB=CD. 스윙 목록에서 가장 최근에 성립한(무효가 아닌) 것 하나씩만 낸다.

쌍봉·쌍바닥 타점: 넥라인 이탈(돌파) 마감에 진입, 손절은 넥라인~꼭짓점 중간, 목표는 넥라인 ± 패턴 높이.
꼭짓점을 넘으면 패턴 자체가 무효(invalid 가격)다.
"""
import pandas as pd

from app.services.chart_analysis.levels import plan, r

RECENT_BARS = 60        # 패턴의 마지막 꼭짓점이 최근 이 봉수 안에 있어야 한다
MIN_GAP_BARS = 5        # 쌍봉 두 꼭짓점 사이 최소 봉수
TOP_TOL_PCT = 3.0       # 두 꼭짓점 높이 차 허용(%). ATR×0.75 가 더 크면 그쪽
MIN_DEPTH_PCT = 5.0     # 꼭짓점 사이 골(넥라인) 최소 깊이(%). ATR×1.5 가 더 크면 그쪽
ABCD_BC = (0.382, 0.886)  # BC 되돌림 허용 범위(AB 대비)
ABCD_MAX_DIST_PCT = 30.0  # 아직 D 전인데 D 가 현재가에서 이 % 넘게 떨어져 있으면 버린다


def _after(df: pd.DataFrame, i: int) -> pd.DataFrame:
    return df.iloc[i + 1:]


def _pt(p, label):
    return {'date': p['date'], 'kind': p['kind'], 'price': r(p['price']), 'label': label}


def _double(df, swings, atr_last, n):
    """쌍봉(H-L-H) / 쌍바닥(L-H-L). 반환은 최근 것 하나씩."""
    found = {}
    for k in range(len(swings) - 2, 0, -1):
        p1, mid, p2 = swings[k - 1], swings[k], swings[k + 1]
        kind = 'double_top' if p1['kind'] == 'H' else 'double_bottom'
        if kind in found or n - 1 - p2['i'] > RECENT_BARS or p2['i'] - p1['i'] < MIN_GAP_BARS:
            continue
        ref = max(p1['price'], p2['price']) if kind == 'double_top' else min(p1['price'], p2['price'])
        tol = max(TOP_TOL_PCT / 100 * ref, atr_last * 0.75)
        depth_min = max(MIN_DEPTH_PCT / 100 * ref, atr_last * 1.5)
        if abs(p1['price'] - p2['price']) > tol:
            continue
        neck = mid['price']
        height = abs(ref - neck)
        if height < depth_min:
            continue

        after = _after(df, p2['i'])
        closes = after['close'].astype(float)
        if kind == 'double_top':
            target = neck - height
            broke = (closes < neck)
            failed = (closes > ref)
            hit = (after['low'].astype(float) <= target)
            p = plan('sell', neck, neck + height * 0.5, target, invalid=r(ref))
            names = ('첫 고점', '넥라인', '둘째 고점')
            label = '쌍봉'
        else:
            target = neck + height
            broke = (closes > neck)
            failed = (closes < ref)
            hit = (after['high'].astype(float) >= target)
            p = plan('buy', neck, neck - height * 0.5, target, invalid=r(ref))
            names = ('첫 저점', '넥라인', '둘째 저점')
            label = '쌍바닥'

        # 무효 · 이탈 중 먼저 일어난 쪽
        b_idx = broke.idxmax() if broke.any() else None
        f_idx = failed.idxmax() if failed.any() else None
        if f_idx is not None and (b_idx is None or f_idx < b_idx):
            continue        # 무효가 된 패턴은 내지 않고 더 앞의 후보를 본다
        if b_idx is not None:
            if hit.loc[b_idx:].any():
                status, status_label = 'done', '목표 도달'
            else:
                status, status_label = 'triggered', '넥라인 이탈' if kind == 'double_top' else '넥라인 돌파'
        else:
            status = 'forming' if not p2['confirmed'] else 'waiting'
            status_label = '형성 중' if not p2['confirmed'] else ('이탈 대기' if kind == 'double_top' else '돌파 대기')

        found[kind] = {
            'type': kind,
            'label': label,
            'points': [_pt(p1, names[0]), _pt(mid, names[1]), _pt(p2, names[2])],
            'neckline': r(neck),
            'trigger': f"넥라인 {r(neck):,.0f} {'아래' if kind == 'double_top' else '위'}에서 마감",
            'plan': p,
            'status': status,
            'status_label': status_label,
        }
    return list(found.values())


def _abcd(df, swings, n):
    """A-B-C 세 스윙으로 D(CD=AB)를 투영한다. 하락 AB=CD(A 고점)면 D 가 매수 후보."""
    last_close = float(df['close'].iloc[-1])
    for k in range(len(swings) - 1, 1, -1):
        a, b, c = swings[k - 2], swings[k - 1], swings[k]
        if not c['confirmed']:
            # C 가 아직 진행 중인 극값이면 D 투영 기준이 흔들린다 — 한 칸 앞에서 본다
            continue
        if n - 1 - c['i'] > RECENT_BARS:
            break
        ab = a['price'] - b['price']            # 양수면 하락 AB(→ D 매수), 음수면 상승 AB(→ D 매도)
        if ab == 0:
            continue
        bc = (c['price'] - b['price']) / ab
        if not (ABCD_BC[0] <= bc <= ABCD_BC[1]):
            continue

        bull = ab > 0
        d = c['price'] - ab
        d_ext = c['price'] - ab * 1.272
        if d <= 0 or d_ext <= 0:
            continue        # CD=AB 투영이 0 아래 — 현실성 없는 후보
        target = d + (c['price'] - d) * 0.618

        after = _after(df, c['i'])
        if bull:
            reached = after['low'].astype(float) <= d
            failed = after['high'].astype(float) > c['price']
            p = plan('buy', d, d_ext, target)
        else:
            reached = after['high'].astype(float) >= d
            failed = after['low'].astype(float) < c['price']
            p = plan('sell', d, d_ext, target)

        r_idx = reached.idxmax() if reached.any() else None
        f_idx = failed.idxmax() if failed.any() else None
        if f_idx is not None and (r_idx is None or f_idx < r_idx):
            continue        # D 전에 C 를 넘어 무효 — 더 앞의 후보를 본다
        if r_idx is None and abs(d - last_close) / last_close * 100 > ABCD_MAX_DIST_PCT:
            continue
        if r_idx is not None:
            # D 도달 이후 목표·손절 중 먼저 닿은 쪽으로 끝난 패턴인지 본다
            rest = after.loc[r_idx:]
            if bull:
                t_hit, s_hit = rest['high'].astype(float) >= target, rest['low'].astype(float) <= d_ext
            else:
                t_hit, s_hit = rest['low'].astype(float) <= target, rest['high'].astype(float) >= d_ext
            t_idx = t_hit.idxmax() if t_hit.any() else None
            s_idx = s_hit.idxmax() if s_hit.any() else None
            if s_idx is not None and (t_idx is None or s_idx <= t_idx):
                status, status_label = 'stopped', '손절 기준 통과'
            elif t_idx is not None:
                status, status_label = 'done', '목표 도달'
            else:
                status, status_label = 'triggered', 'D 도달'
        else:
            status, status_label = 'waiting', 'D 도달 대기'

        return [{
            'type': 'abcd',
            'label': 'AB=CD',
            'bias': 'bull' if bull else 'bear',
            'points': [_pt(a, 'A'), _pt(b, 'B'), _pt(c, 'C')],
            'd': r(d),
            'd_ext': r(d_ext),
            'bc_ratio': r(bc),
            'trigger': f"D {r(d):,.0f} 부근 {'반등' if bull else '저항'} 확인",
            'plan': p,
            'status': status,
            'status_label': status_label,
        }]
    return []


def analyze_patterns(df: pd.DataFrame, swings: list, atr_last: float) -> list:
    n = len(df)
    return _double(df, swings, atr_last, n) + _abcd(df, swings, n)
