"""
bt_wave2_portfolio.py — 2파 매수추천 + 매도 규칙을 최대 N종목 분할 계좌로 돌린다. (bt_wave2_trend_ride 결과 사용)

계좌: 초기 200만원. 신호일 D 장 마감에 D 까지 끝난 청산만 현금으로 친다. 빈 슬롯 수 = N - 보유 수.
매수: 그날 추천(거래량 배수 큰 순, 최대 10개) 위에서부터 빈 슬롯만큼, 슬롯당 예산 = 현금 / 빈 슬롯 수, D+1 시가, 1주 단위 내림.
      예산으로 1주도 못 사거나 이미 보유한 종목은 건너뛰고 다음 순위. 신호 없는 날은 매수 없음. 추가 매수 없음.
매도: tline_C(상승 추세선 종가 이탈 → 다음 날 시가), tline_I(장중 터치), 각각의 -8% 장중 손절 추가판(tline_C8/I8), live8(현행 실전 규칙). 데이터 끝(10-21)은 종가 평가.
평가: 일별 종가 평가 자산으로 누적·MDD. 시작일을 앞쪽 신호일 40개로 바꾼 분포, 상위 3건 제외, 체결 비용 민감도.
주의: 현재 상장 종목만(상폐 제외). 워커 갭 게이트·슬리피지 없음. 재매수 자금의 결제 지연 없음.

사용
    poetry run python -m app.test.bt_wave2_portfolio
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import CACHE, OUT as W2

INIT = 2_000_000
END = '2026-10-21'
WINDOWS = {'최근 1년 2025-11-10~': '2025-11-10', '전체 2022-10~': '2022-10-01'}
NAMES = {'tline_C': '상승 추세선 [종가]', 'tline_I': '상승 추세선 [장중]', 'tline_C8': '추세선 [종가] + -8%', 'tline_I8': '추세선 [장중] + -8%', 'live8': '현행 실전 규칙'}
RULES = list(NAMES)


def closes(res):
    out = {}
    for code in res.code.unique():
        d = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl'))
        out[code] = dict(zip(d.datetime.astype(str).str[:10], d.close.astype(float)))
    return out


def opens(res):
    out = {}
    for code in res.code.unique():
        d = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl'))
        out[code] = dict(zip(d.datetime.astype(str).str[:10], d.open.astype(float)))
    return out


def simulate(res, by_date, op, rule, n_slots, start, cost=0.0, drop=()):
    cash, pos, trades = float(INIT), [], []

    def settle(day):
        nonlocal cash, pos
        keep = []
        for p in pos:
            if p['x'] <= day:
                cash += p['proceeds']
                trades.append(p)
            else:
                keep.append(p)
        pos = keep

    for day in by_date:
        if day < start:
            continue
        settle(day)
        free = n_slots - len(pos)
        if free <= 0:
            continue
        budget = cash / free
        held = {p['code'] for p in pos}
        for t in by_date[day]:
            if free <= 0:
                break
            ret = t[rule]
            if t['code'] in held or ret != ret or (t['code'], t['date']) in drop:
                continue
            e = op[t['code']][t['entry_date']]
            qty = int(budget // e)
            if qty < 1:
                continue
            cash -= qty * e
            pos.append({'code': t['code'], 'name': t.get('name', ''), 'date': t['date'], 'entry': t['entry_date'], 'x': t[rule + '_x'], 'e': e, 'qty': qty,
                        'ret': ret - cost, 'proceeds': qty * e * (1 + ret - cost), 'pnl': qty * e * (ret - cost), 'rank': t['rank'], 'vr': t['vr'],
                        'open': bool(t.get(rule + '_open', False))})
            held.add(t['code'])
            free -= 1
    settle('9999')
    return cash, trades


def equity_curve(trades, cl, calendar, start):
    """현금 흐름과 보유 종가로 일별 자산."""
    days = [d for d in calendar if d >= start]
    delta = {}
    for t in trades:
        delta[t['entry']] = delta.get(t['entry'], 0.0) - t['qty'] * t['e']
        delta[t['x']] = delta.get(t['x'], 0.0) + t['proceeds']
    cash, curve = float(INIT), []
    for d in days:
        cash += delta.get(d, 0.0)
        val = 0.0
        for t in trades:
            if t['entry'] <= d < t['x']:
                val += t['qty'] * cl[t['code']].get(d, t['e'])
        curve.append(cash + val)
    return pd.Series(curve, index=days)


def main():
    res = pd.read_pickle(os.path.join(W2, 'trend_ride.pkl')).sort_values(['date', 'vr'], ascending=[True, False])
    res['rank'] = res.groupby('date').cumcount() + 1
    res = res[res['rank'] <= 10]
    op, cl = opens(res), closes(res)
    calendar = sorted(pd.read_pickle(os.path.join(W2, 'breadth.pkl')).index)
    calendar = [d for d in calendar if d <= END]
    by_date = {d: g.to_dict('records') for d, g in res.groupby('date', sort=True)}
    dates = sorted(by_date)
    saved = {}
    for label, start in WINDOWS.items():
        starts = [d for d in dates if d >= start][:40]
        days = [d for d in calendar if d >= start]
        yrs = len(days) / 245
        print(f"[{label}] 초기 {INIT:,}원, {len(days)}거래일")
        print(f"{'매도':<20}{'슬롯':>4}{'최종 자산':>13}{'누적':>8}{'연환산':>8}{'MDD':>7}{'매매':>6}{'승률':>6}{'평균보유':>7}{'상위3 제외':>10}{'시작일 분포(최소/중앙/최대)':>24}{'비용0.3%':>9}{'비용0.6%':>9}")
        for rule in RULES:
            for n in (1, 3, 5):
                cash, tr = simulate(res, by_date, op, rule, n, start)
                eq = equity_curve(tr, cl, calendar, start)
                mdd = (eq / eq.cummax() - 1).min()
                top = {(t['code'], t['date']) for t in sorted(tr, key=lambda v: -v['pnl'])[:3]}
                c3, _ = simulate(res, by_date, op, rule, n, start, drop=top)
                dist = [simulate(res, by_date, op, rule, n, s)[0] / INIT - 1 for s in starts]
                hold = np.mean([calendar.index(t['x']) - calendar.index(t['entry']) + 1 for t in tr if t['x'] in calendar and t['entry'] in calendar])
                c1 = simulate(res, by_date, op, rule, n, start, .003)[0] / INIT - 1
                c2 = simulate(res, by_date, op, rule, n, start, .006)[0] / INIT - 1
                tot = cash / INIT - 1
                print(f"{NAMES[rule]:<20}{n:>4}{cash:>13,.0f}{tot * 100:>+7.0f}%{((1 + tot) ** (1 / yrs) - 1) * 100:>+7.0f}%{mdd * 100:>+6.0f}%{len(tr):>6}{np.mean([t['ret'] > 0 for t in tr]) * 100:>5.0f}%{hold:>7.1f}"
                      f"{(c3 / INIT - 1) * 100:>+9.0f}%{min(dist) * 100:>+11.0f}/{np.median(dist) * 100:+.0f}/{max(dist) * 100:+.0f}%{c1 * 100:>+8.0f}%{c2 * 100:>+8.0f}%")
                saved[(label, rule, n)] = (tr, eq)
        print()
        if start == '2022-10-01':
            print('연도별 수익률(슬롯 5, 일별 자산 기준)')
            for rule in RULES:
                eq = saved[(label, rule, 5)][1]
                yr = eq.groupby(eq.index.str[:4]).agg(['first', 'last'])
                print(f"  {NAMES[rule]:<20}" + ' '.join(f"{y} {(r['last'] / r['first'] - 1) * 100:+.0f}%" for y, r in yr.iterrows()))
            print()
    pd.to_pickle(saved, os.path.join(W2, 'portfolio.pkl'))


if __name__ == '__main__':
    main()
