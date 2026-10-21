"""
bt_reco_chart_analysis.py — 매수추천(2단계 composite) 신호에 엘리엇·타점 조건을 얹으면 결과가 좋아지는가.

질문
    "추천 종목 중 엘리엇·피보·패턴·다이버전스 조건을 함께 만족하는 것만 고르면(가점) / 특정 조건을 빼면(제외)
     실제 매매 결과(승률·평균수익)가 추천 전체보다 나아지는가?"
    엘리엇이 혼자 맞는지가 아니라, shape_proba 가 이미 잡은 정보 **위에** 더해지는 게 있는지를 본다.

추천 재현(운영 StockBuyCheckJob 2단계 경로를 그대로 따른다 — 워커 기본 매수순서가 composite_rank_no 우선)
    1) 종목별 일봉 → KisService.compute_indicator_df(라이브와 같은 함수) → shape 피처
    2) shape_proba = 배포 모델(shape_gbm_v1) — 라이브처럼 피처 결측은 0 으로 채운 뒤 추론
    3) 2단계 안정성 필터(_composite_eligible 재현, ema120 필터 포함)
    4) 날짜별 pool 전체 기준 모멘텀 z-score → proba 상위 10 → 모멘텀 재정렬 → composite_rank 1..10
    ※ 재무 점수가 섞인 1단계(watch 게이트 rank_no)는 과거 재무를 재현할 수 없어 다루지 않는다.
    ※ 관리종목·거래정지는 현재 상태(stock_admin_status)만 있어 과거 시점과 다를 수 있다.
    ※ 같은 날 모든 종목이 있어야 z-score 가 운영과 같아진다 — 소수 종목 스모크 테스트는 경로 확인용일 뿐.

미래 참조 차단
    - 지표·피처는 전부 과거 봉만 쓰는 rolling/ewm 이라 전체 구간에서 한 번 계산해도 D 시점 값이 같다.
      (--check-causal 로 몇 종목을 "D 까지 자른 계산"과 대조해 확인한다)
    - 차트 분석(stock_shared.chart_analysis)은 픽마다 D 까지의 봉만 넣고 다시 계산한다
      (ZigZag 는 나중 봉이 들어오면 앞 스윙이 바뀌므로 반드시 시점별 재계산).

평가
    D+1 시가 진입, 신호마다 독립 평가, 왕복 수수료 차감. 매도는 **실전 워커 근사**(bt_reco_stop.sim_live):
    손절(-5%, --stop 로 변경)·익절(+30%)·트레일은 장중 그 가격에, 타임스탑 등 일봉 신호는 다음 날 시가.
    ※ 예전 표준 run_one_trade(종가 판정·20일선 예외·익일 시가)는 실전과 달라 참고값(old_ret)으로만 남긴다.
    엘리엇 목표 익절(el_ret): 같은 매도 규칙 + 추천일 D 의 가장 유력한 '다음 상승' 해석 목표가에 닿으면 익절.

기간 구분(모델이 본 데이터와 겹치지 않게)
    A: ~2023-12-31          조건 고르기(탐색)
    B: 2024-01-01~2025-09-07  확인(검증) — 여기서 같은 방향이어야 채택
    C: 2025-09-08~          모델 학습셋(trade_shape_train_daily) 기간 → proba 가 부풀려져 참고만

데이터 소스
    --source db : stock_ohlcv_daily(5년 수정주가, StockOhlcvDailyJob 이 적재) — 본 실행
    --source yf : yfinance(코드에 .KS/.KQ 접미사) — 테이블 준비 전 스모크 테스트용

사용
    poetry run python -m app.test.bt_reco_chart_analysis --source yf --codes 005930.KS,000660.KS --check-causal
    poetry run python -m app.test.bt_reco_chart_analysis --source db                 # 전 종목(단계별 캐시)
    poetry run python -m app.test.bt_reco_chart_analysis --source db --phase report  # 캐시로 리포트만
"""
import argparse
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from app.ext_services.kis.component.KisStockService import KisService
from app.test.eval_shape_proba import (
    DB_URL,
    COMPOSITE_TOP_N, COMPOSITE_PENNY_PRICE_MIN, COMPOSITE_EXTREME_MOVE_PCT, COMPOSITE_EXTREME_LOOKBACK,
    COMPOSITE_ATR_RATIO_MAX, COMPOSITE_SMA20_TREND_BARS, COMPOSITE_MOMENTUM_COLS,
    _zscore, _base_user_info, run_one_trade, _wilson,
)
from stock_shared import chart_analysis
from stock_shared.chart_analysis.elliott import analyze_elliott
from stock_shared.ml.shape_features import (
    SHAPE_FEATURE_COLUMNS,
    EXHAUSTION_BARS_SINCE_MIN_MIN, EXHAUSTION_TOTAL_RET_14_MIN, EXHAUSTION_RET_1D_TODAY_MIN,
)
from stock_shared.strategy.kospi1 import KospiStrategy1

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'bt_reco_cache')
WARMUP_BARS = 250          # 라이브 매수추천 배치가 받는 최소 봉 수 — 이보다 앞 날짜는 신호로 안 쓴다
ANALYSIS_BARS = 350        # 차트 API 와 동일: 350봉 넣고 화면 200봉에서 분석
VIEW_BARS = 200
RECENT_DIV_BARS = 10       # 다이버전스가 최근 이 봉수 안에 끝났으면 "최근"
PERIODS = [('A', None, '2023-12-31'), ('B', '2024-01-01', '2025-09-07'), ('C', '2025-09-08', None)]


# ══════════════════════════════════════════════════════════════════
# 1. 일봉 + 지표 + proba + 2단계 적격 (종목별, 캐시)
# ══════════════════════════════════════════════════════════════════
def load_bars(source: str, code: str, engine=None) -> pd.DataFrame | None:
    if source == 'db':
        df = pd.read_sql(text(
            "SELECT trade_date, open_price, high_price, low_price, close_price, volume "
            "FROM stock_ohlcv_daily WHERE stock_code = :c ORDER BY trade_date"), engine, params={'c': code})
        if df.empty:
            return None
        df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df['datetime'] = pd.to_datetime(df['datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return df
    import yfinance as yf
    h = pd.DataFrame()
    for attempt in range(3):            # 레이트리밋·일시 오류는 잠깐 쉬고 다시
        try:
            h = yf.Ticker(code).history(period='5y', auto_adjust=True)
            break
        except Exception as e:  # noqa: BLE001
            print(f"[yf] {code} 재시도 {attempt + 1}: {e}", flush=True)
            time.sleep(3)
    if h.empty:
        return None
    # 거래정지·상장 전후 등으로 가격이 빈 봉이 섞여 오는 종목이 있다 — 정수 변환 전에 버린다
    h = h.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume']).reset_index()
    if h.empty:
        return None
    df = pd.DataFrame({
        'datetime': pd.to_datetime(h['Date']).dt.strftime('%Y-%m-%d %H:%M:%S'),
        'open': h['Open'].round().astype(int), 'high': h['High'].round().astype(int),
        'low': h['Low'].round().astype(int), 'close': h['Close'].round().astype(int),
        'volume': h['Volume'].astype(int),
    })
    return df[df['volume'] > 0].reset_index(drop=True)


def _model():
    import joblib
    path = os.path.join(os.path.dirname(__file__), '..', '..', '..',
                        'shared', 'stock_shared', 'ml', 'artifacts', 'shape_gbm_v1.joblib')
    return joblib.load(os.path.normpath(path))


def compute_stock(bars: pd.DataFrame, code: str, admin_bad: bool, model) -> pd.DataFrame:
    """라이브 _process_chunk 와 같은 순서로 지표·피처·proba·적격을 붙인다(전 구간 한 번에)."""
    computed = KisService().compute_indicator_df(bars.copy(), user_info=_base_user_info())
    computed['coin'] = code
    computed['datetime'] = computed['datetime'].astype(str).str[:10]

    # 소진 게이트는 fillna 전 raw 로(라이브와 동일)
    exh = (
        (computed['shape_bars_since_min'] >= EXHAUSTION_BARS_SINCE_MIN_MIN)
        & (computed['shape_total_ret_14'] >= EXHAUSTION_TOTAL_RET_14_MIN)
        & (computed['shape_ret_1d_today'] >= EXHAUSTION_RET_1D_TODAY_MIN)
    ).fillna(False)

    # 라이브는 computed.fillna(0.0) 뒤의 마지막 행 피처로 점수를 매긴다
    X = computed[SHAPE_FEATURE_COLUMNS].astype(float).fillna(0.0)
    computed['proba'] = model.predict_proba(X.values)[:, 1]

    close = computed['close'].astype(float)
    ema20, ema120 = computed['ema20'].astype(float), computed['ema120'].astype(float)
    ext = close.pct_change().abs().rolling(COMPOSITE_EXTREME_LOOKBACK, min_periods=1).max() * 100
    computed['eligible'] = (
        (not admin_bad)
        & (close >= COMPOSITE_PENNY_PRICE_MIN)
        & (ema20 > ema20.shift(COMPOSITE_SMA20_TREND_BARS))
        & (ema120 > 0) & (computed['low'].astype(float) > ema120)
        & (computed['atr'].astype(float) / close <= COMPOSITE_ATR_RATIO_MAX)
        & (ext < COMPOSITE_EXTREME_MOVE_PCT)
        & ~exh
        & (np.arange(len(computed)) >= WARMUP_BARS)
    ).fillna(False).astype(bool)
    return computed


def phase_features(args, codes: list, engine, admin: dict):
    os.makedirs(os.path.join(CACHE_DIR, 'stocks'), exist_ok=True)
    model = _model()
    slim = []
    for n, code in enumerate(codes, 1):
        path = os.path.join(CACHE_DIR, 'stocks', f'{code}.pkl')
        if os.path.exists(path) and not args.refresh:
            computed = pd.read_pickle(path)
        else:
            bars = load_bars(args.source, code, engine)
            if bars is None or len(bars) < WARMUP_BARS + 20:
                continue
            computed = compute_stock(bars, code, admin.get(code.split('.')[0], False), model)
            computed.to_pickle(path)
        keep = ['coin', 'datetime', 'close', 'proba', 'eligible', 'ind_rsi14'] + COMPOSITE_MOMENTUM_COLS
        slim.append(computed[keep])
        if n % 50 == 0 or n == len(codes):
            print(f"[features] {n}/{len(codes)}", flush=True)
    df = pd.concat(slim, ignore_index=True) if slim else pd.DataFrame()
    df.to_pickle(os.path.join(CACHE_DIR, 'slim.pkl'))
    return df


def check_causal(codes: list, cut_back: int = 40):
    """전 구간 계산값과 'D 까지 자른 데이터로 다시 계산한 값'이 같은지(피처·적격·proba)."""
    model = _model()
    bad = 0
    for code in codes:
        full = pd.read_pickle(os.path.join(CACHE_DIR, 'stocks', f'{code}.pkl'))
        i = len(full) - 1 - cut_back
        bars = full[['datetime', 'open', 'high', 'low', 'close', 'volume']].iloc[:i + 1].copy()
        bars['datetime'] = bars['datetime'] + ' 00:00:00'
        part = compute_stock(bars, code, False, model)
        cols = SHAPE_FEATURE_COLUMNS + ['proba', 'eligible', 'ema20', 'ema120', 'atr']
        a, b = full.iloc[i][cols], part.iloc[-1][cols]
        diff = [c for c in cols if not (pd.isna(a[c]) and pd.isna(b[c]))
                and not np.isclose(float(a[c]), float(b[c]), rtol=1e-6, atol=1e-9)]
        print(f"[causal] {code} {full.iloc[i]['datetime']}: {'OK' if not diff else '불일치 ' + str(diff)}", flush=True)
        bad += bool(diff)
    return bad == 0


# ══════════════════════════════════════════════════════════════════
# 2. 날짜별 composite top10 (운영 _compute_composite_top10 재현)
# ══════════════════════════════════════════════════════════════════
def phase_picks(slim: pd.DataFrame) -> pd.DataFrame:
    pool = slim[slim['eligible']].dropna(subset=['proba'] + COMPOSITE_MOMENTUM_COLS + ['ind_rsi14'])
    out = []
    for d, p in pool.groupby('datetime', sort=True):
        p = p.copy()
        for col in COMPOSITE_MOMENTUM_COLS:
            p[f'z_{col}'] = _zscore(p[col])
        p['z_rsi_centered'] = _zscore(p['ind_rsi14'] - 50)
        p['momentum_composite'] = p[[f'z_{c}' for c in COMPOSITE_MOMENTUM_COLS] + ['z_rsi_centered']].mean(axis=1)
        top = p.sort_values(['proba', 'coin'], ascending=[False, True]).head(COMPOSITE_TOP_N)
        top = top.sort_values(['momentum_composite', 'coin'], ascending=[False, True]).reset_index(drop=True)
        top['composite_rank'] = range(1, len(top) + 1)
        top['pool_size'] = len(p)
        out.append(top[['datetime', 'coin', 'close', 'proba', 'momentum_composite', 'composite_rank', 'pool_size']])
    picks = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    picks.to_pickle(os.path.join(CACHE_DIR, 'picks.pkl'))
    print(f"[picks] {picks['datetime'].nunique() if len(picks) else 0}일 / {len(picks)}건", flush=True)
    return picks


# ══════════════════════════════════════════════════════════════════
# 3. 픽마다 D 시점 차트 분석 → 조건값 / 4. 매매 결과
# ══════════════════════════════════════════════════════════════════
def _status(lst, typ, bias=None):
    for p in lst or []:
        if p.get('type') == typ and (bias is None or p.get('bias') == bias):
            return p.get('status')
    return None


def flatten(a: dict, ctx, dates_idx: dict, i_last: int) -> dict:
    """analysis(dict) → 조건 판정에 쓸 평평한 값들."""
    f = {}
    el = a.get('elliott') or {}
    c, items = el.get('consensus') or {}, el.get('items') or []
    f['el_label'] = c.get('label')
    f['el_up_share'] = c.get('up_share')
    f['el_unan_up'] = bool(c.get('unanimous')) and c.get('up_count', 0) > 0
    f['el_unan_down'] = bool(c.get('unanimous')) and c.get('down_count', 0) > 0
    f['el_up_invalid_pct'] = c.get('up_invalid_pct')
    f['el_trend'] = c.get('trend')
    f['el_primary_bias'] = items[0].get('bias') if items else None
    f['el_primary_title'] = items[0].get('title') if items else None
    # 큰 추세 가점 없이(TREND_WEIGHT=0) 계산한 주요 해석 — 가점 효과 비교용
    el0 = analyze_elliott(ctx.view, ctx.atr, trend_weight=0)
    f['el0_label'] = el0['consensus'].get('label')
    f['el0_primary_bias'] = el0['items'][0].get('bias') if el0['items'] else None

    fib = a.get('fib') or {}
    f['fib_side'] = (fib.get('plan') or {}).get('side')
    f['fib_status'] = fib.get('status')

    pat = a.get('pattern') or []
    f['pat_dbl_bottom'] = _status(pat, 'double_bottom')
    f['pat_dbl_top'] = _status(pat, 'double_top')
    f['pat_abcd_bull'] = _status(pat, 'abcd', 'bull')
    f['pat_abcd_bear'] = _status(pat, 'abcd', 'bear')

    def recent(d):
        j = dates_idx.get(d['to']['date'])
        return j is not None and i_last - j <= RECENT_DIV_BARS
    div = a.get('divergence') or []
    f['div_bull_recent'] = any(d['bias'] == 'bull' and recent(d) for d in div)
    f['div_bear_recent'] = any(d['bias'] == 'bear' and recent(d) for d in div)

    f['struct_trend'] = (a.get('structure') or {}).get('trend')
    return f


def _el_take(a: dict, entry: float):
    """추천일 분석에서 가장 유력한 '다음 상승' 해석의 다음 목표. 진입가 +1% 이하면 쓰지 않는다."""
    items = (a.get('elliott') or {}).get('items') or []
    up = next((c for c in items if c.get('bias') == 'up'), None)
    t = up.get('bias_target') if up else None
    return t if t and t > entry * 1.01 else None


def phase_eval(picks: pd.DataFrame, stop_pct: float = 0.05) -> pd.DataFrame:
    from app.test.bt_reco_stop import sim_live
    strategy = KospiStrategy1()
    strategy.stop_loss_pct = stop_pct
    rows = []
    t0 = time.time()
    for n, (code, grp) in enumerate(picks.groupby('coin', sort=False), 1):
        computed = pd.read_pickle(os.path.join(CACHE_DIR, 'stocks', f'{code}.pkl'))
        recs = computed.to_dict('records')
        dates_idx = {d: k for k, d in enumerate(computed['datetime'])}
        ohlc = computed[['datetime', 'open', 'high', 'low', 'close']].rename(columns={'datetime': 'ymd'})
        for _, pk in grp.iterrows():
            i = dates_idx.get(pk['datetime'])
            if i is None:
                continue
            trade = sim_live(strategy, recs, i)
            if not trade:
                continue
            full = ohlc.iloc[max(0, i - ANALYSIS_BARS + 1): i + 1]
            ctx = chart_analysis.Context(full, VIEW_BARS)
            a = {name: fn(ctx) for name, fn in chart_analysis.MODULES.items() if name not in ('swing', 'rsi')}
            entry = float(recs[i + 1]['open'])
            take = _el_take(a, entry)
            el = sim_live(strategy, recs, i, take=take) if take else trade
            old = run_one_trade(strategy, recs, i, None)
            row = {**pk.to_dict(), 'ret_net': trade['ret_net'], 'reason': trade['reason'],
                   'bars_held': trade['bars_held'],
                   'el_take_pct': (take / entry - 1) * 100 if take else np.nan,
                   'el_ret': el['ret_net'], 'el_why': el['reason'], 'el_bars': el['bars_held'],
                   'old_ret': old['ret_net'] if old else np.nan}
            row.update(flatten(a, ctx, dates_idx, i))
            rows.append(row)
        if n % 50 == 0:
            print(f"[eval] 종목 {n}/{picks['coin'].nunique()} · 신호 {len(rows)} · {time.time() - t0:.0f}s", flush=True)
    res = pd.DataFrame(rows)
    res.to_pickle(os.path.join(CACHE_DIR, 'eval.pkl'))
    res.to_csv(os.path.join(CACHE_DIR, 'eval.csv'), index=False)
    print(f"[eval] {len(res)}건 → {CACHE_DIR}/eval.csv", flush=True)
    return res


# ══════════════════════════════════════════════════════════════════
# 5. 리포트 — 조건별 추천 전체 대비
# ══════════════════════════════════════════════════════════════════
# 실행 전에 고정한 조건 목록(결과를 보고 늘리지 않는다). 'keep' 은 가점(만족만 남김), 'drop' 은 제외(만족을 뺌).
CONDITIONS = [
    ('엘리엇 상승 우세',            'keep', lambda r: r['el_label'] == '상승 우세'),
    ('엘리엇 하락 우세',            'drop', lambda r: r['el_label'] == '하락 우세'),
    ('엘리엇 방향 불명확',          'keep', lambda r: r['el_label'] == '방향 불명확'),
    ('엘리엇 전부 상승',            'keep', lambda r: r['el_unan_up']),
    ('엘리엇 전부 하락',            'drop', lambda r: r['el_unan_down']),
    ('주요 해석 다음 상승',         'keep', lambda r: r['el_primary_bias'] == 'up'),
    ('주요 해석 다음 하락',         'drop', lambda r: r['el_primary_bias'] == 'down'),
    ('상승 해석 무효선 8% 이내',     'keep', lambda r: pd.notna(r['el_up_invalid_pct']) and r['el_up_invalid_pct'] <= 8),
    ('(추세가점 없음) 상승 우세',    'keep', lambda r: r['el0_label'] == '상승 우세'),
    ('(추세가점 없음) 주요 다음 상승', 'keep', lambda r: r['el0_primary_bias'] == 'up'),
    ('피보 매수 구간 진입',          'keep', lambda r: r['fib_side'] == 'buy' and r['fib_status'] == 'in_zone'),
    ('피보 매도 쪽(하락 파동 반등)',  'drop', lambda r: r['fib_side'] == 'sell'),
    ('쌍바닥 넥라인 돌파',           'keep', lambda r: r['pat_dbl_bottom'] == 'triggered'),
    ('쌍봉 형성·이탈',              'drop', lambda r: r['pat_dbl_top'] in ('forming', 'waiting', 'triggered')),
    ('AB=CD 상승 D 도달',           'keep', lambda r: r['pat_abcd_bull'] == 'triggered'),
    ('최근 RSI 상승 다이버전스',     'keep', lambda r: bool(r['div_bull_recent'])),
    ('최근 RSI 하락 다이버전스',     'drop', lambda r: bool(r['div_bear_recent'])),
    ('추세 구조 상승',              'keep', lambda r: r['struct_trend'] == 'up'),
    ('추세 구조 하락',              'drop', lambda r: r['struct_trend'] == 'down'),
]


def _period(d: str) -> str:
    for name, s, e in PERIODS:
        if (s is None or d >= s) and (e is None or d <= e):
            return name
    return '?'


def _stat(s: pd.Series) -> dict:
    n = len(s)
    if n == 0:
        return {'n': 0, 'win': None, 'avg': None, 'ci': (None, None)}
    k = int((s > 0).sum())
    lo, hi = _wilson(k, n)
    return {'n': n, 'win': k / n * 100, 'avg': s.mean() * 100, 'ci': (lo, hi)}


def report(res: pd.DataFrame, min_n: int):
    res = res.copy()
    res['period'] = res['datetime'].map(_period)
    for scope, sub0 in (('top1(실제 매수 1순위)', res[res['composite_rank'] == 1]), ('top10', res)):
        print(f"\n══ {scope} — 승률(%) / 평균 순수익(%) / 건수  [기간 A=탐색, B=검증, C=모델 학습기간(참고)]")
        hdr = f"{'조건':<24}{'규칙':<6}" + ''.join(f"{p:>22}" for p, _, _ in PERIODS)
        print(hdr)

        def cell(sub):
            st = _stat(sub['ret_net'])
            return f"{'-':>22}" if st['n'] == 0 else f"{st['win']:>6.1f} {st['avg']:>+6.2f} n={st['n']:<5}"
        base = {p: sub0[sub0['period'] == p] for p, _, _ in PERIODS}
        print(f"{'추천 전체(기준)':<24}{'':<6}" + ''.join(cell(base[p]) for p, _, _ in PERIODS))
        for name, rule, fn in CONDITIONS:
            mask = sub0.apply(fn, axis=1).astype(bool)
            kept = sub0[mask] if rule == 'keep' else sub0[~mask]
            line = f"{name:<24}{('가점' if rule == 'keep' else '제외'):<6}"
            for p, _, _ in PERIODS:
                k = kept[kept['period'] == p]
                c = cell(k)
                b = _stat(base[p]['ret_net'])
                s = _stat(k['ret_net'])
                flag = ''
                if s['n'] >= min_n and b['n'] and s['win'] is not None:
                    flag = '↑' if s['win'] - b['win'] >= 3 and s['avg'] > b['avg'] else '↓' if s['win'] - b['win'] <= -3 else ''
                line += c[:-1] + (flag or ' ')
            print(line)
    print(f"\n↑/↓: 그 기간 표본 {min_n}건 이상이고 승률이 기준 대비 ±3%p 이상(↑는 평균수익도 개선). "
          "채택 후보 = A 와 B 모두 ↑.")

    # ── 매도: 엘리엇 목표 익절을 더하면 ──
    print("\n══ 매도 — 같은 신호, 현행(실전 근사) vs 현행 + 엘리엇 목표 익절  [top10 / top1]")
    for scope, sub0 in (('top10', res), ('top1', res[res['composite_rank'] == 1])):
        sub0 = sub0[(sub0['reason'] != 'OPEN_MTM') & (sub0['el_why'] != 'OPEN_MTM')]
        for p, _, _ in PERIODS:
            s = sub0[sub0['period'] == p]
            if not len(s):
                continue
            d = (s['el_ret'] - s['ret_net']) * 100
            rng = np.random.default_rng(7)
            bs = [d.iloc[rng.integers(0, len(d), len(d))].mean() for _ in range(1000)]
            print(f"  {scope:<6}{p}  n={len(s):<5} 승률 {(s['ret_net'] > 0).mean() * 100:5.1f}% → {(s['el_ret'] > 0).mean() * 100:5.1f}%  "
                  f"평균 {s['ret_net'].mean() * 100:+6.2f}% → {s['el_ret'].mean() * 100:+6.2f}%  "
                  f"차이 {d.mean():+.2f}%p [90% {np.percentile(bs, 5):+.2f}~{np.percentile(bs, 95):+.2f}]  "
                  f"목표 익절 {(s['el_why'] == 'TAKE').mean() * 100:.0f}% · 목표까지 중앙 {s['el_take_pct'].median():+.1f}%")

    # ── 매수 쪽 항목별 가중치(전 항목 동시 로지스틱) — A 로 맞추고 B 로 확인 ──
    from app.test.bt_reco_history import FEATURES, report as weight_report
    w = res[res['period'].isin(['A', 'B'])].copy()
    w['stock_code'] = w['coin']
    w['path'] = 'composite'
    for k, fn in FEATURES.items():
        w[k] = w.apply(fn, axis=1).astype(int)
    print("\n══ 매수 항목별 가중치 (top10 신호, 기간 A·B — '앞'=A, '뒤'=B)")
    weight_report(w, '2024-01-01', 0.5, 300, 5)


# ══════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=['db', 'yf'], default='db')
    ap.add_argument('--codes', default='', help='쉼표 목록(yf 는 .KS/.KQ 포함). 비우면 db 의 전 종목')
    ap.add_argument('--phase', choices=['all', 'features', 'picks', 'eval', 'report'], default='all')
    ap.add_argument('--refresh', action='store_true', help='종목 캐시 무시하고 다시 계산')
    ap.add_argument('--check-causal', action='store_true')
    ap.add_argument('--min-n', type=int, default=100)
    ap.add_argument('--stop', type=float, default=0.05, help='장중 손절 비율(실전 기본 0.05)')
    args = ap.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)
    engine = create_engine(DB_URL)
    codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    if not codes and args.source == 'db':
        codes = pd.read_sql(text("SELECT stock_code FROM stock_ohlcv_daily_state WHERE bar_cnt > 0 "
                                 "ORDER BY stock_code"), engine)['stock_code'].tolist()
    if not codes and args.source == 'yf':
        # 매수추천 배치와 같은 대상(StockService.get_stock_master_list('batches') 조건) + yfinance 접미사
        codes = pd.read_sql(text(
            "SELECT CONCAT(stock_code, '.', stock_type_yf) AS c FROM master_stock "
            "WHERE market_stop IN ('1', 'N') AND stock_type_yf IN ('KS', 'KQ') AND ("
            "  group_code IN ('ST', 'RT', 'MF')"
            "  OR (group_code = 'EF' AND (stock_name LIKE '%200' OR stock_name LIKE '%인버스')"
            "      AND stock_name NOT LIKE '%선물%')) "
            "ORDER BY stock_code"), engine)['c'].tolist()
        print(f"[universe] yfinance 대상 {len(codes)}종목", flush=True)
    admin = {}
    if args.phase in ('all', 'features'):
        a = pd.read_sql(text("SELECT coin, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status"), engine)
        admin = dict(zip(a['coin'], a['mang_issu_cls_code'].fillna('N').str.upper().eq('Y')
                         | a['temp_stop_yn'].fillna('N').str.upper().eq('Y')))

    if args.phase in ('all', 'features'):
        slim = phase_features(args, codes, engine, admin)
        if args.check_causal:
            check_causal([c for c in codes if os.path.exists(os.path.join(CACHE_DIR, 'stocks', f'{c}.pkl'))][:5])
    if args.phase in ('all', 'picks'):
        slim = pd.read_pickle(os.path.join(CACHE_DIR, 'slim.pkl'))
        picks = phase_picks(slim)
    if args.phase in ('all', 'eval'):
        picks = pd.read_pickle(os.path.join(CACHE_DIR, 'picks.pkl'))
        phase_eval(picks, args.stop)
    if args.phase in ('all', 'report', 'eval'):
        report(pd.read_pickle(os.path.join(CACHE_DIR, 'eval.pkl')), args.min_n)


if __name__ == '__main__':
    main()
