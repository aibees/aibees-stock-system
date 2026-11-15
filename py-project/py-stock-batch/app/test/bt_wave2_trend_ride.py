"""
bt_wave2_trend_ride.py — 손절·익절 없이 상승 추세를 타다가 꺾임 신호에만 파는 매도 후보 비교 + 1순위 순차 매매.

매수: 2파 하락 추세선 돌파 + 거래량 2배↑ (stock_shared.strategy.wave2_breakout, 운영과 같은 판정·필터). D+1 시가.
      events 와 달리 캐시 끝(10-21)까지 신호를 뽑아 10월도 포함. 평가 표는 결과가 충분한 ~09-16(1,249건 재현), 순차 매매는 전 구간.
매도(고정 손절·익절 없음, 신호가 올 때까지 보유. 데이터 끝이면 종가 평가):
    선 이탈형 — 두 판을 본다. C: 종가 이탈 → 다음 날 시가 / I: 장중 저가가 어제 기준 선에 닿으면 그 가격(갭이면 시가) = 실시간 감시 근사
      EMA20, EMA60, 고점-3ATR, 고점-5ATR,
      스윙2.5 / 스윙4 : ZigZag(ATR 배수) 확정 저점 이탈. 시작은 2파 저점, 더 높은 저점이 확정되면 올린다 (엘리엇: 상승 구조 붕괴)
      추세선 : 2파 저점·이후 확정 고저점(ATR 2.5)을 잇는 상승 추세선 이탈 (매수 신호의 거울)
      엘리엇+EMA20 / 엘리엇+3ATR : 3파 목표(L2 + 1.618 × 1파) 전에는 2파 저점만, 도달 후에는 EMA20 / 고점-3ATR 이탈
    신호형 — 종가 판정, 다음 날 시가 : MACD 데드, MACD 데드+EMA20 아래, 동시 꺾임(T6), OBV 데드+EMA20 아래
비교: 실전 규칙 live8(-8%, +30%, 트레일, 타임스탑).
주의: 캐시는 현재 상장 종목뿐이라 상장폐지가 빠져 있다 — 손절 없는 규칙의 꼬리 위험이 과소평가된다.

사용
    poetry run python -m app.test.bt_wave2_trend_ride
    poetry run python -m app.test.bt_wave2_trend_ride --report-only
"""
import argparse
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_reco_stop import sim_live
from app.test.bt_wave2_turn_features import indicators
from app.test.bt_wave2_trendline import CACHE, FEE, MIN_AMOUNT, MIN_CAP, MIN_PRICE, OUT as W2, WARMUP
from stock_shared.chart_analysis.indicators import atr as atr_fn
from stock_shared.strategy.reco import RecoStrategy
from stock_shared.strategy.wave2_breakout import MIN_PCT, scan

MAX_HOLD = 250
LINES = ['ema20', 'ema60', 'atr3', 'atr5', 'sw25', 'sw4', 'tline', 'ew_ema', 'ew_atr']
SIGNALS = ['macd', 'macd_ema', 't6', 'obv_ema']
RULES = [f'{x}_{m}' for x in LINES for m in ('C', 'I')] + SIGNALS + ['tline_C8', 'tline_I8']   # 끝의 8 = -8% 장중 손절 추가
NAMES = {'ema20': 'EMA20 이탈', 'ema60': 'EMA60 이탈', 'atr3': '고점-3ATR', 'atr5': '고점-5ATR', 'sw25': '스윙2.5 저점 이탈', 'sw4': '스윙4 저점 이탈',
         'tline': '상승 추세선 이탈', 'ew_ema': '엘리엇 목표 후 EMA20', 'ew_atr': '엘리엇 목표 후 3ATR', 'macd': 'MACD 데드', 'macd_ema': 'MACD 데드+EMA20 아래',
         't6': '동시 꺾임', 'obv_ema': 'OBV 데드+EMA20 아래', 'live8': '실전 규칙(live8)'}
_G = {}


def _init(meta):
    _G.update(meta)


def pivots(h, l, a, mult):
    """하루씩 진행하는 ZigZag. 확정 저점 [(확정 봉, 저점 봉, 가격)]."""
    out, direction, ext, hi, lo = [], 0, 0, 0, 0

    def thr(i, ref):
        return max(a[i] * mult, ref * MIN_PCT / 100)
    for i in range(1, len(h)):
        if direction == 0:
            hi = i if h[i] > h[hi] else hi
            lo = i if l[i] < l[lo] else lo
            if lo < hi and h[hi] - l[lo] >= thr(i, l[lo]):
                out.append((i, lo, l[lo])); direction, ext = 1, hi
            elif hi < lo and h[hi] - l[lo] >= thr(i, h[hi]):
                direction, ext = -1, lo
        elif direction > 0:
            if h[i] > h[ext]:
                ext = i
            elif h[ext] - l[i] >= thr(i, h[ext]):
                direction, ext = -1, i
        else:
            if l[i] < l[ext]:
                ext = i
            elif h[i] - l[ext] >= thr(i, l[ext]):
                out.append((i, ext, l[ext])); direction, ext = 1, i
    return out


def ride(rule, arr, i, e, l2, i2, t3):
    """rule 하나의 청산. 반환 (수익, 보유 봉수, 청산 봉 index, 미청산 여부)."""
    o, h, l, c, n = arr['o'], arr['h'], arr['l'], arr['c'], len(arr['c'])
    stop = None
    if rule.endswith('8'):                # -8% 손절 추가판: 장중 저가가 닿으면 손절가(갭이면 시가)
        rule, stop = rule[:-1], e * 0.92
    base, mode = (rule.rsplit('_', 1) + [None])[:2] if rule.endswith(('_C', '_I')) else (rule, None)
    last = min(i + MAX_HOLD, n - 1)
    peak, line, pts, reached = e, l2, [(i2, l2)], t3 <= e * 1.01
    p_key = {'sw25': 'p25', 'tline': 'p25', 'sw4': 'p4'}.get(base)
    piv = [x for x in arr[p_key] if x[1] > i2 and x[0] > i] if p_key else []
    pi = 0

    def line_at(k):
        """k 봉 종가까지 아는 정보로 정한 선 값."""
        if base == 'ema20':
            return arr['ema20'][k]
        if base == 'ema60':
            return arr['ema60'][k]
        if base == 'atr3':
            return peak - 3 * arr['a'][k]
        if base == 'atr5':
            return peak - 5 * arr['a'][k]
        if base in ('sw25', 'sw4'):
            return line
        if base == 'tline':
            if len(pts) < 2:
                return pts[0][1]
            (x0, y0), (x1, y1) = pts[-2], pts[-1]
            return max(y1 if x1 == x0 else y0 + (y1 - y0) / (x1 - x0) * (k + 1 - x0), l2)
        if base == 'ew_ema':
            return arr['ema20'][k] if reached else l2
        if base == 'ew_atr':
            return peak - 3 * arr['a'][k] if reached else l2
        return None

    y_line = line_at(i)                   # 신호일 종가까지의 선
    for k in range(i + 1, last + 1):
        if mode == 'I' and y_line == y_line and l[k] <= (y_line if stop is None else max(y_line, stop)):
            lv = y_line if stop is None else max(y_line, stop)
            return min(o[k], lv) / e - 1 - FEE, k - i, k, False
        if stop is not None and l[k] <= stop:
            return min(o[k], stop) / e - 1 - FEE, k - i, k, False
        peak = max(peak, h[k])
        reached = reached or h[k] >= t3
        while piv and pi < len(piv) and piv[pi][0] <= k:
            _, x, y = piv[pi]
            pi += 1
            if y > line:
                line = y
            if not pts or y > pts[-1][1]:
                pts.append((x, y))
        y_line = line_at(k)
        if k + 1 > last:
            break
        if mode == 'C':
            hit = y_line == y_line and c[k] < y_line
        elif mode == 'I':
            hit = False
        else:
            hit = arr[base][k]
        if hit:
            return o[k + 1] / e - 1 - FEE, k + 1 - i, k + 1, False
    return c[last] / e - 1 - FEE, last - i, last, last == n - 1 and last < i + MAX_HOLD


def run_stock(path):
    code = os.path.basename(path)[:-4]
    if not code.endswith('0') or code in _G['bad'] or code not in _G['shares']:
        return []
    df = pd.read_pickle(path).reset_index(drop=True)
    n = len(df)
    if n < WARMUP + 25:
        return []
    df['coin'] = code
    df['datetime'] = df['datetime'].astype(str).str[:10]
    o, h, l, c, v = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume'))
    amt20 = pd.Series(c * v).rolling(20).mean().to_numpy()
    cap = c * _G['shares'][code]
    ok = (np.arange(n) >= WARMUP) & (c >= MIN_PRICE) & (amt20 >= MIN_AMOUNT) & (cap >= MIN_CAP) & (np.arange(n) < n - 1)
    a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
    ev = [(i, vr, retr, s, p1) for kind, i, vr, retr, s, p1 in scan(df, a) if kind == 'tl' and ok[i] and vr == vr and vr >= 2]
    if not ev:
        return []
    x = indicators(df)
    hist = df['macd'].astype(float) - df['macd_s'].astype(float)
    e20 = df['ema20'].to_numpy(float)
    arr = {'o': o, 'h': h, 'l': l, 'c': c, 'a': a, 'ema20': e20,
           'ema60': pd.Series(c).ewm(span=60, adjust=False).mean().to_numpy(),
           'p25': pivots(h, l, a, 2.5), 'p4': pivots(h, l, a, 4.0)}
    arr['macd'] = ((hist < 0) & (hist.shift(1) >= 0)).to_numpy()
    arr['macd_ema'] = arr['macd'] & (c < e20)
    arr['t6'] = x['t6'].to_numpy()
    arr['obv_ema'] = x['t4'].to_numpy() & (c < e20)
    dates = df['datetime'].tolist()
    s8 = RecoStrategy()
    s8.stop_loss_pct = 0.08
    recs = df.to_dict('records')
    rows = []
    for i, vr, retr, since, p1 in ev:
        e = o[i + 1]
        i1 = i - int(since)
        l2_rel = int(np.argmin(l[i1 + 1:i + 1]))
        l2, i2 = l[i1 + 1 + l2_rel], i1 + 1 + l2_rel
        p0 = p1 - (p1 - l2) / retr
        t3 = l2 + 1.618 * (p1 - p0)
        r = {'code': code, 'date': dates[i], 'year': dates[i][:4], 'entry_date': dates[i + 1], 'vr': vr}
        for rule in RULES:
            ret, d, k, open_ = ride(rule, arr, i, e, l2, i2, t3)
            r[rule], r[rule + '_d'], r[rule + '_x'], r[rule + '_open'] = ret, max(d, 1), dates[k], open_
        t = sim_live(s8, recs, i)
        if t:
            r['live8'], r['live8_d'] = t['ret_net'], max(t['bars_held'], 1)
            r['live8_x'] = dates[min(i + t['bars_held'], n - 1)]
            r['live8_open'] = t.get('reason') == 'OPEN_MTM' or i + t['bars_held'] >= n - 1
        rows.append(r)
    return rows


def run():
    from sqlalchemy import create_engine
    from app.test.eval_shape_proba import DB_URL
    eng = create_engine(DB_URL)
    ms = pd.read_sql("SELECT stock_code, listed_shares FROM master_stock", eng).drop_duplicates('stock_code')
    adm = pd.read_sql("SELECT coin, iscd_stat_cls_code, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status", eng)
    bad = set(adm.coin[(adm.mang_issu_cls_code.fillna('N') == 'Y') | (adm.temp_stop_yn.fillna('N') == 'Y') | adm.iscd_stat_cls_code.isin(['51', '58'])])
    meta = {'shares': {k: float(v) for k, v in zip(ms.stock_code, ms.listed_shares) if v}, 'bad': bad}
    paths = sorted(os.path.join(CACHE, 'stocks', x) for x in os.listdir(os.path.join(CACHE, 'stocks')))
    out = []
    with Pool(8, initializer=_init, initargs=(meta,)) as pool:
        for rows in pool.imap_unordered(run_stock, paths, chunksize=8):
            out += rows
    res = pd.DataFrame(out).sort_values(['date', 'vr'], ascending=[True, False]).reset_index(drop=True)
    res.to_pickle(os.path.join(W2, 'trend_ride.pkl'))
    return res


def label_of(rule):
    if rule.endswith('8') and rule != 'live8':
        return label_of(rule[:-1]) + ' + -8% 손절'
    if rule.endswith(('_C', '_I')):
        return NAMES[rule[:-2]] + (' [종가]' if rule.endswith('_C') else ' [장중]')
    return NAMES[rule]


def table(res):
    s = res[res.date <= '2026-09-16']
    print(f"신호 {len(res)}건(~{res.date.max()}) / 평가 표 {len(s)}건(~09-16). 앞 2022~24, 뒤 2025~26. 수익 우선 정렬.\n")
    rng = np.random.default_rng(7)
    codes = s.code.to_numpy()
    groups = {k: np.flatnonzero(codes == k) for k in np.unique(codes)}
    keys = list(groups)
    rows = []
    for rule in RULES + ['live8']:
        x = s[rule].to_numpy(float)
        m = ~np.isnan(x)
        d = s[rule + '_d'].to_numpy(float)
        early = s.year.isin(['2022', '2023', '2024']).to_numpy()
        diff = x - s['live8'].to_numpy(float)
        bs = [np.nanmean(np.concatenate([diff[groups[k]] for k in rng.choice(keys, len(keys))])) for _ in range(500)]
        nm = label_of(rule)
        rows.append((np.nanmean(x), nm, np.nanmedian(x), np.nanmean(d[m]), np.nanmean(x) / np.nanmean(d[m]), np.nanmean(x > 0), np.nanmean(x >= .3),
                     np.nanpercentile(x, 10), np.nanmin(x), np.nanmean(x[early]), np.nanmean(x[~early]), np.nanmean(diff), np.percentile(bs, 5), np.percentile(bs, 95)))
    print(f"{'매도':<30}{'매매당':>8}{'중앙':>8}{'보유일':>7}{'1일당':>8}{'승률':>6}{'+30%↑':>7}{'하위10%':>9}{'최악':>8}{'앞':>8}{'뒤':>8}{'실전 대비':>10}{'90% 구간':>16}")
    for r in sorted(rows, key=lambda v: -v[0]):
        print(f"{r[1]:<30}{r[0] * 100:>+7.2f}%{r[2] * 100:>+7.2f}%{r[3]:>7.1f}{r[4] * 100:>+7.3f}%{r[5] * 100:>5.0f}%{r[6] * 100:>6.0f}%{r[7] * 100:>+8.1f}%{r[8] * 100:>+7.0f}%"
              f"{r[9] * 100:>+7.2f}%{r[10] * 100:>+7.2f}%{r[11] * 100:>+9.2f}%p{r[12] * 100:>+8.2f}~{r[13] * 100:<+6.2f}")
    print()


def sequential(res, rule, start, end=None, cost=0.0):
    """하루 신호 중 거래량 배수 1위만, 1포지션 전량. 신호일까지 청산이 끝나 있어야 매수."""
    day1 = res[(res.date >= start) & (res[rule].notna())]
    if end:
        day1 = day1[day1.date <= end]
    day1 = day1.groupby('date', sort=True).head(1)
    eq, peak, mdd, free, trades, wins = 1.0, 1.0, 0.0, '', 0, 0
    for t in day1.itertuples():
        if t.date < free:
            continue
        ret = getattr(t, rule) - cost
        eq *= 1 + ret
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        free = getattr(t, rule + '_x')
        trades += 1
        wins += ret > 0
    return eq - 1, mdd, trades, wins / max(trades, 1)


def path_table(res, rules, start, end, label):
    dates = sorted(res[(res.date >= start) & (res.date <= end)].date.unique())
    starts = dates[:40]
    print(f"[{label}] 1순위 1포지션 순차 복리. 시작일을 앞쪽 신호일 {len(starts)}개로 바꾼 분포. 비용은 체결 왕복 추가분")
    print(f"{'매도':<30}{'기준 누적':>10}{'MDD':>8}{'매매수':>7}{'승률':>6}{'분포 최소':>10}{'중앙':>9}{'최대':>9}{'비용 0.3%':>10}{'비용 0.6%':>10}")
    for rule in rules:
        r0 = sequential(res, rule, start, end)
        dist = [sequential(res, rule, s, end)[0] for s in starts]
        nm = label_of(rule)
        print(f"{nm:<30}{r0[0] * 100:>+9.0f}%{r0[1] * 100:>+7.0f}%{r0[2]:>7}{r0[3] * 100:>5.0f}%{min(dist) * 100:>+9.0f}%{np.median(dist) * 100:>+8.0f}%{max(dist) * 100:>+8.0f}%"
              f"{sequential(res, rule, start, end, .003)[0] * 100:>+9.0f}%{sequential(res, rule, start, end, .006)[0] * 100:>+9.0f}%")
    print()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--report-only', action='store_true')
    a_ = ap.parse_args()
    res_ = pd.read_pickle(os.path.join(W2, 'trend_ride.pkl')) if a_.report_only else run()
    table(res_)
    all_rules = RULES + ['live8']
    path_table(res_, all_rules, '2025-11-10', '2026-10-20', '최근 1년 2025-11-10~')
    path_table(res_, all_rules, '2022-10-01', '2026-10-20', '전체 2022-10~')
    oct_ = res_[res_.date >= '2026-09-17']
    print(f"10월 포함 구간 신호(09-17~): {len(oct_)}건, 미청산 비율 예: {oct_['ema60_C_open'].mean():.0%}(EMA60 종가)")
