"""
eval_shape_proba.py — 편향 없는 전종목 스캔(trade_shape_scan_stock) 기반 "승률" 시뮬레이션.

2026-09 세션에서 ad-hoc 으로 돌렸다가 커밋 안 해서 날아간 proba 백테스트를
재현 가능한 형태로 복원한 것.

╔══════════════════════════════════════════════════════════════════════════════╗
║ ★ 2026-09-23: "20일선(sma20) 하락 모멘트 제어" 가정은 **철회됐다**(사용자 결정). ║
║   아래 ma20 기울기 계열 variant(sell_*/buy_ma20/both)는 그 검증에 쓴 것이고,    ║
║   운영에 반영하지 않는다. 코드는 **재실험 방지용 증거**로만 남긴다 —            ║
║   같은 가정을 다시 세우기 전에 이 파일 아래 "실행 결과" 블록을 먼저 읽을 것.     ║
║   기본 실행(--variant 기본값 base)은 ma20 조건이 전부 꺼진 순수 proba 백테스트다.║
╚══════════════════════════════════════════════════════════════════════════════╝

20일선 기울기 조건 (철회됨. variant 로 명시할 때만 동작):
  1) SELL_MA20_DOWN : 보유중 "당일 20일선 < 전일 20일선"(기울기 음전)이면 매도.
                      kospi1 의 손절/익절/트레일보다 **먼저** 평가한다.
     - plain      : 음전이면 무조건 매도(원안).
     - grace      : 평가수익 > MA20_GRACE_PROFIT_MIN 이면 매도 보류 →
                    트레일링(고점-3ATR)/익절에 위임. 상승 구간을 살리고 손실 구간만 자른다.
     - 2day       : **연속 2일** 음전일 때만 매도(1일 노이즈 음전 무시).
     - grace+2day : 위 둘 동시 적용.
     - plain+regime / grace+regime : kospi1 의 적응형 추세국면 분류기
       (downtrend_ratio = 최근 REGIME_WINDOW 봉 중 close<ema60 비율)가
       **하락국면(>= REGIME_THRESHOLD)** 일 때만 음전매도를 켠다. 상승국면에서는
       기존 손절/익절/트레일에 그대로 맡긴다.
       ※ downtrend_ratio 는 스캔 테이블(2026-06-01~)만으로는 90봉 lookback 이
         안 나오므로, 픽에 등장하는 종목(≈175개)의 일봉을 KIS 에서 받아
         라이브와 같은 식(rolling(90, min_periods=20))으로 계산하고
         REGIME_CACHE 에 캐시한다. 첫 실행은 종목당 1.5초 슬립으로 ~5분.
         --no-regime 을 주면 regime 계열 variant 를 건너뛴다.
  2) BUY_MA20_UP    : 시그널일 20일선이 전일보다 낮으면 매수 후보에서 제외.
  "20일선" = 스캔 테이블 ema20 컬럼(운영 코드가 sma20 이라 부르는 그 필드).
  --ma20 sma 를 주면 close 로 진짜 SMA20 을 계산해 쓴다(앞 19봉은 후보에서 빠짐).

평가 모드(--mode):
  independent (기본) : 거래일마다 그날의 픽을 **독립 트레이드**로 평가(중복보유 허용).
      거래일 수만큼 표본이 나온다(75일 → arm 당 최대 75건). 2026-09 세션이 인용한
      "승률 13.6%→22.7%" 류 수치와 같은 계열의 측정. 통계적 비교는 이쪽을 본다.
  sequential : 동시 보유 1종목 순차 복리(실전 trade_worker 와 동일 구조).
      현실적이지만 75거래일에 5~10건밖에 안 나와 승률 비교는 노이즈다.
      실전 체감 수익률(누적/MDD) 확인용으로만 쓴다.

체결/청산 규약 (KisBacktester.run_one 과 동일):
  - 시그널일 D 종가 기준 판단 → D+1 시초가 매수. 매도 시그널일 D' → D'+1 시초가 매도.
    (다음 봉이 없으면 당일 종가 체결)
  - 매도판단 = KospiStrategy1.get_action_in_active 를 **그대로 호출**(식 복제 금지).
    s1_* 옵션은 전부 None → kospi1 기본값(손절 -5%/익절 +30%/트레일 ATR3.0/타임스탑 12봉).
  - 진입 봉에서도 즉시 매도판정(bars_held=1 로 올린 뒤) — backtester 와 동일.
  - 왕복 수수료 = 2 * FEE_RATE.

픽 방식(arm):
  composite     : 그날 후보 pool 에서 proba top10 → 모멘텀 z-score 합성 재정렬 1위
                  (StockBuyCheckJob._compute_composite_top10 과 동일 식. 현 운영 기본값)
  proba_top1    : proba 최상위 1종목
  overheat_min  : 당일 등락률 최저 종목(기존 rank_no '과열최저' 근사 = 대조군)

재현 한계(정직하게 기록):
  · 스캔 테이블에 ema120 이 없어 _composite_eligible 의 "low > sma120" 장기추세
    필터는 빠졌다. 모든 arm/variant 에 동일하게 빠지므로 조건 2종의 delta 비교엔
    영향 없지만, 절대 승률은 실전보다 후하다.
  · 관리종목/거래정지는 stock_admin_status 의 **현재** 스냅샷(scan_admin_status.py)
    이다 — "당시에도 같은 상태였다"는 근사.
  · 배포 모델(shape_gbm_v1.joblib, 14피처)은 이 기간을 학습에 포함했을 수 있다
    (in-sample 가능성). --proba stored_old 로 9피처 구버전 값과 교차확인 가능.

━━━ 실행 결과 (모두 '채택 안 함'으로 종결. 철회 근거) ━━━━━━━━━━━━━━━━━━━━━━━━

2026-09-23 실행 ①(20일선 조건 2종 평가, mode=independent, 거래일 75일):
  · SELL_MA20_DOWN(기울기 음전 매도) — **구간별로 부호가 뒤집힌다**. composite arm 기준
    전반기(06-01~07-24) 승률 20.8%→37.5%(p=0.030, 개선), 후반기(07-25~09-16)
    52.8%→41.7%(p=0.002, 악화). 전체구간은 40.0%→40.0%, 평균수익 +0.52%→-0.20%.
    하락장에서 손실을 줄이고 상승장에서 수익을 깎는 '변동성 축소' 필터로 동작하며,
    평균 보유봉이 8.0→6.8(proba_top1 은 8.1→3.0)로 줄어 트레일/익절 기회를 먼저 끊는다.
    → 단독 승격 근거 없음. 국면(regime) 조건과 묶지 않으면 의미 없다.
  · BUY_MA20_UP(기울기 음수면 매수 제외) — composite arm 에서 **두 구간 모두 악화**
    (전체 40.0%→30.0%, p=0.006 / 전반기 p=0.028 / 후반기 p=0.060). 이유가 설명된다:
    composite 후보 필터가 이미 "ema20 > 14봉전 ema20"(중기 상승)을 요구하는데, 여기에
    일간 기울기 양수까지 걸면 shape 모델이 노리는 '눌림목 직후 반등 초입'
    (shape_recovery_from_min 계열)이 통째로 걸러진다. → 채택하면 안 된다.
  · 구버전 9피처 모델(--proba stored_old)과 진짜 SMA20(--ma20 sma)로 바꿔도 결론 동일.
  · 대조군 overheat_min 에서도 두 조건 다 개선 없음(승률 51.7% → 45.0% / 48.3%).

2026-09-23 실행 ②: 기울기음전 매도의 완화모드 2종(grace / 2day) 평가.
  proba_top1 arm, 60거래, 같은 픽·같은 진입일(매도규칙만 다름):
    모드          승률%  평균%  평균익%  평균손%  -5%초과손실  1봉청산  보유봉
    base          36.7  +1.25   13.95   -6.11      23건      4건    8.1
    plain         43.3  +0.52    6.69   -4.20       8건     39건    3.0
    grace         28.3  +0.68   12.91   -4.15      11건     22건    5.5
    2day          41.7  +0.63    7.56   -4.32      10건     37건    3.6
    grace+2day    30.0  +0.68   12.43   -4.35      13건     21건    5.7
  · **평균손실 축소는 네 모드 모두 전/후반기에서 재현된다**(base -7.93/-4.64 →
    grace -5.18/-3.42, plain -4.96/-3.66, 2day -5.22/-3.72). plain 의 승률 개선이
    구간별로 뒤집히던 것과 달리 이 효과는 방향이 안 바뀐다.
  · grace(이익 중이면 유예)는 설계 의도대로 **평균익을 지킨다**(12.91 vs plain 6.69,
    base 13.95). 케이아이엔엑스 -0.03%→+27.96%, 코디 +11.62%→+31.66% 등이 되살아난다.
  · 대가는 승률이다(36.7%→28.3%, 전/후반기 모두 하락). 손실 중 조기청산이 base 에서
    회복됐을 거래를 확정 손실로 만든다(현대지에프홀딩스 +4.97%→-6.72% 등).
  · 2day 는 1봉청산을 39→37건으로 거의 못 줄였다(음전이 이틀 이어지는 게 흔함).
    회전율 완화 목적이라면 grace 가 훨씬 효과적이다(39→22건).
2026-09-23 실행 ③: regime 게이트(하락국면에서만 음전매도) — **가설 기각**.
  kospi1 분류기(downtrend_ratio = 최근 90봉 중 close<ema60 비율, 임계 0.70) 기준.
  proba_top1 arm, 60거래:
    모드            승률%  평균%  평균익%  평균손%  -5%초과  -8%초과  1봉청산  보유봉  TREND발동
    base            36.7  +1.25   13.95   -6.11    23건    7건    4건   8.1     0
    plain           43.3  +0.52    6.69   -4.20     8건    3건   39건   3.0    51
    grace           28.3  +0.68   12.91   -4.15    11건    3건   22건   5.5    37
    plain+regime    36.7  +0.03   10.02   -5.76    20건    7건   17건   6.3    17
    grace+regime    33.3  +0.31   12.53   -5.80    21건    7건   11건   7.2    11
  · regime 게이트를 걸면 **손실 축소 효과가 거의 사라진다**(-5%초과 손실 8~11건 →
    20~21건, base 23건과 큰 차이 없음). 평균수익도 base 보다 낮아 얻는 게 없다.
  · 원인: 게이트가 **효과가 있던 구간에서 거의 안 켜진다**. 진입일 downtrend_ratio 가
    06월 0.42 → 07월 0.50 → 08월 0.63 → 09월 0.64 로 계속 올라가, '하락국면' 판정
    비율이 14% → 27% → 45% → 55%. 그래서 음전매도가 이득이던 전반기에는
    SELL_TREND 가 24건 중 3건만 발동하고(=base 와 거의 동일), 손해이던 후반기에는
    36건 중 14건 발동한다 — 가설과 정확히 반대로 켜진다.
  · 이유가 설명된다: downtrend_ratio 는 **종목 자신의 60일선 대비 장기 위치**를 재는
    지표다. proba 픽은 60일선 위에서 반등하는 모멘텀·눌림목 종목이라 직후에 깨지더라도
    ratio 가 낮게 나온다. 즉 이 분류기는 '다음 5~10봉의 하방 위험'을 대리하지 못한다.
    국면으로 스위칭하려면 시장(지수) 레벨 또는 단기 악화 지표를 따로 만들어야 한다.
  · composite arm 에서는 regime 게이트가 오히려 유의하게 악화(평균 +0.52% → -0.72%,
    p=0.008).

  · composite arm(운영 기본값)에서는 네 모드 전부 base 보다 나쁘다
    (평균 +0.52% → -0.19~-0.55%, -5%초과 손실도 26→25~29건으로 안 줄어든다).
    → 기울기 매도는 proba_top1 처럼 '단독 최상위 픽' 계열에서만 의미가 있다.

최종: 세 차례 실행 모두 채택 근거가 안 나왔고(승률 개선은 구간별로 부호가 뒤집히고,
  평균손실 축소는 재현되지만 평균익·기대값을 같은 폭으로 내주며, regime 스위칭은
  이득 구간에서 게이트가 안 켜진다), 2026-09-23 사용자 판단으로 가정 자체를 철회했다.
  → 운영(buy_order.py / kospi1.py / StockBuyCheckJob.py)에 반영된 것은 **없다**.
  후속으로 남은 아이디어(미검증): 종목별 분류기 대신 **지수 레벨 국면**으로 스위칭.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

수동 실행:
    cd py-project/py-stock-batch
    ./.venv/bin/python3 -m app.test.eval_shape_proba                      # 전체 arm x variant
    ./.venv/bin/python3 -m app.test.eval_shape_proba --mode sequential
    ./.venv/bin/python3 -m app.test.eval_shape_proba --ma20 sma
    ./.venv/bin/python3 -m app.test.eval_shape_proba --proba stored_old
    ./.venv/bin/python3 -m app.test.eval_shape_proba --arm composite --trades
"""
import argparse
import math
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import Action
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.ml.shape_label import LABEL_WIN_THRESHOLD_PCT
from stock_shared.ml.shape_features import (
    SHAPE_FEATURE_COLUMNS,
    EXHAUSTION_BARS_SINCE_MIN_MIN,
    EXHAUSTION_TOTAL_RET_14_MIN,
    EXHAUSTION_RET_1D_TODAY_MIN,
)

DB_URL = 'mysql+pymysql://stock:stock123!!@210.103.60.108:3333/stock'

FEE_RATE = 0.0011          # 편도. 왕복 2배 차감 (sim_buy_target.py 와 동일)
INIT_CASH = 1_000_000

# ── 2단계 후보 안정성 필터 (StockBuyCheckJob 상수 그대로) ──────────────
COMPOSITE_TOP_N = 10
COMPOSITE_PENNY_PRICE_MIN = 1000
COMPOSITE_EXTREME_MOVE_PCT = 15.0
COMPOSITE_EXTREME_LOOKBACK = 10
COMPOSITE_ATR_RATIO_MAX = 0.10
COMPOSITE_SMA20_TREND_BARS = 14
COMPOSITE_MOMENTUM_COLS = ['obv_gap_norm', 'obv_slope3', 'ind_vol_ratio_today', 'ind_macd_hist_norm']

# 기울기 음전 매도 'grace' 모드: 평가수익이 이 값을 넘으면 매도를 보류하고
# kospi1 의 트레일링/익절에 위임한다(0.0 = 이익 중이면 무조건 유예).
MA20_GRACE_PROFIT_MIN = 0.0

# 추세국면 분류기 — KisStockService.compute_indicator_df / KisBacktester 와 동일 식.
#   ema60 은 이름만 ema 이고 실제로는 60봉 단순이동평균(rolling(60).mean()).
REGIME_WINDOW = 90
REGIME_MIN_PERIODS = 20
REGIME_THRESHOLD = 0.70        # kospi1.regime_threshold 와 동일
REGIME_CACHE = os.path.join(os.path.dirname(__file__), 'regime_cache.csv')
REGIME_FETCH_SLEEP = 1.5

# net_edge 라벨 승리 기준 — stock_shared.ml.shape_label 단일 출처를 쓴다(식 복제 금지).
LABEL_WIN_THRESHOLD = LABEL_WIN_THRESHOLD_PCT

SELL_ACTIONS = {Action.SELL_PROFIT, Action.SELL_STOP_LOSS, Action.SELL_STOP_PROFIT,
                Action.SELL_TRAIL, Action.SELL_TIME}

STORED_SHAPE_COLS = [
    'shape_total_ret_14', 'shape_min_ret_14', 'shape_bars_since_min',
    'shape_recovery_from_min', 'shape_early_ret_9', 'shape_late_ret_5',
    'shape_down_ratio_14', 'shape_path_std_14', 'shape_vol_trend',
    'ind_rsi14', 'ind_macd_hist_norm', 'ind_vol_ratio_today',
]

# variant 이름 → (기울기음전 매도모드, 기울기음수 매수제외)
#   매도모드: None | 'plain' | 'grace' | '2day' | 'grace+2day'
VARIANTS = {
    'base':        (None,         False),
    'sell_ma20':   ('plain',      False),
    'sell_grace':  ('grace',      False),   # ① 수익 중이면 유예
    'sell_2day':   ('2day',       False),   # ② 연속 2일 음전만
    'sell_g2':     ('grace+2day', False),   # ①+②
    'sell_regime': ('plain+regime', False), # ③ 하락국면에서만 음전매도
    'sell_rg':     ('grace+regime', False), # ③+① 하락국면 + 이익중 유예
    'buy_ma20':    (None,         True),
    'both':        ('plain',      True),
}
ARMS = ['composite', 'proba_top1', 'overheat_min']


# ══════════════════════════════════════════════════════════════════
# 데이터 적재 + 파생
# ══════════════════════════════════════════════════════════════════
def load_data(engine) -> pd.DataFrame:
    cols = ['coin', 'datetime', 'open', 'high', 'low', 'close', 'volume',
            'ema20', 'ema60', 'macd', 'macd_s', 'rsi', 'atr', 'vol_avg',
            'shape_proba_old', 'shape_proba_new', 'net_edge_fwd'] + STORED_SHAPE_COLS
    sql = f"SELECT {', '.join(cols)} FROM trade_shape_scan_stock ORDER BY coin, datetime"
    df = pd.read_sql(text(sql), engine)
    for c in cols:
        if c not in ('coin', 'datetime'):
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df['datetime'] = df['datetime'].str[:10]

    admin = pd.read_sql(text(
        "SELECT coin, mang_issu_cls_code, temp_stop_yn FROM stock_admin_status"), engine)
    admin['admin_bad'] = (
        admin['mang_issu_cls_code'].fillna('N').str.upper().eq('Y')
        | admin['temp_stop_yn'].fillna('N').str.upper().eq('Y')
    )
    df = df.merge(admin[['coin', 'admin_bad']], on='coin', how='left')
    df['admin_bad'] = df['admin_bad'].fillna(False).astype(bool)

    names = pd.read_sql(text(
        "SELECT stock_code AS coin, stock_name, stock_type FROM master_stock"), engine)
    df = df.merge(names.drop_duplicates('coin'), on='coin', how='left')
    df['stock_name'] = df['stock_name'].fillna('')
    df['stock_type'] = df['stock_type'].fillna('')
    return df


def derive(df: pd.DataFrame, ma20_kind: str) -> pd.DataFrame:
    """종목별 파생 컬럼. 전부 벡터 연산(groupby)."""
    g = df.groupby('coin', sort=False)

    df['ret_1d'] = g['close'].pct_change()
    df['next_open'] = g['open'].shift(-1)

    # OBV 파생 — 누적 OBV 의 임의 기준점은 두 식(차분/기울기) 모두에서 상쇄되므로
    # 스캔 구간(2026-06~)만으로도 정확히 재현된다(obv_signal 9봉, slope 3봉 lookback).
    sign = np.sign(df['close'].diff())
    sign[g.cumcount().values == 0] = 0.0
    df['_obv_step'] = (sign * df['volume']).fillna(0.0)
    df['obv'] = df.groupby('coin', sort=False)['_obv_step'].cumsum()
    df['obv_signal'] = df.groupby('coin', sort=False)['obv'].transform(
        lambda s: s.rolling(9).mean())
    df['obv_gap_norm'] = (df['obv'] - df['obv_signal']) / (df['vol_avg'] + 1e-9)
    df['obv_slope3'] = (df['obv'] - df.groupby('coin', sort=False)['obv'].shift(3)) \
        / (df['vol_avg'] * 3 + 1e-9)

    # ── 20일선 + 기울기 ──────────────────────────────────────────
    if ma20_kind == 'sma':
        df['ma20'] = df.groupby('coin', sort=False)['close'].transform(
            lambda s: s.rolling(20).mean())
    else:
        df['ma20'] = df['ema20']
    df['ma20_prev'] = df.groupby('coin', sort=False)['ma20'].shift(1)
    df['ma20_slope_up'] = (df['ma20'] > df['ma20_prev']).fillna(False).astype(bool)
    df['ma20_slope_down'] = (df['ma20'] < df['ma20_prev']).fillna(False).astype(bool)
    # 연속 2일 음전(오늘 + 전일 모두 음전). 첫 봉은 전일값이 없어 False.
    df['ma20_slope_down2'] = (
        df['ma20_slope_down']
        & df.groupby('coin', sort=False)['ma20_slope_down'].shift(1).fillna(False).astype(bool)
    )

    # 2단계 필터용
    df['ema20_trend_prev'] = df.groupby('coin', sort=False)['ema20'].shift(COMPOSITE_SMA20_TREND_BARS)
    df['atr_ratio'] = df['atr'] / df['close']
    df['ext_move_max'] = df.groupby('coin', sort=False)['ret_1d'].transform(
        lambda s: s.abs().rolling(COMPOSITE_EXTREME_LOOKBACK, min_periods=1).max())
    df.drop(columns=['_obv_step'], inplace=True)
    return df


def attach_proba(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """proba 컬럼 부착. live=배포 아티팩트로 재추론(14피처), stored_*=스캔 당시 저장값."""
    if mode in ('stored_new', 'stored_old'):
        df['proba'] = df['shape_proba_new' if mode == 'stored_new' else 'shape_proba_old']
        print(f"[proba] 스캔 저장값 사용({mode}): {int(df['proba'].notna().sum())}/{len(df)}행",
              flush=True)
        return df

    import joblib
    path = os.path.join(os.path.dirname(__file__), '..', '..', '..',
                        'shared', 'stock_shared', 'ml', 'artifacts', 'shape_gbm_v1.joblib')
    model = joblib.load(os.path.normpath(path))
    if getattr(model, 'n_features_in_', None) != len(SHAPE_FEATURE_COLUMNS):
        raise RuntimeError(
            f"모델 피처수({model.n_features_in_}) != SHAPE_FEATURE_COLUMNS"
            f"({len(SHAPE_FEATURE_COLUMNS)}) — 아티팩트/코드 버전 불일치")

    X = df[SHAPE_FEATURE_COLUMNS].astype(float)
    ok = X.notna().all(axis=1)
    df['proba'] = np.nan
    if ok.any():
        df.loc[ok, 'proba'] = model.predict_proba(X[ok].values)[:, 1]
    print(f"[proba] 배포모델 재추론: {int(ok.sum())}/{len(df)}행 "
          f"({len(SHAPE_FEATURE_COLUMNS)}피처)", flush=True)
    return df


def load_regime(codes: set, end_date: str, cache_path: str = REGIME_CACHE) -> pd.DataFrame:
    """종목별 downtrend_ratio(일자별)를 돌려준다. 캐시 없으면 KIS 에서 받아 채운다.

    라이브(compute_indicator_df)와 동일:
        ema60 = close.rolling(60).mean()
        below = (close < ema60).where(ema60.notna())
        downtrend_ratio = below.rolling(90, min_periods=20).mean()
    스캔 구간(2026-06-01~)만으로는 90봉 창이 안 채워지므로 KIS 에서 1년치를 받아
    계산한 뒤 스캔 구간만 잘라 캐시한다.
    """
    cached = pd.DataFrame(columns=['coin', 'datetime', 'downtrend_ratio'])
    if os.path.exists(cache_path):
        cached = pd.read_csv(cache_path, dtype={'coin': str})
        print(f"[regime] 캐시 {cache_path}: {len(cached)}행 / "
              f"{cached['coin'].nunique()}종목", flush=True)

    missing = sorted(codes - set(cached['coin'].unique()))
    if missing:
        import time
        from app.ext_services.kis.KisEngine import KisEngine
        kis = KisEngine()
        print(f"[regime] KIS 조회 필요 {len(missing)}종목 "
              f"(종목당 {REGIME_FETCH_SLEEP}초 → 약 {len(missing)*REGIME_FETCH_SLEEP/60:.1f}분)",
              flush=True)
        rows, fail = [], 0
        for n, code in enumerate(missing, 1):
            try:
                time.sleep(REGIME_FETCH_SLEEP)
                o = kis.get_daily_ohlcv(code, '2025-06-01', end_date, min_days=250)
                if o is None or len(o) < REGIME_MIN_PERIODS:
                    fail += 1
                    continue
                o = o.copy()
                o['datetime'] = pd.to_datetime(o['datetime']).dt.strftime('%Y-%m-%d')
                close = o['close'].astype(float)
                ema60 = close.rolling(60).mean()
                below = (close < ema60).where(ema60.notna())
                o['downtrend_ratio'] = below.rolling(
                    REGIME_WINDOW, min_periods=REGIME_MIN_PERIODS).mean()
                o = o.dropna(subset=['downtrend_ratio'])
                for dt, v in zip(o['datetime'], o['downtrend_ratio']):
                    rows.append({'coin': code, 'datetime': dt, 'downtrend_ratio': round(float(v), 4)})
                if n % 20 == 0 or n == len(missing):
                    print(f"[regime] {n}/{len(missing)} (실패 {fail})", flush=True)
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"[regime] {code} 실패: {e}", flush=True)
        if rows:
            cached = pd.concat([cached, pd.DataFrame(rows)], ignore_index=True)
            cached.drop_duplicates(['coin', 'datetime'], keep='last').to_csv(cache_path, index=False)
            print(f"[regime] 캐시 갱신 → {cache_path} ({len(cached)}행)", flush=True)

    return cached[['coin', 'datetime', 'downtrend_ratio']]


def mark_eligible(df: pd.DataFrame) -> pd.DataFrame:
    """_composite_eligible 재현(ema120 필터 제외 — 모듈 docstring 참고)."""
    exhaustion = (
        (df['shape_bars_since_min'] >= EXHAUSTION_BARS_SINCE_MIN_MIN)
        & (df['shape_total_ret_14'] >= EXHAUSTION_TOTAL_RET_14_MIN)
        & (df['ret_1d'] >= EXHAUSTION_RET_1D_TODAY_MIN)
    ).fillna(False)

    df['eligible'] = (
        ~df['admin_bad']
        & (df['close'] >= COMPOSITE_PENNY_PRICE_MIN)
        & (df['ema20'] > df['ema20_trend_prev'])
        & (df['atr_ratio'] <= COMPOSITE_ATR_RATIO_MAX)
        & (df['ext_move_max'] * 100 < COMPOSITE_EXTREME_MOVE_PCT)
        & ~exhaustion
        & df['proba'].notna()
        & df['next_open'].notna()
        & df[COMPOSITE_MOMENTUM_COLS + ['ind_rsi14']].notna().all(axis=1)
    ).fillna(False).astype(bool)
    return df


# ══════════════════════════════════════════════════════════════════
# 픽
# ══════════════════════════════════════════════════════════════════
def _zscore(s: pd.Series) -> pd.Series:
    std = s.std()
    return (s - s.mean()) / std if std and std > 0 else s * 0.0


def pick(pool: pd.DataFrame, arm: str):
    """그날 후보 pool 에서 1종목 선택. 반환 row(Series) 또는 None."""
    if pool.empty:
        return None

    if arm == 'proba_top1':
        return pool.sort_values(['proba', 'coin'], ascending=[False, True]).iloc[0]

    if arm == 'overheat_min':
        p = pool.dropna(subset=['ret_1d'])
        if p.empty:
            return None
        return p.sort_values(['ret_1d', 'coin'], ascending=[True, True]).iloc[0]

    # composite: z-score 는 top10 으로 좁히기 **전** pool 전체 기준 (운영과 동일)
    p = pool.copy()
    for col in COMPOSITE_MOMENTUM_COLS:
        p[f'z_{col}'] = _zscore(p[col])
    p['z_rsi_centered'] = _zscore(p['ind_rsi14'] - 50)
    z_cols = [f'z_{c}' for c in COMPOSITE_MOMENTUM_COLS] + ['z_rsi_centered']
    p['momentum_composite'] = p[z_cols].mean(axis=1)

    top = p.sort_values(['proba', 'coin'], ascending=[False, True]).head(COMPOSITE_TOP_N)
    return top.sort_values(['momentum_composite', 'coin'], ascending=[False, True]).iloc[0]


# ══════════════════════════════════════════════════════════════════
# 단일 트레이드 실행 (independent / sequential 공용)
# ══════════════════════════════════════════════════════════════════
def _base_user_info() -> UserOptionMeta:
    """s1_* 전부 None → kospi1 기본값(손절 -5%/익절 +30%/트레일ATR3.0/타임스탑 12봉)."""
    ui = UserOptionMeta()
    ui.vol_limit = 0
    ui.vol_surge = 3.0
    ui.delay_date = 5
    ui.macd_recent_day = 20
    ui.bb_over_recent_day = 7
    ui.has_position = False
    ui.avg_price = ui.entry_price = ui.entry_atr = ui.peak_high = ui.peak_close = 0.0
    ui.bars_since_peak = 0
    ui.bars_held = 0
    return ui


def _ma20_sell_triggered(r: dict, sell_mode, entry_price: float) -> bool:
    """기울기 음전 매도 발동 여부. sell_mode 별 완화조건 적용."""
    if not sell_mode:
        return False
    two_day = '2day' in sell_mode
    if not bool(r['ma20_slope_down2'] if two_day else r['ma20_slope_down']):
        return False
    if 'regime' in sell_mode:
        # 하락국면(downtrend_ratio >= 임계값)에서만 발동. 상승국면은 기존 청산에 맡긴다.
        dr = r.get('downtrend_ratio')
        if dr is None or pd.isna(dr) or float(dr) < REGIME_THRESHOLD:
            return False
    if 'grace' in sell_mode:
        close = float(r['close'] or 0)
        if entry_price > 0 and (close - entry_price) / entry_price > MA20_GRACE_PROFIT_MIN:
            return False          # 이익 중 → 트레일링/익절에 위임
    return True


def run_one_trade(strategy, recs: list, i_sig: int, sell_mode) -> dict | None:
    """시그널 봉 인덱스 i_sig → i_sig+1 시초가 진입 후 청산까지 1트레이드 실행."""
    if i_sig + 1 >= len(recs):
        return None
    er = recs[i_sig + 1]
    entry_price = float(er['open'] or 0) or float(er['close'] or 0)
    if entry_price <= 0:
        return None

    ui = _base_user_info()
    ui.has_position = True
    ui.avg_price = ui.entry_price = entry_price
    ui.entry_atr = float(er['atr'] or 0)
    ui.peak_high = float(er['high'] or entry_price)
    ui.peak_close = float(er['close'] or entry_price)

    for i in range(i_sig + 1, len(recs)):
        r = recs[i]
        prev_r = recs[i - 1] if i > 0 else r

        # 보유 봉 상태 갱신 (진입 봉 포함 — backtester.run_one 과 동일)
        prev_peak = ui.peak_high
        ui.peak_high = max(ui.peak_high, float(r['high'] or 0))
        ui.peak_close = max(ui.peak_close, float(r['close'] or 0))
        ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
        ui.bars_held += 1

        action = None
        # ★ 20일선 기울기 음전 → 최우선 매도 (모드별 완화조건은 헬퍼에서 판정)
        if _ma20_sell_triggered(r, sell_mode, entry_price):
            action = Action.SELL_TREND
        else:
            res = strategy.get_action_in_active(
                UserCoinInfo.from_dict(prev_r), UserCoinInfo.from_dict(r), ui)
            ra = (res or {}).get('result_action')
            if isinstance(ra, Action) and ra in SELL_ACTIONS:
                action = ra

        if action is None:
            continue

        if i + 1 < len(recs):
            nr = recs[i + 1]
            exit_price = float(nr['open'] or nr['close'])
            exit_dt = nr['datetime']
        else:
            exit_price = float(r['close'])
            exit_dt = r['datetime']
        gross = (exit_price - entry_price) / entry_price
        return {'coin': r['coin'], 'name': r.get('stock_name', ''),
                'market': r.get('stock_type', ''), 'signal_dt': recs[i_sig]['datetime'],
                'entry_dt': er['datetime'], 'entry_price': entry_price,
                'exit_dt': exit_dt, 'exit_price': exit_price, 'reason': action.name,
                'bars_held': ui.bars_held, 'ret_gross': gross,
                'ret_net': gross - 2 * FEE_RATE,
                'net_edge_fwd': recs[i_sig].get('net_edge_fwd')}

    # 데이터 끝까지 미청산 → 마크투마켓
    last = recs[-1]
    gross = (float(last['close']) - entry_price) / entry_price
    return {'coin': last['coin'], 'name': last.get('stock_name', ''),
            'market': last.get('stock_type', ''), 'signal_dt': recs[i_sig]['datetime'],
            'entry_dt': er['datetime'], 'entry_price': entry_price,
            'exit_dt': last['datetime'], 'exit_price': float(last['close']),
            'reason': 'OPEN_MTM', 'bars_held': ui.bars_held, 'ret_gross': gross,
            'ret_net': gross - 2 * FEE_RATE,
            'net_edge_fwd': recs[i_sig].get('net_edge_fwd')}


# ══════════════════════════════════════════════════════════════════
# 두 가지 평가 모드
# ══════════════════════════════════════════════════════════════════
def build_index(df: pd.DataFrame):
    rows_by_coin, idx_by_coin = {}, {}
    for coin, sub in df.groupby('coin', sort=False):
        recs = sub.to_dict('records')
        rows_by_coin[coin] = recs
        idx_by_coin[coin] = {r['datetime']: i for i, r in enumerate(recs)}
    return rows_by_coin, idx_by_coin


def daily_picks(df: pd.DataFrame, dates: list, arm: str, buy_ma20_up: bool) -> dict:
    """거래일 → 그날의 픽 row. 두 모드가 같은 픽 로직을 쓰도록 분리."""
    cand = df[df['eligible'] & df['datetime'].isin(set(dates))]
    if buy_ma20_up:                       # ★ 조건② 기울기 음수면 후보 제외
        cand = cand[cand['ma20_slope_up']]
    out = {}
    for d, pool in cand.groupby('datetime', sort=False):
        row = pick(pool, arm)
        if row is not None:
            out[d] = row
    return out


def eval_independent(rows_by_coin, idx_by_coin, picks: dict, dates: list,
                     sell_mode) -> dict:
    """거래일마다 그날의 픽을 독립 트레이드로 평가(중복보유 허용)."""
    strategy = KospiStrategy1()
    trades = []
    for d in dates:
        row = picks.get(d)
        if row is None:
            continue
        coin = row['coin']
        i = idx_by_coin[coin].get(d)
        if i is None:
            continue
        t = run_one_trade(strategy, rows_by_coin[coin], i, sell_mode)
        if t:
            trades.append(t)
    return {'trades': trades, 'mode': 'independent'}


def eval_sequential(rows_by_coin, idx_by_coin, picks: dict, dates: list,
                    sell_mode, all_dates: list = None) -> dict:
    """동시 보유 1종목 순차 복리. 매도한 날은 그날 바로 재탐색(실전 _open_routine 정책)."""
    strategy = KospiStrategy1()
    all_dates = all_dates or dates
    trades = []
    cash = float(INIT_CASH)
    busy_until = None       # 이 날짜(포함)까지는 보유중 → 신규 시그널 무시
    for d in dates:
        if busy_until is not None and d <= busy_until:
            continue
        row = picks.get(d)
        if row is None:
            continue
        coin = row['coin']
        i = idx_by_coin[coin].get(d)
        if i is None:
            continue
        t = run_one_trade(strategy, rows_by_coin[coin], i, sell_mode)
        if not t:
            continue
        cash *= (1 + t['ret_net'])
        t = dict(t, cash=cash)
        trades.append(t)
        # 청산일(exit_dt) 당일에 바로 새 시그널을 받을 수 있게(실전 _open_routine 의
        # 매도직후 재매수 정책) exit 직전 거래일까지만 잠근다.
        prev_dates = [x for x in all_dates if x < t['exit_dt']]
        busy_until = prev_dates[-1] if prev_dates else d
    return {'trades': trades, 'mode': 'sequential', 'final_cash': cash}


# ══════════════════════════════════════════════════════════════════
# 집계
# ══════════════════════════════════════════════════════════════════
def _wilson(k: int, n: int, z: float = 1.96):
    """승률 95% 신뢰구간(Wilson). 표본 적을 때 정규근사보다 안전."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d * 100, (c + h) / d * 100)


def summarize(res: dict) -> dict:
    t = res['trades']
    n = len(t)
    if n == 0:
        return {'trades': 0}
    rets = np.array([x['ret_net'] for x in t])
    wins = rets > 0
    lo, hi = _wilson(int(wins.sum()), n)
    label = np.array([x['net_edge_fwd'] for x in t], dtype=float)
    label_ok = ~np.isnan(label)

    out = {
        'trades': n,
        'win_rate': float(wins.mean()) * 100,
        'ci': (lo, hi),
        'avg_ret': float(rets.mean()) * 100,
        'med_ret': float(np.median(rets)) * 100,
        'avg_win': float(rets[wins].mean()) * 100 if wins.any() else 0.0,
        'avg_loss': float(rets[~wins].mean()) * 100 if (~wins).any() else 0.0,
        'avg_bars': float(np.mean([x['bars_held'] for x in t])),
        'label_avg': float(label[label_ok].mean()) if label_ok.any() else float('nan'),
        'label_win': float((label[label_ok] >= LABEL_WIN_THRESHOLD).mean()) * 100
                     if label_ok.any() else float('nan'),
    }
    if res['mode'] == 'sequential':
        eq = np.concatenate([[INIT_CASH], np.array([x['cash'] for x in t])])
        peak = np.maximum.accumulate(eq)
        out['total_ret'] = (res['final_cash'] / INIT_CASH - 1) * 100
        out['mdd'] = float(((eq - peak) / peak).min()) * 100
    return out


def paired_bootstrap(base: list, var: list, iters: int = 5000, seed: int = 7) -> float:
    """같은 시그널일에 대응하는 트레이드끼리 짝지어 평균수익 차이의 p-value(양측) 근사."""
    b = {t['signal_dt']: t['ret_net'] for t in base}
    v = {t['signal_dt']: t['ret_net'] for t in var}
    common = sorted(set(b) & set(v))
    if len(common) < 5:
        return float('nan')
    d = np.array([v[k] - b[k] for k in common])
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, len(d), size=(iters, len(d)))].mean(axis=1)
    obs = d.mean()
    if obs == 0:
        return 1.0
    p = (means * np.sign(obs) <= 0).mean() * 2
    return float(min(1.0, p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', choices=ARMS + ['all'], default='all')
    # 기본값 base = ma20 조건 전부 꺼진 순수 proba 백테스트(가정 철회 반영).
    # 철회된 조건들을 다시 보려면 --variant all 또는 개별 이름으로 명시해야 한다.
    ap.add_argument('--variant', choices=list(VARIANTS) + ['all'], default='base')
    ap.add_argument('--mode', choices=['independent', 'sequential', 'both'], default='both')
    ap.add_argument('--ma20', choices=['ema', 'sma'], default='ema',
                    help="20일선 정의. ema=스캔테이블 ema20(운영과 동일), sma=close 단순평균20")
    ap.add_argument('--proba', choices=['live', 'stored_new', 'stored_old'], default='live')
    ap.add_argument('--start', default=None)
    ap.add_argument('--end', default=None)
    ap.add_argument('--trades', action='store_true', help='매매로그 출력')
    ap.add_argument('--no-regime', action='store_true',
                    help='regime 계열 variant 건너뛰기(KIS 조회 안 함)')
    ap.add_argument('--regime-cache', default=REGIME_CACHE)
    args = ap.parse_args()

    retracted = [v for v in (list(VARIANTS) if args.variant == 'all' else [args.variant])
                 if v != 'base']
    if retracted:
        print(f"[주의] ma20 기울기 계열 variant({', '.join(retracted)})는 2026-09-23 "
              f"철회된 가정이다. 파일 상단 '실행 결과' 블록을 먼저 확인할 것.", flush=True)

    engine = create_engine(DB_URL, pool_pre_ping=True)
    print("[1/4] 스캔 데이터 적재...", flush=True)
    df = load_data(engine)
    print(f"      {len(df)}행 / {df['coin'].nunique()}종목 / "
          f"{df['datetime'].min()}~{df['datetime'].max()}", flush=True)

    print("[2/4] 파생 계산...", flush=True)
    df = derive(df, args.ma20)
    df = attach_proba(df, args.proba)
    df = mark_eligible(df)

    # --start/--end 는 **시그널 기간**만 제한한다. 데이터는 통째로 남겨서
    # 기간 끝에 걸린 포지션도 정상 청산되게 한다(구간 분할 안정성 검증용).
    all_dates = sorted(df['datetime'].unique())
    dates = [d for d in all_dates
             if (not args.start or d >= args.start) and (not args.end or d <= args.end)]
    sig_set = set(dates)
    per_day = df[df['eligible'] & df['datetime'].isin(sig_set)].groupby('datetime').size()
    dn = df[df['eligible'] & df['ma20_slope_down'] & df['datetime'].isin(sig_set)] \
        .groupby('datetime').size().reindex(
        per_day.index, fill_value=0)
    print(f"[3/4] 후보 {int(per_day.sum())}행 / 시그널 거래일 {len(dates)}일 / "
          f"일평균 후보 {per_day.mean():.0f}종목 "
          f"(그중 20일선 기울기 음수 {(dn.sum()/per_day.sum()*100):.1f}%)", flush=True)

    arms = ARMS if args.arm == 'all' else [args.arm]
    variants = list(VARIANTS) if args.variant == 'all' else [args.variant]
    modes = ['independent', 'sequential'] if args.mode == 'both' else [args.mode]

    # ── 픽을 먼저 확정한다(픽은 매수필터에만 의존 → 매도모드와 무관) ──────
    picks_cache = {}
    for arm in arms:
        for v in variants:
            _, buy_up = VARIANTS[v]
            key = (arm, v)
            if key not in picks_cache:
                picks_cache[key] = daily_picks(df, dates, arm, buy_up)
        if ('base') not in variants:
            bkey = (arm, 'base')
            if bkey not in picks_cache:
                picks_cache[bkey] = daily_picks(df, dates, arm, False)

    # ── regime 계열 variant 가 있으면 downtrend_ratio 를 붙인다 ──────────
    regime_variants = [v for v in variants if (VARIANTS[v][0] or '').find('regime') >= 0]
    if regime_variants and args.no_regime:
        print(f"[regime] --no-regime → {', '.join(regime_variants)} 건너뜀", flush=True)
        variants = [v for v in variants if v not in regime_variants]
    elif regime_variants:
        codes = {r['coin'] for pk in picks_cache.values() for r in pk.values()}
        reg = load_regime(codes, all_dates[-1], args.regime_cache)
        df = df.merge(reg, on=['coin', 'datetime'], how='left')
        hit = df['coin'].isin(codes)
        cov = df.loc[hit, 'downtrend_ratio']
        print(f"[regime] 픽 종목 {len(codes)}개 / downtrend_ratio 매칭 "
              f"{int(cov.notna().sum())}/{int(hit.sum())}행, "
              f"그중 하락국면(>= {REGIME_THRESHOLD}) "
              f"{(cov >= REGIME_THRESHOLD).sum() / max(1, cov.notna().sum()) * 100:.1f}%",
              flush=True)
    else:
        df['downtrend_ratio'] = np.nan

    if 'downtrend_ratio' not in df.columns:
        df['downtrend_ratio'] = np.nan
    rows_by_coin, idx_by_coin = build_index(df)

    print(f"[4/4] 시뮬레이션 (20일선={args.ma20}, proba={args.proba}, "
          f"kospi1 기본 손절-5%/익절+30%/트레일ATR3/타임스탑12봉, "
          f"진입=다음날시가, 왕복수수료 {2*FEE_RATE*100:.2f}%)", flush=True)

    results = {}
    base_ref = {}       # (mode, arm) → base 트레이드 목록(variant 목록에 base 가 없어도 채운다)
    for mode in modes:
        print(f"\n{'='*118}\n■ mode = {mode}\n{'='*118}")
        hdr = (f"{'arm':<13}{'variant':<13}{'거래':>5}{'승률%':>8}{'승률95%CI':>16}"
               f"{'평균%':>8}{'중앙%':>8}{'평균익%':>9}{'평균손%':>9}{'보유봉':>7}")
        if mode == 'sequential':
            hdr += f"{'누적%':>9}{'MDD%':>8}"
        else:
            hdr += f"{'라벨승률%':>10}{'라벨netedge':>12}{'vs base p':>11}"
        print(hdr)
        print('-' * len(hdr))

        for arm in arms:
            # p-value 기준선. base 를 variant 목록에서 빼고 돌려도 비교는 가능해야 한다.
            if ('base') not in variants:
                bkey = (arm, 'base')
                if bkey not in picks_cache:
                    picks_cache[bkey] = daily_picks(df, dates, arm, False)
                base_trades = (eval_independent if mode == 'independent' else eval_sequential)(
                    rows_by_coin, idx_by_coin, picks_cache[bkey], dates, None)['trades']
                base_ref[(mode, arm)] = base_trades
            else:
                base_trades = None
            for v in variants:
                sell_mode, buy_ma20 = VARIANTS[v]
                key = (arm, v)
                if key not in picks_cache:
                    picks_cache[key] = daily_picks(df, dates, arm, buy_ma20)
                picks = picks_cache[key]
                if mode == 'independent':
                    res = eval_independent(rows_by_coin, idx_by_coin, picks, dates, sell_mode)
                else:
                    res = eval_sequential(rows_by_coin, idx_by_coin, picks, dates, sell_mode,
                                          all_dates=all_dates)
                s = summarize(res)
                results[(mode, arm, v)] = (res, s)
                if v == 'base':
                    base_trades = res['trades']
                    base_ref[(mode, arm)] = base_trades

                if s['trades'] == 0:
                    print(f"{arm:<13}{v:<13}{0:>5}   (거래 없음)")
                    continue
                ci_txt = '[%.0f~%.0f]' % s['ci']
                line = (f"{arm:<13}{v:<13}{s['trades']:>5}{s['win_rate']:>8.1f}{ci_txt:>16}"
                        f"{s['avg_ret']:>8.2f}{s['med_ret']:>8.2f}"
                        f"{s['avg_win']:>9.2f}{s['avg_loss']:>9.2f}{s['avg_bars']:>7.1f}")
                if mode == 'sequential':
                    line += f"{s['total_ret']:>9.2f}{s['mdd']:>8.2f}"
                else:
                    p = (paired_bootstrap(base_trades, res['trades'])
                         if (v != 'base' and base_trades) else float('nan'))
                    line += (f"{s['label_win']:>10.1f}{s['label_avg']:>12.2f}"
                             + (f"{p:>11.3f}" if not math.isnan(p) else f"{'-':>11}"))
                print(line)
            print()

    print("\n[매도사유 분포]")
    for (mode, arm, v), (res, s) in results.items():
        if not res['trades']:
            continue
        c = defaultdict(int)
        for t in res['trades']:
            c[t['reason']] += 1
        print(f"  {mode:<12}{arm:<13}{v:<13}" + ", ".join(f"{k}={n}" for k, n in sorted(c.items())))

    if args.trades:
        for (mode, arm, v), (res, s) in results.items():
            base_map = {t['signal_dt']: t for t in base_ref.get((mode, arm), [])}
            print(f"\n[매매로그] {mode} / {arm} / {v}   (거래 {s['trades']}건, "
                  f"승률 {s['win_rate']:.1f}%, 평균 {s['avg_ret']:+.2f}%, "
                  f"평균손 {s['avg_loss']:+.2f}%)")
            h = (f"{'#':>3}  {'시그널일':<11}{'진입일':<11}{'코드':<7}{'종목명':<15}"
                 f"{'시장':<7}{'진입가':>10}  {'청산일':<11}{'청산가':>10}{'보유':>5}"
                 f"{'순수익%':>9}   {'매도사유':<16}")
            if v != 'base':
                h += f"{'base수익%':>10}"
            print('  ' + h)
            print('  ' + '-' * len(h))
            for n, t in enumerate(res['trades'], 1):
                nm = (t.get('name') or '')[:12]
                pad = 15 - sum(2 if ord(ch) > 0x2000 else 1 for ch in nm)
                line = (f"{n:>3}  {t['signal_dt']:<11}{t['entry_dt']:<11}{t['coin']:<7}"
                        f"{nm}{' ' * max(1, pad)}{(t.get('market') or ''):<7}"
                        f"{t['entry_price']:>10,.0f}  {t['exit_dt']:<11}"
                        f"{t['exit_price']:>10,.0f}{t['bars_held']:>5}"
                        f"{t['ret_net']*100:>+9.2f}   {t['reason']:<16}")
                if v != 'base':
                    b = base_map.get(t['signal_dt'])
                    line += f"{(b['ret_net']*100):>+10.2f}" if b else f"{'-':>10}"
                print('  ' + line)
            losses = [x['ret_net'] * 100 for x in res['trades'] if x['ret_net'] <= 0]
            if losses:
                print(f"    → 손실거래 {len(losses)}건, 평균 {np.mean(losses):+.2f}%, "
                      f"최악 {min(losses):+.2f}%, -5% 초과손실 {sum(1 for x in losses if x < -5)}건")


if __name__ == '__main__':
    main()
