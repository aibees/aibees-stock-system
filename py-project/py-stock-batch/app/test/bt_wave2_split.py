"""
bt_wave2_split.py — 2파 하락 추세선 돌파 + 거래량 2배↑ 신호(bt_wave2_trendline)에서 분할매수 방식별 수익.

매도는 전부 현행 실전 규칙 근사(bt_reco_stop.sim_live 와 같은 루프, KospiStrategy1 손절 8%: +30% 익절·트레일·타임스탑).
수익은 **계획 예산 전체 기준**: 안 산 비중은 현금(수익 0)으로 둔다 — 1포지션 운용에서 놀린 현금도 비용이다.

매수 방식 (D = 신호일, 1차 = D+1 시가 e1)
    full        : D+1 시가 100%
    pyr{t}      : 피라미딩 50:50. 1차 50%. D+1~D+3 중 종가 >= e1 × (1 + t) 인 첫날의 다음 날 시가에 50% 추가
                  (그 시가가 현재 손절선 이하면 추가 안 함). t = 0 / 3 / 5%
    dip{t}      : 눌림 추가 50:50. 1차 50%. D+1~D+3 동안 e1 × (1 - t) 지정가 50% (저가가 닿으면 체결, 갭하락이면 시가). t = 3 / 5%
    time3       : 장중 시간분할 1/3씩 D+1 시가 · (시+고+저+종)/4 · 종가.
                  일봉 근사 — D+1 에 손절이 나면 시가분만 체결로 본다(분할에 유리한 가정).
추가 후 라인 기준 (stop_basis)
    avg   : 평단가로 손절·익절·트레일 모두 재계산(현행 worker 의 add_position_qty → 라인 재계산과 같음)
    first : 손절선은 1차 진입가 × 0.92 고정, 익절·트레일은 평단 기준
보유일수(타임스탑)는 1차 진입부터 센다. 왕복 수수료는 체결 비중만큼.

평가
    ① 신호별 개별(전 신호 1,249건) — 매매당·중앙·수익>0·보유일·1일당·최악·하위10%·연도별, full 대비 차이의 종목 부트스트랩 90% 구간
    ② 1포지션 순차 복리(참고) — 비어 있을 때 그날 거래량 배수 1위 신호만 산다. 경로 우연이 크므로 ① 이 정본.

사용
    poetry run python -m app.test.bt_wave2_split
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import OUT as W2
from app.test.bt_reco_stop import _ui, SELL_ACTIONS, INTRADAY
from app.test.eval_shape_proba import FEE_RATE
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.vo.userCoinInfo import UserCoinInfo

CACHE = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
ADD_WINDOW = 3          # 2차 매수 유효 기간(D+1~D+3)
METHODS = [('full', 'avg'),
           ('pyr0', 'avg'), ('pyr3', 'avg'), ('pyr5', 'avg'), ('pyr3', 'first'),
           ('dip3', 'avg'), ('dip5', 'avg'), ('dip3', 'first'),
           ('time3', 'avg')]
NAMES = {'full': '일괄 100%', 'pyr0': '피라미딩 +0% 확인', 'pyr3': '피라미딩 +3% 확인', 'pyr5': '피라미딩 +5% 확인',
         'dip3': '눌림 -3% 추가', 'dip5': '눌림 -5% 추가', 'time3': '장중 시간분할 1/3'}


def key(m, b):
    return f'{m}_{b}'


def label(m, b):
    return NAMES[m] + ('' if m in ('full', 'time3') else (' · 평단 라인' if b == 'avg' else ' · 1차가 손절'))


def sim_split(strategy, recs, i_sig, method, basis):
    """반환: dict(ret=예산 기준 순수익, dep=최대 투입 비중, held=보유 봉수, add=2차 체결 여부) 또는 None."""
    if i_sig + 1 >= len(recs):
        return None
    er = recs[i_sig + 1]
    e1 = float(er['open'] or 0)
    if e1 <= 0:
        return None
    sl = strategy.stop_loss_pct
    lots = []                                   # [(비중, 체결가)]
    pending = None                              # 피라미딩: 다음 날 시가에 살 비중
    if method == 'time3':
        lots.append((1 / 3, e1))
    elif method == 'full':
        lots.append((1.0, e1))
    else:
        lots.append((0.5, e1))
    trig = int(method[3:]) / 100 if method[:3] in ('pyr', 'dip') else None

    def avg():
        w = sum(x for x, _ in lots)
        return sum(x * p for x, p in lots) / w

    def lines(a):
        stop = e1 * (1 - sl) if basis == 'first' else a * (1 - sl)
        return stop, a * (1 + strategy.take_profit_pct)

    def done(px, held):
        w = sum(x for x, _ in lots)
        ret = sum(x * (px / p - 1) for x, p in lots) - 2 * FEE_RATE * w
        return {'ret': ret, 'dep': w, 'held': max(held, 1), 'add': len(lots) > 1}

    ui = _ui(e1, er)
    a = avg()
    stop, target = lines(a)
    peak = e1
    for i in range(i_sig + 1, len(recs)):
        r, prev_r = recs[i], recs[i - 1]
        o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
        first = i == i_sig + 1
        held = i - i_sig
        # ── 장 시작 전 체결: 피라미딩 2차(전날 종가 확인 → 오늘 시가) ──
        if pending is not None:
            if o > stop:
                lots.append((pending, o))
                a = avg(); stop, target = lines(a)
                ui.avg_price = ui.entry_price = a
            pending = None
        # ── 장중 체결: 눌림 지정가 ──
        if method.startswith('dip') and len(lots) == 1 and held <= ADD_WINDOW:
            lim = e1 * (1 - trig)
            if l <= lim:
                lots.append((0.5, lim if first else min(o, lim)))
                a = avg(); stop, target = lines(a)
                ui.avg_price = ui.entry_price = a
        atr = float(r['atr'] or ui.entry_atr or 0)
        trail = None
        if strategy.use_trailing and (peak - a) / a >= strategy.trail_activate_pct:
            trail, _ = strategy._trail_line_of(a, peak, atr)
        if l <= stop:
            return done(stop if first else min(o, stop), held)
        if h >= target:
            return done(target if first else max(o, target), held)
        if trail is not None and l <= trail:
            return done(min(o, trail), held)
        # ── 장중 시간분할 나머지 2/3 (D+1, 손절이 안 났을 때만) ──
        if method == 'time3' and first:
            lots.append((1 / 3, (o + h + l + c) / 4))
            lots.append((1 / 3, c))
            a = avg(); stop, target = lines(a)
            ui.avg_price = ui.entry_price = a
        # ── 피라미딩 확인(종가) ──
        if method.startswith('pyr') and len(lots) == 1 and held <= ADD_WINDOW and c >= e1 * (1 + trig):
            pending = 0.5
        peak = max(peak, h)
        prev_peak = ui.peak_high
        ui.peak_high = max(ui.peak_high, h)
        ui.peak_close = max(ui.peak_close, c)
        ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
        ui.bars_held += 1
        ra = (strategy.get_action_in_active(UserCoinInfo.from_dict(prev_r), UserCoinInfo.from_dict(r), ui)
              or {}).get('result_action')
        if ra in SELL_ACTIONS and ra not in INTRADAY:
            if i + 1 < len(recs):
                return done(float(recs[i + 1]['open'] or recs[i + 1]['close']), held)
            return done(c, held)
    return done(float(recs[-1]['close']), len(recs) - 1 - i_sig)


def evaluate():
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)].copy()
    s8 = KospiStrategy1(); s8.stop_loss_pct = 0.08
    rows = []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
        df['coin'] = code
        df['datetime'] = df['datetime'].astype(str).str[:10]
        recs = df.to_dict('records')
        idx = {d: k for k, d in enumerate(df['datetime'])}
        for x in g.itertuples():
            i = idx.get(x.date)
            if i is None or i + 1 >= len(recs):
                continue
            r = {'code': code, 'date': x.date, 'year': x.year, 'vol_ratio': x.vol_ratio}
            for m, b in METHODS:
                t = sim_split(s8, recs, i, m, b)
                if t is None:
                    break
                k = key(m, b)
                r[k], r[k + '_d'], r[k + '_dep'], r[k + '_add'] = t['ret'], t['held'], t['dep'], t['add']
                r[k + '_exit'] = recs[min(i + t['held'], len(recs) - 1)]['datetime']
            else:
                rows.append(r)
    res = pd.DataFrame(rows)
    res.to_pickle(os.path.join(W2, 'split.pkl'))
    return res


def sequential(res, k):
    """1포지션 순차 복리: 비어 있으면 그날 거래량 배수 1위 신호를 D+1 에 사고, 청산일 신호부터 다시 본다(청산 다음 날 시가 매수)."""
    day = res.sort_values(['date', 'vol_ratio'], ascending=[True, False]).groupby('date').head(1)
    eq, free_from, n = 1.0, '', 0
    curve = []
    for x in day.itertuples():
        if x.date < free_from:
            continue
        eq *= 1 + getattr(x, k)
        free_from = getattr(x, k + '_exit')
        n += 1
        curve.append(eq)
    curve = np.array(curve)
    mdd = (curve / np.maximum.accumulate(curve) - 1).min() if len(curve) else 0
    return eq, n, mdd


def report(res):
    base = key('full', 'avg')
    print(f"2파 하락 추세선 돌파 + 거래량 2배↑ 신호 {len(res)}건 — 분할매수 방식별 (매도 = 현행 실전 규칙, 손절 8%)")
    print("수익은 계획 예산 전체 기준(안 산 비중은 현금 0%)\n")
    print(f"{'매수 방식':<30}{'매매당':>8}{'중앙':>8}{'수익>0':>8}{'투입':>7}{'2차체결':>8}{'보유일':>7}{'1일당':>8}"
          f"{'최악':>8}{'하위10%':>9}   연도별 매매당(2023/24/25/26)")
    for m, b in METHODS:
        k = key(m, b)
        x, d = res[k] * 100, res[k + '_d']
        yr = ' / '.join(f"{res[res.year == y][k].mean() * 100:+.2f}" for y in ('2023', '2024', '2025', '2026'))
        add = f"{res[k + '_add'].mean() * 100:.0f}%" if m not in ('full',) else '-'
        print(f"{label(m, b):<30}{x.mean():>+7.2f}%{x.median():>+7.2f}%{(x > 0).mean() * 100:>7.0f}%"
              f"{res[k + '_dep'].mean() * 100:>6.0f}%{add:>8}{d.mean():>7.1f}{x.mean() / d.mean():>+7.3f}%"
              f"{x.min():>+7.1f}%{np.percentile(x, 10):>+8.1f}%   {yr}")
    print("\nfull 대비 매매당 차이 [종목 단위 부트스트랩 90%]")
    rng = np.random.default_rng(7)
    codes = res.code.unique()
    for m, b in METHODS[1:]:
        k = key(m, b)
        dd = res[k] - res[base]
        g = {c: dd[res.code == c].values for c in codes}
        ks = list(g)
        bs = [np.concatenate([g[c] for c in rng.choice(ks, len(ks))]).mean() for _ in range(1000)]
        print(f"  {label(m, b):<30}{dd.mean() * 100:>+6.2f}%p  [{np.percentile(bs, 5) * 100:+.2f} ~ {np.percentile(bs, 95) * 100:+.2f}]")
    print("\n결과 구간별 — full 이 손실(<0)인 신호 vs 수익(>0)인 신호에서 각 방식의 평균")
    lose, win = res[res[base] < 0], res[res[base] > 0]
    for m, b in METHODS:
        k = key(m, b)
        print(f"  {label(m, b):<30}손실 신호 {lose[k].mean() * 100:>+6.2f}% (n={len(lose)})   수익 신호 {win[k].mean() * 100:>+6.2f}% (n={len(win)})")
    print("\n(참고) 1포지션 순차 복리 — 그날 거래량 배수 1위만, 청산 다음 날부터 재진입")
    for m, b in METHODS:
        eq, n, mdd = sequential(res, key(m, b))
        print(f"  {label(m, b):<30}누적 {(eq - 1) * 100:>+8.1f}%  매매 {n:>3}건  MDD {mdd * 100:>+6.1f}%")


if __name__ == '__main__':
    report(evaluate())
