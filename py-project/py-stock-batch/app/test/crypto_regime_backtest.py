"""
BTC 2층 구조 백테스트 (2026-10 세션 설계 검증용). 기본 데이터 = 바이낸스 BTC/USDT.

왜 USDT 인가: BTC 이평·TOTAL 레짐은 달러 기준 지표다. 업비트 원화 가격은 김치 프리미엄 변동이
섞여 이평 신호가 달라진다. 업비트 원화로도 돌려볼 수 있게 --source upbit 를 남겨 둔다.

1층 레짐(일봉) — 보유 허용 여부만 결정한다.
    BTC 일봉 종가 > MA120  AND  TOTAL(전체 시총) > MA50  → ON, 하나라도 깨지면 OFF(전량 청산)
    근거: 2013~2026 일봉 백테스트에서 MDD 를 -85% → -54% 로 줄였고, MA 기간 25개 조합
    모두 Sharpe 1.1~1.4 로 특정 숫자에 과최적화되지 않았다. 숏 변형은 오히려 나빴다(롱/현금만).

2층 진입(1시간봉) — 레짐 ON 동안 "어떻게 들어갈지"만 비교한다.
    market   : 레짐 ON 되는 순간 시장가 전량 (기준선)
    pullback : 지정가 n분할을 ref*(1-d*i) 에 깔고 눌림에서만 체결. 미체결 상태로 가격이
               ref*(1+d) 위로 가면 ref 를 올려 다시 깐다(랠리를 영영 놓치지 않게).
    hybrid   : 1분할은 시장가, 나머지 n-1 분할은 pullback 과 같은 지정가.
    공통 하드 규칙(2021 BitMEX 공개 거래내역 분석에서 최대 손실이 전부 "상한 없는 물타기"였음):
      - 분할 수 = 물타기 상한. 다 채운 뒤엔 추가 매수 없음.
      - 손절: 1h 종가 < 평단*(1-stop) → 다음 봉 시가 청산, COOLDOWN_H 동안 재진입 금지.
      - 레짐 OFF → 다음 봉 시가 전량 청산.

look-ahead 방지:
    - 일봉 D 는 KST D 09:00 ~ D+1 09:00(바이낸스·업비트 동일). 그 종가로 만든 레짐은 D+1 09:00 봉부터 적용.
    - TOTAL(CoinMarketCap, 00:00 UTC 스탬프)은 스냅샷/일집계 여부가 불확실해 하루 더 늦춰 쓴다.
    - 지정가는 저가가 지정가를 "뚫어야"(low < limit) 체결로 본다(같은 가격 큐 대기 가정).
    - 손절/레짐 판단은 봉 종가로 하고 체결은 다음 봉 시가.

데이터: BTC 1h/1d 는 stock_shared.crypto.binance(또는 upbit)로, TOTAL 은 CoinMarketCap 웹 데이터 API
(비공식, 키 없음)로 받아 CACHE_DIR 에 캐시한다. --refresh 로 다시 받는다.

수동 실행:
    cd py-project/py-stock-batch && ./.venv/bin/python3 -m app.test.crypto_regime_backtest
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from itertools import product

import numpy as np
import pandas as pd

sys.path.insert(0, '../shared')

from stock_shared.crypto.binance import BinanceClient
from stock_shared.crypto.upbit import UpbitClient

CACHE_DIR = os.path.expanduser('~/.cache/aibees/crypto')
# 데이터 소스별 설정. fee = 편도 수수료(테이커 기준).
SOURCES = {
    'binance': dict(client=BinanceClient, start='2017-08-17', fee=0.0010, ccy='USDT',
                    label='바이낸스 BTC/USDT'),
    'upbit': dict(client=UpbitClient, start='2017-09-25', fee=0.0005, ccy='KRW',
                  label='업비트 KRW-BTC'),
}
SOURCE = 'binance'   # main 에서 --source 로 덮어쓴다

FEE = SOURCES[SOURCE]['fee']
SLIP = 0.0005         # 시장가 체결 슬리피지 가정
COOLDOWN_H = 24

BTC_MA = 120
TOTAL_MA = 50

PERIODS = {
    '전체': ('2018-03-01', None),
    '18-21': ('2018-03-01', '2021-12-31'),
    '22-26': ('2022-01-01', None),
}


# ---------------------------------------------------------------- data
def _cache(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def load_ohlcv(timeframe, refresh):
    src = SOURCES[SOURCE]
    path = _cache(f'{SOURCE}_btc_{timeframe}.csv')
    if os.path.exists(path) and not refresh:
        return pd.read_csv(path, parse_dates=['datetime'])
    print(f"{src['label']} {timeframe} 다운로드 중...")
    df = src['client']().fetch_ohlcv_range('BTC', timeframe, src['start'])
    df.to_csv(path, index=False)
    return df


def load_total(refresh):
    """CoinMarketCap 전체 시총(USD) 일별. index = UTC 날짜."""
    path = _cache('cmc_total_1d.csv')
    if os.path.exists(path) and not refresh:
        return pd.read_csv(path, parse_dates=['date']).set_index('date')['total']
    print('TOTAL 다운로드 중...')
    rows, s, end = [], 1367193600, int(time.time())
    while s < end:
        e = min(s + 2000 * 86400, end)   # API 1회 최대 2200개
        req = urllib.request.Request(
            'https://api.coinmarketcap.com/data-api/v3/global-metrics/quotes/historical'
            f'?format=chart&interval=1d&timeStart={s}&timeEnd={e}',
            headers={'User-Agent': 'Mozilla/5.0'})
        for q in json.load(urllib.request.urlopen(req, timeout=60))['data']['quotes']:
            rows.append((q['timestamp'][:10], q['quote'][0]['totalMarketCap']))
        s = e
        time.sleep(2)
    t = pd.DataFrame(rows, columns=['date', 'total']).drop_duplicates('date')
    t['date'] = pd.to_datetime(t['date'])
    t.to_csv(path, index=False)
    return t.set_index('date')['total']


# ---------------------------------------------------------------- regime
def build_signal(d1, total, use_total=True):
    """일봉 D 종가 기준 레짐 신호(index = 일봉 D). D+1 거래일에 적용하려면 shift(1)."""
    d = d1.set_index(d1['datetime'].dt.normalize())['close']
    ma = d.rolling(BTC_MA).mean()
    on = (d > ma) & ma.notna()
    if use_total:
        t = total.asfreq('D').ffill()
        t_on = (t > t.rolling(TOTAL_MA).mean()).shift(1, fill_value=False)   # 하루 더 늦춤(위 docstring)
        on = on & t_on.reindex(on.index, fill_value=False)
    return on


# ---------------------------------------------------------------- engine
def simulate(h1, regime, mode, n=3, d=0.02, stop=0.10, trail=None, cooldown_h=COOLDOWN_H,
             weight=1.0, dd_rule=None, streak_rule=None, entry_ok=None, trim=None):
    """1h 루프 시뮬레이션. 반환: 시간별 equity(Series), 거래 로그(list).

    stop  : 평단 대비 종가 손실이 이 비율을 넘으면 다음 봉 시가 청산(None/1.0 = 없음).
    trail : 진입 후 최고 종가 대비 이 비율 이상 밀리면 다음 봉 시가 청산(None = 없음).
    cooldown_h : 손절/트레일링 청산 후 재진입 금지 시간.
    계좌 단위 규칙(전부 '다음 진입'에만 적용, 보유 중 포지션을 강제로 팔지 않는다):
    weight      : 진입 시 계좌(현금)의 이 비율만 매수. 나머지는 현금(이자 0 가정).
    dd_rule     : ('half', X) → 계좌가 고점 대비 X 이상 빠져 있으면 진입 비중을 절반으로(신고점 회복 시 해제)
                  ('pause', X, days) → 청산 시점에 계좌 낙폭이 X 이상이면 days 일 동안 진입 금지
    streak_rule : (k, w_low) → k 연패 중이면 진입 비중 w_low 배. 1승하면 해제.
    entry_ok    : 거래일→bool Series(regime 과 같은 인덱스 규약). False 인 날은 새로 진입하지 않는다
                  (청산은 regime 만 따른다 — 진입 전용 필터).
    trim        : (ext, hi, lo) — ext 는 거래일→과열도 Series. 보유 중 ext > hi 인 날 09:00 에 절반 매도,
                  이후 ext < lo 로 식으면 남은 현금으로 다시 채운다(레짐 ON 동안).
    """
    ts = h1['datetime'].values
    o, hi, lo, c = (h1[k].values for k in ('open', 'high', 'low', 'close'))
    trade_day = (h1['datetime'] - pd.Timedelta(hours=9)).dt.normalize()
    on = trade_day.map(regime.astype(float)).fillna(0).astype(bool).values
    ok = (trade_day.map(entry_ok.astype(float)).fillna(0).astype(bool).values
          if entry_ok is not None else np.ones(len(on), dtype=bool))
    if trim is not None:
        ext = trade_day.map(trim[0]).values
        new_day = np.r_[True, trade_day.values[1:] != trade_day.values[:-1]]
    trimmed = False

    cash, qty = 1.0, 0.0
    cost_basis = 0.0                 # 보유분 매수금액 합(평단 계산용)
    levels, tranche = [], 0.0        # 미체결 지정가, 분할 1개 금액
    ref = None
    exit_next = False                # 다음 봉 시가 청산 예약(손절)
    cooldown_until = -1
    eq = np.empty(len(c))
    log = []
    entry_t = None                   # 현재 포지션 첫 체결 시각
    peak = 0.0                       # 진입 후 최고 종가(트레일링용)
    acct_peak = 1.0                  # 계좌 최고 평가액(dd_rule 용)
    losses = 0                       # 연패 수(streak_rule 용)
    pause_until = -1
    exit_why = 'stop'

    def buy_market(i, amount):
        nonlocal cash, qty, cost_basis, entry_t
        if entry_t is None:
            entry_t = ts[i]
        px = o[i] * (1 + SLIP)
        qty += amount * (1 - FEE) / px
        cash -= amount
        cost_basis += amount

    def sell_all(i, why):
        nonlocal cash, qty, cost_basis, levels, ref, entry_t, losses, pause_until
        if qty > 0:
            proceeds = qty * o[i] * (1 - SLIP) * (1 - FEE)
            losses = losses + 1 if proceeds < cost_basis else 0
            if dd_rule and dd_rule[0] == 'pause':
                acct = cash + proceeds
                if acct < acct_peak * (1 - dd_rule[1]):
                    pause_until = i + dd_rule[2] * 24
            log.append(dict(entry_t=entry_t, entry_px=cost_basis / qty, t=ts[i],
                            exit_px=o[i] * (1 - SLIP), why=why, pnl=proceeds / cost_basis - 1))
            cash += proceeds
        qty, cost_basis, levels, ref, entry_t = 0.0, 0.0, [], None, None

    def budget():
        """계좌 규칙을 반영한 이번 진입 금액(무포지션 상태라 cash = 계좌 평가액)."""
        w = weight
        if dd_rule and dd_rule[0] == 'half' and cash < acct_peak * (1 - dd_rule[1]):
            w *= 0.5
        if streak_rule and losses >= streak_rule[0]:
            w *= streak_rule[1]
        return cash * w

    def arm(i):
        """레짐 ON + 무포지션 + 쿨다운 끝 → 이번 봉 시가 기준으로 진입 셋업."""
        nonlocal tranche, levels, ref
        amount = budget()
        if mode == 'market':
            buy_market(i, amount)
            return
        tranche = amount / n
        ref = o[i]
        k0 = 1
        if mode == 'hybrid':
            buy_market(i, tranche)
            k0 = 2
        levels = [ref * (1 - d * (k - 1)) for k in range(k0, n + 1)] if mode == 'hybrid' \
            else [ref * (1 - d * k) for k in range(1, n + 1)]

    for i in range(len(c)):
        # 1) 시가 시점 처리: 손절 예약 / 레짐 OFF 청산 / 진입 셋업
        if exit_next:
            sell_all(i, exit_why)
            exit_next = False
            cooldown_until = i + cooldown_h
        if not on[i]:
            if qty > 0 or levels:
                sell_all(i, 'regime_off')
        elif qty == 0 and not levels and i >= max(cooldown_until, pause_until) and cash > 0 and ok[i]:
            arm(i)
        elif trim is not None and qty > 0 and new_day[i] and not np.isnan(ext[i]):
            if not trimmed and ext[i] > trim[1]:            # 과열 → 절반 익절
                q = qty / 2
                cash += q * o[i] * (1 - SLIP) * (1 - FEE)
                cost_basis *= 0.5
                qty -= q
                trimmed = True
            elif trimmed and ext[i] < trim[2]:              # 식으면 다시 채움
                buy_market(i, cash * weight)
                trimmed = False
        if qty == 0:
            trimmed = False

        # 2) 미체결 지정가: 아직 1개도 안 찼는데 가격이 위로 달아나면 ref 를 따라 올린다
        if levels and qty == 0 and ref is not None and o[i] > ref * (1 + d):
            ref = o[i]
            levels = [ref * (1 - d * k) for k in range(1, len(levels) + 1)]

        # 3) 봉 중 지정가 체결 (저가가 뚫어야 체결)
        if levels:
            remain = []
            for lv in levels:
                if lo[i] < lv:
                    if entry_t is None:
                        entry_t = ts[i]
                    amt = min(tranche, cash)
                    qty += amt * (1 - FEE) / lv
                    cash -= amt
                    cost_basis += amt
                else:
                    remain.append(lv)
            levels = remain

        # 4) 종가 시점: 손절/트레일링 판단(다음 봉 시가 체결)
        if qty > 0:
            peak = max(peak, c[i])
            if stop is not None and c[i] < (cost_basis / qty) * (1 - stop):
                exit_next, exit_why, levels = True, 'stop', []
            elif trail is not None and c[i] < peak * (1 - trail):
                exit_next, exit_why, levels = True, 'trail', []
        else:
            peak = 0.0

        eq[i] = cash + qty * c[i]
        acct_peak = max(acct_peak, eq[i])

    if qty > 0:   # 미청산 포지션은 마지막 종가로 평가해 표시만 한다
        log.append(dict(entry_t=entry_t, entry_px=cost_basis / qty, t=None, exit_px=c[-1],
                        why='open', pnl=qty * c[-1] / cost_basis - 1))
    return pd.Series(eq, index=pd.to_datetime(ts)), log


# ---------------------------------------------------------------- report
def stats(eq, h1_close, start, end):
    e = eq[start:end].resample('D').last().dropna()
    if len(e) < 30:
        return {}
    r = e.pct_change().dropna()
    yrs = (e.index[-1] - e.index[0]).days / 365
    cagr = (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1
    mdd = (e / e.cummax() - 1).min()
    sh = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else 0
    return dict(CAGR=round(cagr * 100, 1), MDD=round(mdd * 100, 1),
                Sharpe=round(sh, 2), Calmar=round(cagr / -mdd, 2) if mdd < 0 else np.nan)


def export_report(path, h1, d1, signals, regimes, res, grid, base):
    """리포트 페이지용 JSON. 메인 전략 = BTC>120&TOTAL>50 + 시장가 진입."""
    reg = regimes['BTC>120&TOTAL>50']
    eq, log = simulate(h1, reg, 'market')
    close = h1.set_index('datetime')['close']
    ed = eq.resample('D').last().dropna()
    cd = close.resample('D').last().reindex(ed.index)
    start = PERIODS['전체'][0]
    ed, cd = ed[start:], cd[start:]
    eqn, bhn = ed / ed.iloc[0], cd / cd.iloc[0]
    day = lambda t: pd.Timestamp(t).strftime('%Y-%m-%d %H:%M')
    trades = [dict(entry=day(x['entry_t']), entry_px=round(x['entry_px']),
                   exit=day(x['t']) if x['t'] is not None else None, exit_px=round(x['exit_px']),
                   ret=round(x['pnl'] * 100, 2), why=x['why'],
                   days=round(((pd.Timestamp(x['t']) if x['t'] is not None else close.index[-1])
                               - pd.Timestamp(x['entry_t'])).total_seconds() / 86400, 1))
              for x in log if pd.Timestamp(x['entry_t']) >= pd.Timestamp(start)]
    yr = pd.DataFrame({'strategy': ed.groupby(ed.index.year).last() / ed.groupby(ed.index.year).first() - 1,
                       'bh': cd.groupby(cd.index.year).last() / cd.groupby(cd.index.year).first() - 1})
    # 연도 경계 수익률: 전년 말 → 당년 말 (첫 해는 시작일부터)
    ye, yc = ed.groupby(ed.index.year).last(), cd.groupby(cd.index.year).last()
    yr['strategy'] = ye / ye.shift(1).fillna(ed.iloc[0]) - 1
    yr['bh'] = yc / yc.shift(1).fillna(cd.iloc[0]) - 1
    out = dict(
        generated=pd.Timestamp.now(tz='Asia/Seoul').strftime('%Y-%m-%d %H:%M'),
        params=dict(source=SOURCES[SOURCE]['label'], ccy=SOURCES[SOURCE]['ccy'],
                    btc_ma=BTC_MA, total_ma=TOTAL_MA, fee=FEE, slip=SLIP, start=start,
                    end=str(ed.index[-1].date())),
        daily=dict(date=[d.strftime('%Y-%m-%d') for d in ed.index],
                   close=[round(v) for v in cd], eq=[round(v, 4) for v in eqn], bh=[round(v, 4) for v in bhn],
                   dd=[round(v * 100, 2) for v in (eqn / eqn.cummax() - 1)],
                   bh_dd=[round(v * 100, 2) for v in (bhn / bhn.cummax() - 1)],
                   on=[bool(reg.get(d, False)) for d in ed.index]),
        trades=trades,
        yearly=[dict(year=int(y), strategy=round(r.strategy * 100, 1), bh=round(r.bh * 100, 1),
                     inmkt=round(float(pd.Series([reg.get(d, False) for d in ed.index], index=ed.index)
                                       [str(y)].mean()) * 100))
                for y, r in yr.iterrows()],
        summary=res.replace({np.nan: None}).to_dict('records'),
        grid=dict(base_sharpe=base['Sharpe'],
                  by_mode={m: dict(beat=round(float((gm.Sharpe > base['Sharpe']).mean()) * 100),
                                   sharpe_med=float(gm.Sharpe.median()), mdd_med=float(gm.MDD.median()),
                                   sharpe_max=float(gm.Sharpe.max()), n=len(gm))
                           for m, gm in grid.groupby('mode')}),
        current={k: bool(v.iloc[-1]) for k, v in signals.items()},
    )
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    print(f'리포트 JSON 저장: {path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true', help='캐시 무시하고 다시 다운로드')
    ap.add_argument('--export', help='리포트용 JSON 저장 경로')
    ap.add_argument('--source', choices=list(SOURCES), default='binance', help='BTC 시세 소스')
    args = ap.parse_args()

    global SOURCE, FEE
    SOURCE, FEE = args.source, SOURCES[args.source]['fee']
    print(f"데이터: {SOURCES[SOURCE]['label']} | 수수료 {FEE:.2%} + 슬리피지 {SLIP:.2%}")
    h1 = load_ohlcv('1h', args.refresh)
    d1 = load_ohlcv('1d', args.refresh)
    total = load_total(args.refresh)
    print(f'1h {len(h1)}봉 {h1.datetime.min()} ~ {h1.datetime.max()} | 1d {len(d1)}봉 | TOTAL {len(total)}일')

    signals = {'BTC>120&TOTAL>50': build_signal(d1, total, True),
               'BTC>120': build_signal(d1, total, False)}
    # D 종가 → D+1 거래일. shift(1) 대신 인덱스를 미는 이유: 마지막 신호가 다음 거래일(=오늘)까지 이어지게.
    regimes = {k: pd.Series(s.values, index=s.index + pd.Timedelta(days=1)) for k, s in signals.items()}
    bh = h1.set_index('datetime')['close']
    bh = bh / bh.iloc[0]

    # --- 1) 레짐 × 진입방식 (기본 파라미터 n=3, d=2%, stop=10%)
    rows = []
    for rname, reg in regimes.items():
        for mode in ('market', 'pullback', 'hybrid'):
            eq, log = simulate(h1, reg, mode)
            stops = sum(1 for x in log if x['why'] == 'stop')
            for pname, (s, e) in PERIODS.items():
                rows.append(dict(regime=rname, mode=mode, period=pname, **stats(eq, bh, s, e),
                                 trades=sum(1 for x in log if x['why'] != 'open'), stops=stops))
    for pname, (s, e) in PERIODS.items():
        rows.append(dict(regime='-', mode='B&H', period=pname, **stats(bh, bh, s, e)))
    res = pd.DataFrame(rows)
    for pname in PERIODS:
        print(f'\n== {pname}  (n=3, d=2%, stop=10%)')
        print(res[res.period == pname].drop(columns='period').to_string(index=False))

    # --- 2) 진입 파라미터 민감도 (레짐=BTC>120&TOTAL>50, 전체 구간 Sharpe/MDD)
    reg = regimes['BTC>120&TOTAL>50']
    base_eq, _ = simulate(h1, reg, 'market')
    base = stats(base_eq, bh, *PERIODS['전체'])
    print(f"\n== 민감도 (전체 구간) — 기준선 market: Sharpe {base['Sharpe']} / MDD {base['MDD']}%")
    grid = []
    for mode, n, d, stop in product(('pullback', 'hybrid'), (2, 3, 4), (0.01, 0.02, 0.03, 0.05),
                                    (0.05, 0.10, 0.15, 1.0)):
        eq, log = simulate(h1, reg, mode, n=n, d=d, stop=stop)
        st = stats(eq, bh, *PERIODS['전체'])
        grid.append(dict(mode=mode, n=n, d=d, stop=stop, **st))
    g = pd.DataFrame(grid)
    for mode in ('pullback', 'hybrid'):
        gm = g[g['mode'] == mode]
        print(f"\n[{mode}] Sharpe > 기준선 비율: {(gm.Sharpe > base['Sharpe']).mean():.0%}  "
              f"| Sharpe 중앙값 {gm.Sharpe.median()}  | MDD 중앙값 {gm.MDD.median()}%")
        print(gm.pivot_table(index='d', columns='stop', values='Sharpe', aggfunc='median').round(2).to_string())

    if args.export:
        export_report(args.export, h1, d1, signals, regimes, res, g, base)

    # --- 3) 현재 상태
    last_day = d1.datetime.dt.normalize().iloc[-1]
    print(f'\n현재 레짐(마감 일봉 {last_day.date()} 기준, 다음 거래일 적용):',
          {k: bool(v.iloc[-1]) for k, v in signals.items()})


if __name__ == '__main__':
    main()
