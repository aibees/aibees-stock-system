"""
bt_wave2_fake_rise.py — "큰 승자는 두고 가짜 상승만 일찍 거른다" 검증.

대상: 2파 하락 추세선 돌파 + 거래량 2배↑ 신호(bt_wave2_trendline events.pkl). 매수 D+1 시가, 기준 매도 = base15(+15%/-8%/10거래일).
정의
    큰 승자   : base15 가 +15% 에 닿은 신호  (건드리면 안 되는 대상. 최우선 보호)
    가짜 상승 : 한 번 +3% 이상 갔다가 -8% 손절된 신호 (청산 후보)
    운명      : +3% 도달 신호가 이후 어떻게 끝났나(+15% / -8% / 10일 만료)

[1단계] 운명 분포 — 가짜 상승이 흔한가?
[2단계] 사전 고정한 청산 규칙 각각을 채점. 규칙은 "+3% 이상 갔던 신호"에서 보유 중에만 발동하고,
        발동하면 그 규칙의 체결가로 청산, 아니면 기준 결과 그대로.
        종가 신호 → 익일 시가 체결 / 장중 규칙 → 라인가(갭이면 시가) 체결. 같은 봉에 기준 청산이 겹치면 기준 우선(보수적).
        채점: 큰 승자를 몇 건·얼마 자르나(비용) vs 가짜 상승에서 얼마 막나(이득) → 매매당 순 효과(종목 단위 부트스트랩).
  규칙(사전 고정, 추가 금지 — 많이 시험하면 우연히 좋아 보이는 조합이 나온다)
    R1 돌파 실패 : 종가가 돌파일 종가 아래로 복귀
    R2 거래량 음봉 : 음봉 + 거래량 ≥ 20일 평균 1.5배
    R3 반납 50%  : 고점 수익의 50% 이상 반납한 종가 (고점 ≥ +3%)
    R4 20일선 이탈 : 종가가 EMA20 아래 (진입 후 +3% 갔던 뒤)
  기준선(판독 없는 단순 규칙 — 패턴 규칙이 이걸 못 이기면 쓸 이유 없음)
    B1 본전 손절 : +4% 도달 후 손절선을 진입가로
    B2 트레일 3%+ : +3% 도달 후 고점 - 3×ATR(진입 ATR) 이탈
왕복 수수료 0.22%. 수익 극대화 기준: 매매당 평균 수익.

사용
    poetry run python -m app.test.bt_wave2_fake_rise
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from app.test.bt_wave2_trendline import OUT as W2
from stock_shared.chart_analysis.indicators import atr as atr_fn

CACHE = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
FEE = 0.0022
H = 10          # 기준 보유 거래일
STOP, TP = 0.08, 0.15
ARM = 0.03      # "상승했다"의 기준
RULES = ['R1', 'R2', 'R3', 'R4', 'B1', 'B2']
NAMES = {'R1': 'R1 돌파일 종가 아래 복귀', 'R2': 'R2 거래량 1.5배 음봉', 'R3': 'R3 고점수익 50% 반납', 'R4': 'R4 EMA20 이탈',
         'B1': 'B1 +4% 후 본전 손절', 'B2': 'B2 +3% 후 트레일 3ATR'}


def base_path(o, h, l, c, i, e):
    """base15 경로. 반환 (수익, 결과 'W'/'F'/'N', 종료 오프셋 d, 도달 최대고가수익(종료 봉 포함)).
    최대고가수익은 손절 봉의 고가까지 포함한다 — 같은 날 +3% 찍고 -8% 까지 밀린 건도 '한 번 +3% 갔던 신호'다.
    다만 일봉으로는 그 봉 안의 고가·저가 순서를 알 수 없고, 같은 봉에 -8%·+15% 가 다 닿으면 손절로 친다(보수적)."""
    peak = 0.0
    for d in range(1, H + 1):
        k = i + d
        if l[k] / e - 1 <= -STOP:
            return (-STOP if d == 1 else min(o[k] / e - 1, -STOP)) - FEE, 'F', d, max(peak, h[k] / e - 1)
        peak = max(peak, h[k] / e - 1)
        if peak >= TP:
            return (TP if d == 1 else max(o[k] / e - 1, TP)) - FEE, 'W', d, peak
    return c[i + H] / e - 1 - FEE, 'N', H, peak


def apply_rules(o, h, l, c, v, ema, atr_e, i, e, sig_close, end_d):
    """각 규칙의 (청산 오프셋 d, 수익). 기준 종료일(end_d) 이전(엄격히 작은 날)에 발동한 경우만 값이 있다."""
    out = {r: None for r in RULES}
    armed = False          # 한 번이라도 고가가 +3% 를 넘었나(전날까지 확정된 것만 규칙 판정에 사용)
    peak = 0.0
    be_armed = False       # +4% 도달
    for d in range(1, end_d):
        k = i + d
        # --- 장중 규칙(B1, B2): 오늘 봉 이전까지의 고점 기준 라인 ---
        if out['B1'] is None and be_armed and l[k] <= e:
            out['B1'] = (d, (e if d == 1 else min(o[k], e)) / e - 1 - FEE)
        if out['B2'] is None and armed:
            line = peak - 3 * atr_e
            if line > 0 and l[k] <= line:
                px = line if d == 1 else min(o[k], line)
                out['B2'] = (d, px / e - 1 - FEE)
        # --- 오늘 봉 반영 ---
        peak = max(peak, h[k])
        if peak / e - 1 >= ARM:
            armed = True
        if peak / e - 1 >= 0.04:
            be_armed = True
        # --- 종가 규칙: 내일 시가 체결(내일이 기준 종료일보다 빨라야 함) ---
        if armed and d + 1 < end_d:
            nx = o[k + 1] / e - 1 - FEE
            pk = peak / e - 1
            if out['R1'] is None and c[k] < sig_close:
                out['R1'] = (d + 1, nx)
            vavg = v[max(0, k - 20):k].mean() if k >= 1 else 0
            if out['R2'] is None and c[k] < o[k] and vavg > 0 and v[k] >= 1.5 * vavg:
                out['R2'] = (d + 1, nx)
            if out['R3'] is None and pk >= ARM and (c[k] / e - 1) <= 0.5 * pk:
                out['R3'] = (d + 1, nx)
            if out['R4'] is None and c[k] < ema[k]:
                out['R4'] = (d + 1, nx)
    return out


def evaluate():
    ev = pd.read_pickle(os.path.join(W2, 'events.pkl'))
    ev = ev[(ev.kind == 'tl') & (ev.vol_ratio >= 2)].copy()
    rows = []
    for code, g in ev.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl')).reset_index(drop=True)
        df['datetime'] = df['datetime'].astype(str).str[:10]
        o, h, l, c, v, ema = (df[k].to_numpy(float) for k in ('open', 'high', 'low', 'close', 'volume', 'ema20'))
        a = atr_fn(df['high'].astype(float), df['low'].astype(float), df['close'].astype(float)).bfill().fillna(0).to_numpy()
        idx = {d: k for k, d in enumerate(df['datetime'])}
        for x in g.itertuples():
            i = idx.get(x.date)
            if i is None or i + H + 1 >= len(c):
                continue
            e = o[i + 1]
            ret, res, end_d, peak = base_path(o, h, l, c, i, e)
            r = {'code': code, 'date': x.date, 'year': x.year, 'base': ret, 'res': res, 'end_d': end_d,
                 'peak': peak, 'armed': peak >= ARM,
                 'stop_bar_high': h[i + end_d] / e - 1, 'stop_bar_low': l[i + end_d] / e - 1}
            if peak >= ARM:
                for name, val in apply_rules(o, h, l, c, v, ema, a[i], i, e, c[i], end_d).items():
                    r[name] = np.nan if val is None else val[1]
                    r[name + '_d'] = np.nan if val is None else val[0]
            rows.append(r)
    res = pd.DataFrame(rows)
    res.to_pickle(os.path.join(W2, 'fake_rise.pkl'))
    return res


def boot(x, codes, rng, n=1000):
    """종목 단위 부트스트랩: x(신호별 값, 전체 신호 기준) 평균의 90% 구간."""
    g = {k: x[codes == k] for k in np.unique(codes)}
    ks = list(g)
    bs = [np.concatenate([g[k] for k in rng.choice(ks, len(ks))]).mean() for _ in range(n)]
    return np.percentile(bs, 5), np.percentile(bs, 95)


def report(res):
    n = len(res)
    print(f"2파 추세선 돌파+거래량 2배↑ 신호 {n}건 — 기준 base15 매매당 {res.base.mean() * 100:+.2f}%\n")
    print("[1단계] 운명 분포 (기준 base15)")
    for k, nm in (('W', '+15% 도달(큰 승자)'), ('F', '-8% 손절'), ('N', '10일 만료')):
        print(f"  {nm:<18}{(res.res == k).sum():>6}건 {(res.res == k).mean() * 100:>5.1f}%")
    ar = res[res.armed]
    print(f"\n  한 번이라도 +{ARM * 100:.0f}% 도달: {len(ar)}건 ({len(ar) / n * 100:.0f}%)")
    for k, nm in (('W', '→ 결국 +15% 도달'), ('F', '→ 가짜 상승(-8% 손절)'), ('N', '→ 10일 만료')):
        s = ar[ar.res == k]
        extra = f"  평균 {s.base.mean() * 100:+.1f}%" if len(s) else ''
        print(f"  {nm:<22}{len(s):>6}건 {len(s) / len(ar) * 100:>5.1f}%{extra}")
    f = ar[ar.res == 'F']
    both = f[(f.stop_bar_high >= ARM)]
    amb = res[(res.stop_bar_high >= TP) & (res.stop_bar_low <= -STOP)]
    print(f"  가짜 상승 중 손절 봉 자체에서 +3% 이상 찍은 건: {len(both)}건 (봉 안 순서 불명) / 같은 봉에 +15%·-8% 둘 다 닿아 손절 처리: {len(amb)}건")
    print(f"  가짜 상승이 +3% 이후 -8% 까지 걸린 일수 중앙 {f.end_d.median():.0f}일 / 고점 +3% 도달 때 고점수익 중앙 {f.peak.median() * 100:+.1f}%")
    print(f"  (가짜 상승 평균 손실 {f.base.mean() * 100:+.2f}% — 청산이 막을 수 있는 최대치는 건당 이 값과 +3% 청산 수익의 차이)")

    print(f"\n[2단계] 청산 규칙 채점 — 전체 {n}건 기준 매매당 효과(규칙 적용 - 기준). 큰 승자 손실이 최우선 지표.")
    print(f"{'규칙':<24}{'발동':>5}{'큰승자 자름':>12}{'자른 손실':>10}{'가짜 잡음':>10}{'막은 손실':>10}{'순효과/매매':>12}{'90% 구간(종목)':>18}   연도별(23/24/25/26)")
    rng = np.random.default_rng(7)
    codes = res.code.to_numpy()
    for r in RULES:
        fired = res[r].notna()
        new = np.where(fired, res[r], res.base)
        diff = new - res.base.to_numpy()
        w = fired & (res.res == 'W')
        fk = fired & (res.res == 'F')
        nw = (res.res == 'W').sum()
        nf = ((res.res == 'F') & res.armed).sum()
        lo, hi = boot(diff, codes, rng)
        yr = ' / '.join(f"{diff[(res.year == y).to_numpy()].mean() * 100:+.2f}" for y in ('2023', '2024', '2025', '2026'))
        print(f"{NAMES[r]:<24}{fired.sum():>5}{w.sum():>6}/{nw:<4}({w.sum() / nw * 100:>2.0f}%){diff[w.to_numpy()].sum() / n * 100:>+8.2f}%"
              f"{fk.sum():>6}/{nf:<4}{diff[fk.to_numpy()].sum() / n * 100:>+9.2f}%{diff.mean() * 100:>+10.2f}%p{lo * 100:>+9.2f}~{hi * 100:<+7.2f}   {yr}")
    print("\n  자른 손실/막은 손실 = 해당 건들의 (규칙-기준) 합을 전체 건수로 나눈 값(%p). 순효과 = 둘의 합 + 나머지(만료 건).")


if __name__ == '__main__':
    report(evaluate())
