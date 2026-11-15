"""
bt_wave2_intraday_turn.py — 장중 분봉으로 "수익 상태에서 +15% 도달 전에 꺾이면 바로 판다" 검증.

대상: 분봉이 있는 최근 약 1년 2파 신호(collect_wave2_minutes). 매수 D+1 시가.
기준: +15% / -8% / 10거래일을 1분봉 순서대로 판정(일봉에서 몰랐던 같은 봉 안 순서를 여기서 가린다).
발동: 봉 완성 시점에 현재 수익 ≥ X 이고 신호가 켜지면, 다음 1분봉 시가에 전량 매도(수수료 포함, 슬리피지 없음).
      기준 청산보다 먼저일 때만 인정. 장 마지막 봉 신호는 다음 날 시가 체결(갭 위험 그대로).
신호(사전 고정, 결과 보고 바꾸지 않는다)
    RECO 고점 반납   : 1분봉 종가 수익이 진입 후 고점 수익의 50% 이하
    S2 VWAP 이탈  : 5분봉 종가가 당일 VWAP 위 → 아래
    S3 5분 MACD   : 5분봉 히스토그램 기울기 + → - 이고 거래량이 직전 12봉 평균보다 큼
    S4 30분 동시 꺾임: 30분봉 최근 3봉 내 BB(20,2) 상단 터치 + 종가 상단 아래 + MACD 기울기 음 + OBV 3봉 기울기 음
    U  무조건     : 1분봉 종가 수익 ≥ X 면 판독 없이 매도 (그 수준에서 '계속 보유'의 가치를 보는 기준)
지표는 진입 전 3거래일 분봉부터 이어 계산한다. 비교: 같은 신호 집합에 일봉 규칙(bt_wave2_profit_turn) 적용 결과.

사용
    poetry run python -m app.test.bt_wave2_intraday_turn
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_fake_rise import CACHE, FEE, boot
from app.test.bt_wave2_trendline import OUT as W2
from app.test.collect_wave2_minutes import FROM, OUT as MIN_DIR, WARMUP

LEVELS = [0.0, 0.03, 0.05, 0.08, 0.10]
SIGS = {'U': 'U 무조건', 'RECO': 'RECO 고점 50% 반납', 'S2': 'S2 VWAP 이탈', 'S3': 'S3 5분 MACD+거래량', 'S4': 'S4 30분 동시 꺾임'}
STOP, TP = 0.08, 0.15


def resample(m, rule):
    """1분봉 → N분봉. 15:30 단일가 체결은 직전 봉에 합친다. 완성 시각 = 그 묶음의 마지막 1분봉."""
    t = m.index.where(m.index.strftime('%H%M') != '1530', m.index - pd.Timedelta(minutes=1))
    g = m.groupby(pd.DatetimeIndex(t).floor(rule))
    b = g.agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'), volume=('volume', 'sum'))
    b['pos'] = g['pos'].last()
    return b


def macd_hist(c):
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    return m - m.ewm(span=9, adjust=False).mean()


def signals(m):
    """각 1분봉 위치에 대응하는 신호 배열(S2~S4). 봉 완성 위치에서만 True."""
    n = len(m)
    out = {k: np.zeros(n, bool) for k in ('S2', 'S3', 'S4')}
    # S2 VWAP (당일 누적)
    tp = (m.high + m.low + m.close) / 3
    day = m.index.normalize()
    vwap = (tp * m.volume).groupby(day).cumsum() / m.volume.groupby(day).cumsum().replace(0, np.nan)
    m5 = resample(m, '5min')
    v5 = vwap.to_numpy()[m5.pos.to_numpy()]
    below = m5.close.to_numpy() < v5
    above_prev = np.r_[False, m5.close.to_numpy()[:-1] >= v5[:-1]]
    out['S2'][m5.pos.to_numpy()[below & above_prev]] = True
    # S3 5분 MACD + 거래량
    slope = macd_hist(m5.close).diff()
    flip = (slope < 0) & (slope.shift(1) >= 0)
    vavg = m5.volume.shift(1).rolling(12).mean()
    on = flip & (m5.volume > vavg) & (np.arange(len(m5)) >= 35)
    out['S3'][m5.pos.to_numpy()[on.to_numpy()]] = True
    # S4 30분 동시 꺾임
    m30 = resample(m, '30min')
    mid = m30.close.rolling(20).mean()
    ub = mid + 2 * m30.close.rolling(20).std()
    touch = (m30.high >= ub).astype(float).rolling(3).max() == 1
    sl = macd_hist(m30.close).diff()
    obv = (np.sign(m30.close.diff()).fillna(0) * m30.volume).cumsum()
    on = touch & (m30.close < ub) & (sl < 0) & (obv - obv.shift(3) < 0) & (np.arange(len(m30)) >= 26)
    out['S4'][m30.pos.to_numpy()[on.to_numpy()]] = True
    return out


def evaluate():
    tr = pd.read_pickle(os.path.join(W2, 'fake_rise.pkl'))
    tr = tr[tr.date >= FROM]
    rows, skipped = [], 0
    for code, g in tr.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl'))
        dates = df['datetime'].astype(str).str[:10].tolist()
        idx = {d: k for k, d in enumerate(dates)}
        for s in g.itertuples():
            i = idx[s.date]
            days = [dates[i + d].replace('-', '') for d in range(1 - WARMUP, int(s.end_d) + 1)]
            paths = [os.path.join(MIN_DIR, code, f'{d}.pkl') for d in days]
            hold_days = days[WARMUP:]
            if not all(os.path.exists(os.path.join(MIN_DIR, code, f'{d}.pkl')) for d in hold_days):
                skipped += 1
                continue
            m = pd.concat([pd.read_pickle(p) for p in paths if os.path.exists(p)]).astype(float)
            m = m[m.close > 0].copy()
            m['pos'] = np.arange(len(m))
            sig = signals(m)
            start = int(np.searchsorted(m.index, pd.Timestamp(hold_days[0])))
            e = float(df['open'].iloc[i + 1])
            o, h, l, c = (m[k].to_numpy(float)[start:] for k in ('open', 'high', 'low', 'close'))
            # 기준 경로(1분봉 순서, 같은 분은 손절 먼저)
            hit_s = np.flatnonzero(l <= e * (1 - STOP))
            hit_t = np.flatnonzero(h >= e * (1 + TP))
            ts, tt = (hit_s[0] if len(hit_s) else 10 ** 9), (hit_t[0] if len(hit_t) else 10 ** 9)
            if ts == 10 ** 9 and tt == 10 ** 9:
                res, end, ret = 'N', len(c) - 1, c[-1] / e - 1 - FEE
            elif ts <= tt:
                res, end, ret = 'F', ts, min(o[ts], e * (1 - STOP)) / e - 1 - FEE
            else:
                res, end, ret = 'W', tt, max(o[tt], e * (1 + TP)) / e - 1 - FEE
            gain = c / e - 1
            peak = np.maximum.accumulate(h) / e - 1
            on = {'U': np.ones(len(c), bool), 'RECO': (peak > 0) & (gain <= 0.5 * peak)}
            on.update({k: v[start:] for k, v in sig.items()})
            r = {'code': code, 'date': s.date, 'res_d': s.res, 'res': res, 'base': ret, 'n': end,
                 'peak_before': peak[end - 1] if end else 0.0}
            for X in LEVELS:
                ok = gain[:end] >= X
                for nm, a in on.items():
                    f = np.flatnonzero(a[:end] & ok)
                    if len(f):
                        t = f[0] + 1              # 다음 1분봉 시가
                        r[f'{nm}_{X:.2f}'] = o[t] / e - 1 - FEE
                        r[f'{nm}_{X:.2f}_days'] = len(np.unique(m.index[start:][:t + 1].normalize()))
            rows.append(r)
    res = pd.DataFrame(rows)
    want = [f'{n}_{X:.2f}' for n in SIGS for X in LEVELS]
    res = res.reindex(columns=list(res.columns) + [w for w in want if w not in res.columns])
    res.to_pickle(os.path.join(W2, 'intraday_turn.pkl'))
    return res, skipped


def line(lab, v, tr, rng):
    n, nw = len(tr), (tr.res == 'W').sum()
    base = tr.base.to_numpy()
    fired = ~np.isnan(v)
    diff = np.where(fired, v, base) - base
    w = fired & (tr.res == 'W').to_numpy()
    f = fired & (tr.res == 'F').to_numpy()
    lo, hi = boot(diff, tr.code.to_numpy(), rng, n=500)
    half = tr.date.to_numpy() < np.sort(tr.date.to_numpy())[len(tr) // 2]
    px = np.nanmean(v) * 100 if fired.any() else float('nan')
    print(f"{lab:<24}{fired.sum():>5}{w.sum():>5}/{nw:<3}({w.sum() / nw * 100:>3.0f}%){f.sum():>5}/{(tr.res == 'F').sum():<4}{px:>+7.1f}%"
          f"{diff.mean() * 100:>+8.2f}%p{lo * 100:>+8.2f}~{hi * 100:<+7.2f}{diff[half].mean() * 100:>+7.2f}{diff[~half].mean() * 100:>+7.2f}")


def report(tr, skipped):
    rng = np.random.default_rng(7)
    print(f"신호 {len(tr)}건(제외 {skipped}) / 분봉 기준 매매당 {tr.base.mean() * 100:+.2f}% / {tr.res.value_counts().to_dict()}")
    ch = tr[tr.res != tr.res_d]
    print(f"일봉 판정과 달라진 건 {len(ch)}: {ch.groupby(['res_d', 'res']).size().to_dict()}")
    f = tr[tr.res == 'F']
    print(f"손절 {len(f)}건 중 손절 전 +3% 이상 갔던 건 {(f.peak_before >= .03).sum()} / +5% {(f.peak_before >= .05).sum()} / +8% {(f.peak_before >= .08).sum()} / +10% {(f.peak_before >= .10).sum()}\n")
    head = f"{'':<24}{'발동':>5}{'큰승자 자름':>13}{'손절 잡음':>10}{'청산가':>8}{'순효과':>10}{'90% 구간':>16}{'앞':>7}{'뒤':>7}"
    for X in LEVELS:
        print(f"[현재 수익 ≥ {X * 100:.0f}%] 장중\n{head}")
        for nm, lab in SIGS.items():
            line(lab, tr[f'{nm}_{X:.2f}'].to_numpy(float), tr, rng)
        print()
    d = pd.read_pickle(os.path.join(W2, 'profit_turn.pkl'))
    d = d[d.date >= FROM].merge(tr[['code', 'date']], on=['code', 'date'])
    print(f"[비교] 같은 {len(d)}건에 일봉 규칙(다음 날 시가, 기준은 일봉 판정)\n{head}")
    for X in LEVELS:
        for nm, lab in (('U', 'U 무조건'), ('T2', 'T2 MACD 꺾임'), ('T6', 'T6 동시 꺾임')):
            line(f"{X * 100:>3.0f}% {lab}", d[f'{nm}_{X:.2f}'].to_numpy(float), d, rng)


if __name__ == '__main__':
    report(*evaluate())
