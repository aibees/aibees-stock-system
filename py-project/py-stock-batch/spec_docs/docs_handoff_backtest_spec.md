# 요청 명세: trade_candle_data 적재 + Strategy 백테스트 재구현

> **수신**: Flask web server 개발 담당 session
> **발신**: py-stock-batch (배치) session
> **목적**: 배치 프로젝트의 `trade_candle_data` 적재 로직과 KIS strategy 백테스트 엔진을 Flask web server 쪽에 **동일하게(as-is)** 재구현한다.
> **원칙**: 지표 계산식 / 매수·매도 판별 로직 / 체결 가정은 **한 글자도 바꾸지 말고 그대로** 옮길 것. 결과 수치가 배치 기준과 일치해야 함.

---

## 0. 전체 데이터 흐름

```
OHLCV 소스(KIS) ──> compute_indicator_df (지표 계산)
                        │
                        ▼
                 trade_candle_data UPSERT (적재)
                        │
                        ▼
             select_candle_data (datetime 오름차순 조회)
                        │
                        ▼
         KisBacktester.run_one (종목별 백테스트)
                        │
                        ▼
        aggregate / summarize (성과지표 집계)
```

크게 **2개 기능**으로 나뉜다.

1. **적재(Ingest)**: OHLCV → 지표 계산 → `trade_candle_data` UPSERT
2. **백테스트(Backtest)**: `trade_candle_data` 조회 → strategy 시그널 순회 → 매매기록/성과 집계

---

## 1. DB 스키마

### 1-1. `trade_candle_data` (PK: `coin` + `datetime`)

```sql
CREATE TABLE trade_candle_data (
  coin            VARCHAR(10)   NOT NULL,             -- 종목코드
  datetime        VARCHAR(19)   NOT NULL,             -- 'YYYY-MM-DD HH:MM:SS' (문자열)
  -- OHLCV
  open            DECIMAL(18,8) NOT NULL,
  high            DECIMAL(18,8) NOT NULL,
  low             DECIMAL(18,8) NOT NULL,
  close           DECIMAL(18,8) NOT NULL,
  volume          DECIMAL(18,8) NOT NULL,
  -- 추세 (EMA: 실제는 SMA로 계산됨, 컬럼명만 ema)
  ema20           DECIMAL(18,8),
  ema60           DECIMAL(18,8),
  ema120          DECIMAL(18,8),
  -- Bollinger Band
  bb_mid          DECIMAL(18,8),
  bb_lower        DECIMAL(18,8),
  bb_lower_chk    DECIMAL(1,0),
  bb_upper        DECIMAL(18,8),
  bb_upper_chk    DECIMAL(1,0),
  bb_mid_breakout DECIMAL(18,8),
  bb_width        DECIMAL(18,8),
  bb_width_avg    DECIMAL(18,8),
  recent_high     DECIMAL(18,8),
  -- MACD
  macd            DECIMAL(18,8),
  macd_s          DECIMAL(18,8),
  macd_lower_mean DECIMAL(18,8),
  macd_upper_mean DECIMAL(18,8),
  macd_recent_min DECIMAL(18,8),
  macd_recent_max DECIMAL(18,8),
  macd_g_cross_n  VARCHAR(1),
  macd_d_cross_n  VARCHAR(1),
  -- Stochastic (현재 적재 안 함, 컬럼만 존재)
  fs_k            DECIMAL(18,8),
  fs_d            DECIMAL(18,8),
  -- 기타
  roc             DECIMAL(18,8),
  atr             DECIMAL(18,8),
  -- OBV
  obv             DECIMAL(18,8),
  obv_signal      DECIMAL(18,8),
  obv_cross       VARCHAR(1),
  obv_recent_min  DECIMAL(18,8),
  obv_recent_max  DECIMAL(18,8),
  obv_g_cross_n   VARCHAR(1),
  obv_d_cross_n   VARCHAR(1),
  -- RSI
  rsi             DECIMAL(18,8),
  rsi_signal      DECIMAL(18,8),
  rsi_cross       VARCHAR(1),
  -- Volume
  vol_surge_n     DECIMAL(18,8),
  -- Score
  score_trend      DECIMAL(18,8),
  score_momentum   DECIMAL(18,8),
  score_volatility DECIMAL(18,8),
  score_volume     DECIMAL(18,8),
  score_total      DECIMAL(18,8),
  regime           VARCHAR(10),
  -- Decision
  watch_action    VARCHAR(45),
  active_action   VARCHAR(45),
  PRIMARY KEY (coin, datetime)
);
```

> **주의**
> - `datetime`은 DATETIME이 아니라 **VARCHAR(19) 문자열**. 범위 필터는 문자열 비교로 동작한다 (`'YYYY-MM-DD HH:MM:SS'` 포맷이라 사전식 비교 = 시간순 비교가 성립).
> - 컬럼명은 `ema`지만 **계산은 SMA(단순이동평균)**. 이름만 ema임. 절대 EMA로 바꾸지 말 것.
> - 적재 단계에서 채우는 컬럼은 일부(아래 1-3 참고)이며, `fs_k/fs_d/roc/score_*/watch_action/active_action` 등은 백테스트 적재 경로에서 비워둠.

### 1-2. `trade_log` (백테스트 로그용, PK: `trade_id` AUTO_INCREMENT)

```sql
CREATE TABLE trade_log (
  trade_id     BIGINT       NOT NULL AUTO_INCREMENT,
  user_id      INT          NOT NULL,
  coin_symbol  VARCHAR(20)  NOT NULL,       -- 예: 'BTC/KRW', 종목코드
  action_type  VARCHAR(15)  NOT NULL,       -- BUY / SELL
  order_time   DATETIME     NOT NULL,
  exec_time    DATETIME     NULL,
  price        DECIMAL(18,8) NOT NULL,      -- 체결 단가
  quantity     DECIMAL(18,8) NOT NULL,      -- 체결 수량
  total_amount DECIMAL(18,8) NOT NULL,      -- price * quantity
  remain_qty   DECIMAL(18,8) NOT NULL DEFAULT 0,  -- 보유 잔량
  fee          DECIMAL(18,8) NOT NULL DEFAULT 0,
  pnl          DECIMAL(18,8) NOT NULL DEFAULT 0,
  krw_balance  DECIMAL(18,8) NOT NULL DEFAULT 0,
  sma_checker  VARCHAR(1) NULL,
  rsi_checker  VARCHAR(1) NULL,
  macd_checker VARCHAR(1) NULL,
  stk_checker  VARCHAR(1) NULL,
  obv_checker  VARCHAR(1) NULL,
  score        DECIMAL(5,2) NULL,
  note         VARCHAR(255) NULL,
  PRIMARY KEY (trade_id),
  INDEX idx_trade_log_exec_time (exec_time),
  INDEX idx_trade_log_coin_symbol (coin_symbol)
);
```

### 1-3. `user_options` strategy 파라미터 (s1_*)

`KospiStrategy0` 의 파라미터는 `user_options` 테이블의 `s1_*` 컬럼으로 override 가능하다. **NULL이면 전략 클래스 기본값 사용**. 마이그레이션 DDL은 `migrate_user_options_s1.sql` 참고. 핵심 컬럼:

| 컬럼 | 타입 | 기본값 | 의미 |
|---|---|---|---|
| s1_stop_loss_pct | DECIMAL(6,4) | 0.05 | 손절 비율 |
| s1_take_profit_pct | DECIMAL(6,4) | 0.30 | 익절 비율 |
| s1_max_hold_bars | INT | 12 | 최대 보유 봉수(타임스탑 기준) |
| s1_rsi_overbought | INT | 70 | RSI 과매수 진입차단 |
| s1_rsi_ideal_low / high | INT | 40 / 65 | RSI 신뢰구간 |
| s1_vol_ma_window | INT | 20 | 평균거래량 산정기간 |
| s1_vol_ma_mult | DECIMAL(6,2) | 0.5 | 진입 최소거래량 배수 |
| s1_regime_window | INT | 90 | 국면 분류 봉 길이 |
| s1_regime_threshold | DECIMAL(6,4) | 0.70 | 하락국면 판정 임계값 |
| s1_strict_need_macd_up | TINYINT(1) | 1 | 하락국면 macd>=signal 요구 |
| s1_loose_need_vol_surge | TINYINT(1) | 1 | 상승국면 거래량급증 요구 |
| s1_surge_relax_mult | DECIMAL(6,2) | 2.0 | 완화 급증 배수(전봉 대비) |
| s1_downtrend_surge_bypass | TINYINT(1) | 1 | 하락국면 급증 우회 |
| s1_surge_bypass_mult | DECIMAL(6,2) | 2.0 | 우회 급증 배수 |
| s1_use_trailing | TINYINT(1) | 1 | 트레일링 사용 |
| s1_trail_basis | VARCHAR(5) | close | close/high |
| s1_trail_activate_pct | DECIMAL(6,4) | 0.08 | 트레일링 활성화 수익 |
| s1_k_trail_atr | DECIMAL(6,2) | 3.0 | 샹들리에 ATR 배수 |
| s1_trail_floor_pct | DECIMAL(6,4) | 0.10 | ATR 미산출 시 대체 하락폭 |
| s1_time_stop_extend | TINYINT(1) | 1 | 타임스탑 연장 허용 |
| s1_time_stop_band | DECIMAL(6,4) | 0.02 | 정체 판정 수익밴드 |
| s1_time_stop_grace | INT | 3 | 신고가 갱신 허용 봉수 |
| s1_max_hold_bars_hard | INT | 20 | 절대 보유 한도 |
| s1_obv_dead_min_bars | INT | 5 | OBV 데드크로스 노이즈 무시 봉수 |

---

## 2. 기능 ① 적재: 지표 계산 + UPSERT

### 2-1. 지표 계산 (`compute_indicator_df`)

입력: OHLCV DataFrame (`open/high/low/close/volume`). 출력: 지표 컬럼이 추가된 DataFrame.
**아래 계산식을 그대로 구현할 것** (파라미터 출처: `user_info` = `UserOptionMeta`):

- **이동평균(컬럼명 ema, 실제 SMA)**: `ema20/60/120 = close.rolling(20/60/120).mean()`
- **Bollinger Band(20, 2σ)**:
  - `ma = close.rolling(20).mean()`, `std = close.rolling(20).std(ddof=0)`
  - `bb_mid = ma`, `bb_upper = ma + 2*std`, `bb_lower = ma - 2*std`
  - `bb_upper_chk` = 최근 `bb_over_recent_day`봉 내 `high > bb_upper` 발생여부 rolling max (0/1)
  - `bb_lower_chk` = 최근 `bb_over_recent_day`봉 내 `low < bb_lower` 발생여부 rolling max (0/1)
  - `bb_mid_breakout` = bb_mid 돌파 이벤트 체크 (아래 §2-2 `__bb_mid_check`)
  - `bb_width = bb_upper - bb_lower`, `bb_width_avg = bb_width.rolling(20).mean()`
- **MACD(12,26,9)**:
  - `macd = close.ewm(span=12,adjust=False).mean() - close.ewm(span=26,adjust=False).mean()`
  - `macd_s = macd.ewm(span=9,adjust=False).mean()`
  - `macd_lower_mean / macd_upper_mean` = 국소 극값 평균 (§2-2 `__n_day_avg`)
  - `macd_recent_min/max = macd.rolling(macd_recent_day, min_periods=macd_recent_day).min()/max()`
  - `macd_g_cross_n / macd_d_cross_n` = 최근 `delay_date`봉 내 골든/데드크로스 여부 → 'G'/'D' or '' (§2-2 `__n_day_cross_check`)
- **OBV**:
  - `obv = (sign(close.diff()) * volume).fillna(0).cumsum()`
  - `obv_signal = obv.rolling(9).mean()`
  - `obv_g_cross_n / obv_d_cross_n` = 최근 `delay_date`봉 내 골든/데드크로스 ('G'/'D' or '')
- **Volume**:
  - `is_surge_today = (volume >= prev_vol * vol_surge) & (prev_vol > 0)`  (prev_vol = volume.shift(1))
  - `vol_surge_n = is_surge_today.rolling(delay_date).max() == 1`  (boolean)
  - `vol_avg = volume.rolling(20).mean()`  ← **DB 미저장**, 라이브 경로에서만 사용. 백테스트는 §3-1에서 즉석계산.
- **RSI(14, Wilder, ewm com=13)**:
  - `delta = close.diff()`, `gain = delta.where(delta>0,0)`, `loss = -delta.where(delta<0,0)`
  - `avg_gain = gain.ewm(com=13,adjust=False).mean()`, `avg_loss = loss.ewm(com=13,adjust=False).mean()`
  - `rs = avg_gain / avg_loss.replace(0, NaN)`, `rsi = (100 - 100/(1+rs)).fillna(50.0)`
- **ATR(14, Wilder)**:
  - `tr = max(high-low, |high-prev_close|, |low-prev_close|)`
  - `atr = tr.ewm(alpha=1/14, adjust=False).mean()`
  - `atr_pct = (atr/close)` (inf→0)
- **recent_high** = `high.rolling(20).max()`
- **downtrend_ratio**(국면 분류기, **DB 미저장**): 최근 90봉 중 `close < ema60` 비율, `min_periods=20`. ema60 NaN봉 제외. 라이브는 여기서 계산, 백테스트는 §3-1에서 즉석계산.

### 2-2. 보조 함수 (정확히 재현 필요)

- **`__check_than_bb(bb_type, target, df_bb, window)`**: `bb_upper`면 `target > df_bb`, 아니면 `target < df_bb` → `rolling(window, min_periods=1).max()`
- **`__n_day_avg(src, avg_type, window=120, order=5)`**: `scipy.signal.argrelextrema`로 국소 극값 인덱스 추출 (`lower`=less_equal & 값<0, `upper`=greater_equal & 값>0) → 해당 위치 값만 남긴 Series를 `rolling(120, min_periods=1).mean()`. **scipy 의존성 필요.**
- **`__n_day_cross_check(cross_type, data, signal, n)`**: `G`=`(prev_data<=prev_sig)&(data>sig)`, `D`=`(prev_data>=prev_sig)&(data<sig)` → `rolling(n).max()==1` 이면 'G'/'D' 아니면 ''
- **`__bb_mid_check(open, close, bb_mid, n)`**: '완벽한 돌파 이벤트'(어제 bb_mid 하단 → 오늘 양봉이며 중심점이 bb_mid 위) 가 최근 n봉 내 있었고 + 당일 `close > bb_mid` 유지 시 True. (원본 로직 그대로 — §원본파일 참조)

> 위 4개 함수는 미묘한 edge case가 많으니 **원본 `KisStockService.py` 코드를 그대로 포팅**하고, 동일 입력에 동일 출력이 나오는지 회귀 테스트로 검증할 것.

### 2-3. UPSERT (`upsert_candle_data_kis`)

- `INSERT ... ON DUPLICATE KEY UPDATE` (MySQL). PK(`coin`,`datetime`) 충돌 시 PK 제외 전 컬럼 갱신.
- 적재 컬럼: `open/high/low/close/volume`, `ema20/60/120`, `bb_*`, `recent_high`, `macd/macd_s/macd_lower_mean/macd_upper_mean/macd_recent_min/macd_recent_max/macd_g_cross_n/macd_d_cross_n`, `obv/obv_signal/obv_g_cross_n/obv_d_cross_n`, `rsi`, `atr`, `vol_surge_n`.
- 계산 후 `df.fillna(0.0)` 적용 뒤 행단위로 upsert, 종목별 `commit`.

### 2-4. 적재 러너 (`test_backtest_insert`)

- 입력: `end_date(YYYY-MM-DD)`, `lookback_days(기본 250)`. `start_date = end_date - lookback_days`.
- stock master 전체 종목 순회 → `getOHLCV(code, start, end)` → `compute_indicator_df` → `fillna(0)` → 행별 `upsert_candle_data_kis` → 종목별 commit. 단일종목 버전(`_one`)도 제공.

---

## 3. 기능 ② 백테스트 엔진 (`KisBacktester`)

### 3-1. 진입 전 즉석 계산 (DB에 없는 파생값 주입)

`run_one(coin_code, rows, base_user_info)` — `rows`는 datetime 오름차순 candle dict 리스트.

- **vol_avg 주입**: 각 i에 대해 `rows[i]['vol_avg'] = mean(volume[i+1-w : i+1])` (w=`vol_ma_window`, 기본20; 봉 부족 시 0.0)
- **downtrend_ratio 주입**: 각 i에 대해 최근 `regime_window`(기본90)봉 중 `close < ema60` 비율. `ema60`이 None/0인 봉은 분모에서 제외. total=0이면 0.0.

> 라이브 경로는 `compute_indicator_df`가 vol_avg/downtrend_ratio를 채우지만, **DB에는 저장 안 하므로** 백테스트에서 동일 로직으로 즉석 계산. **두 경로의 계산식이 일치해야 함.**

### 3-2. 포지션/체결 가정

- 한 종목당 **동시 1 포지션, 전액 진입**. 수익률은 트레이드별 % 복리 집계.
- **진입**: watch 시그널이 BUY류면 **다음 봉이 존재할 때만** 예약(`pending_buy`) → **다음 봉 시초가(open)** 로 체결 (open 없으면 close).
- **청산**: active 시그널이 SELL류면 **다음 봉 시초가**로 청산, 다음 봉 없으면 **현재 종가**.
- **수수료**: `fee_rate`(기본 0.0015, 편도). 순수익 `ret_net = ret_gross - 2*fee_rate` (왕복).
- **종료 미청산**: 마지막 봉 종가로 강제 청산(exit_reason='EOD', mark-to-market).

BUY/SELL 액션 집합:
```
BUY_ACTIONS  = {BUY, BUY_BREAKOUT, BUY_DIP, BUY_ALL, BUY_SURGE}
SELL_ACTIONS = {SELL_PROFIT, SELL_STOP_LOSS, SELL_STOP_PROFIT, SELL_TRAIL, SELL_TIME}
```

### 3-3. 보유 중 매 봉 포지션 상태 갱신 (매도 판별 입력)

진입 시: `entry_price/entry_atr/peak_high/peak_close` 세팅, `bars_since_peak=0`, `bars_held=0`.
보유 봉마다:
- `peak_high = max(peak_high, high)`, `peak_close = max(peak_close, close)`
- 신고가(peak_high) 갱신 시 `bars_since_peak=0`, 아니면 `+1`
- `bars_held += 1`

### 3-4. 시그널 호출

- 무포지션: `strategy.get_action_with_prev('watch', prev_info, coin_info, ui)` → BUY류면 진입 예약
- 보유중: 상태 갱신 후 `get_action_with_prev('active', ...)` → SELL류면 청산

> `prev_info` / `coin_info` 는 각각 `rows[i-1]`, `rows[i]` 를 `UserCoinInfo.from_dict`로 변환. `i`는 1부터 순회.

### 3-5. 성과 집계 (`_summarize` / `aggregate`)

종목별 dict 반환:
```
trades, win_rate(%), total_return(%, 복리), avg_ret(%), avg_win/avg_loss(%),
profit_factor(=Σwin/Σ|loss|, loss=0이면 'inf'), mdd(%, 복리 자본곡선 기준),
avg_bars, exit_breakdown(청산사유별 카운트), trade_list[]
```
- 자본곡선: `equity *= (1+ret_net)` 누적, `mdd = min(v/peak - 1)`.
- `aggregate`: 전 종목 trade_list 합쳐 'ALL'로 재집계 + `symbols`(거래발생 종목수).

---

## 4. Strategy: `KospiStrategy0` (핵심 — 정확히 재현)

`get_action_with_prev(position_type, prev_info, coin_info, user_info)`:
- 호출 첫줄에서 `configure(user_info)` 실행 → `user_options.s1_*` 값으로 기본값 override.
- `position_type=='watch'` → 매수 판별, `'active'` → 매도 판별.

### 4-1. 매수 판별 (`get_action_in_watch`) — 순서대로 게이트 통과

**핵심 엣지**: MACD + OBV **동시** 골든크로스 (단독 신호로는 절대 진입 안 함).

1. **dual fresh 필수**:
   - `is_macd_g = macd_g_cross_n=='G'`, `is_obv_g = obv_g_cross_n=='G'`
   - `is_macd_gap_closing` = `(curr_gap > prev_gap)` and `(macd > prev_macd)` (gap = macd - macd_s)
   - `is_macd_signal = is_macd_g or is_macd_gap_closing`
   - `both_now = is_macd_signal and is_obv_g`
   - `prev_full_pass` = 직전봉이 (macd_g + obv_g + rsi<overbought + close<=bb_upper + 거래량조건) 모두 충족
   - `is_dual_fresh = both_now and not prev_full_pass` → **False면 HOLD**
2. **보조 필터** (하나라도 실패 시 HOLD):
   - `macd_ok` = `macd>0` or (`macd>macd_s` and `macd>prev_macd`) or `is_macd_gap_closing`
   - `not is_rsi_overbought` (rsi < `rsi_overbought`)
   - `is_under_bb_upper` (`close <= bb_upper`)
   - `is_vol_above_avg` (`vol_avg<=0` or `volume >= vol_avg * vol_ma_mult`)
3. **적응형 추세국면 게이트** (`regime_gate`, False면 HOLD):
   - `dt_ratio = downtrend_ratio`, `is_downtrend_regime = dt_ratio >= regime_threshold`
   - **하락국면**: `strict_ok = above_ema60 and (ema20>ema60) and (macd>=macd_s or not strict_need_macd_up)`; 단 `surge_bypass = downtrend_surge_bypass and above_ema20 and is_surge_relaxed` 면 면제. `regime_gate = strict_ok or surge_bypass`
   - **상승국면**: `regime_gate = above_ema20 and (is_vol_surge or is_surge_relaxed or not loose_need_vol_surge)`
   - `is_surge_relaxed = prev_vol>0 and volume >= prev_vol * surge_relax_mult`
4. **진입 액션**: `is_vol_surge`(vol_surge_n>0)면 `BUY_SURGE`, 아니면 `BUY`.

### 4-2. 매도 판별 (`get_action_in_active`) — 우선순위 순

`entry = entry_price>0 ? entry_price : avg_price`, `profit_pct=(close-entry)/entry`,
`stop_price=entry*(1-stop_loss_pct)`, `target_price=entry*(1+take_profit_pct)`.

1. **손절(최우선)** → `SELL_STOP_LOSS`:
   - `price_stop_valid = (close<=stop_price) and not (close>ema20)` (20일선 위면 손절 보류)
   - `obv_dead_valid = (obv_d_cross_n=='D') and bars_held>=obv_dead_min_bars`
   - 둘 중 하나라도 참이면 매도.
2. **익절** → `SELL_PROFIT`: `close >= target_price`
3. **트레일링(샹들리에)** → `SELL_TRAIL`:
   - `peak = (trail_basis=='close'? peak_close : peak_high) or close`
   - `atr = coin.atr>0 ? coin.atr : entry_atr`
   - `trail_line = atr>0 ? peak - k_trail_atr*atr : peak*(1-trail_floor_pct)`
   - `peak_gain=(peak-entry)/entry`, `trail_on = use_trailing and peak_gain>=trail_activate_pct`
   - `trail_valid = trail_on and close<=trail_line` 이면 매도.
4. **동적 타임스탑** (`bars_held >= max_hold_bars` 일 때만 평가):
   - `trend_alive = profit_pct>time_stop_band and close>ema20 and bars_since_peak<=time_stop_grace`
   - `over_hard = bars_held>=max_hold_bars_hard`
   - `time_stop_extend and trend_alive and not over_hard` → **HOLD(보류, 트레일/손절에 위임)**
   - 아니면 → `SELL_TIME`
5. 위 어느 것도 아니면 `HOLD`.

### 4-3. Action enum

```
HOLD=0
BUY=1, BUY_BREAKOUT=2, BUY_DIP=3, BUY_ALL=4, BUY_SURGE=5
SELL_PROFIT=11, SELL_STOP_LOSS=12, SELL_TRAIL=13, SELL_STOP_PROFIT=14, SELL_TIME=15
```

---

## 5. 데이터 구조 (DTO)

- **`UserCoinInfo`**: candle 한 봉 + 지표. `from_dict(dict)` / `to_dict()` 지원. 백테스트 핵심 필드: `coin_code, datetime, open/high/low/close/volume, ema20/60/120, bb_*, macd/macd_s, macd_g_cross_n/macd_d_cross_n, obv_g_cross_n/obv_d_cross_n, rsi, atr, vol_surge_n, vol_avg, downtrend_ratio`.
- **`UserOptionMeta`**: 전략 파라미터 + **포지션 상태**(`entry_price, entry_atr, peak_high, peak_close, bars_since_peak, bars_held, has_position, avg_price`) + `s1_*` override 필드. 진입 옵션: `vol_limit, vol_surge, delay_date, macd_recent_day, bb_over_recent_day, bb_width_threshold`.

---

## 6. Flask web server 측 산출물 (제안)

배치는 CLI/test 함수로 실행되지만, web server는 HTTP API로 노출하면 됨. **로직은 위와 동일하게**, 진입점만 API로:

- `POST /backtest/ingest` — body: `{end_date, lookback_days?, stock_codes?[]}` → 지표 계산 + `trade_candle_data` 적재. (전체 or 지정 종목)
- `POST /backtest/run` — body: `{coin_code, start_date?, end_date?, fee_rate?, init_cash?}` → 단일종목 백테스트 결과(summary + trade_list + 가상자금 시뮬). 
- `POST /backtest/run-all` — body: `{start_date?, end_date?, fee_rate?}` → 전 종목 집계 + 종목별 상/하위 랭킹.
- `GET /candle?coin=&start_date=&end_date=` — `select_candle_data` 조회 (datetime 오름차순, end_date가 날짜만이면 ` 23:59:59` 보정).

> API 형태/엔드포인트명은 Flask 팀 컨벤션에 맞춰 조정 가능. **불변 조건은 적재·계산·매매 로직의 결과가 배치와 동일**하다는 것.

가상자금 시뮬(`run`의 콘솔 출력 부분) 참고식: 매수수수료/매도수수료 0.0011 편도, 정수 주 매수.
`shares = int(cash / (entry*(1+BUY_FEE)))`, `cash = cash - shares*entry*(1+BUY_FEE) + shares*exit*(1-SELL_FEE)`.

---

## 7. 의존성 / 주의사항

- **scipy** (`argrelextrema`), **pandas**, **numpy** 필요.
- OHLCV 소스는 KIS(`KisEngine.getOHLCV`). web server에 KIS 연동이 없으면, 배치가 적재한 `trade_candle_data`를 **공유 DB에서 조회만** 하는 방식도 가능(적재는 배치, 백테스트만 web). 어느 쪽으로 갈지 협의 필요.
- DECIMAL → float 변환 시 미세 오차 가능 (`to_dict`의 `f()`).
- `datetime` 문자열 비교 의존 — 포맷 깨지면 범위필터 오동작.
- **이름 함정**: `ema*` 컬럼은 실제 SMA. `obv_cross/rsi_cross/fs_k/fs_d/roc/score_*` 는 백테스트 적재 경로에서 채우지 않음(0/NULL).

---

## 8. 검증 기준 (인수 조건)

1. 동일 OHLCV 입력 → `compute_indicator_df` 출력이 배치와 **컬럼별 일치**(부동소수 허용오차 내).
2. 동일 `trade_candle_data` → `KisBacktester.run_one` 결과(trades/win_rate/total_return/mdd/exit_breakdown)가 배치와 **완전 일치**.
3. 대표 종목(예: 005930, 005070, 066430, 048910) 회귀 테스트 통과.

---

### 부록: 원본 파일 위치 (배치 프로젝트)

| 기능 | 파일 |
|---|---|
| 테이블 모델 | `app/domain/model/tradeCandleData.py`, `app/domain/model/batchBackTestLog.py` |
| DAO(조회/upsert) | `app/domain/dao/tradeCandleDataDao.py` |
| 지표 계산 | `app/ext_services/kis/component/KisStockService.py` |
| 백테스트 엔진 | `shared/stock_shared/strategy/backtester.py` |
| 전략 | `shared/stock_shared/strategy/kospi0.py`, `shared/stock_shared/strategy/base.py` |
| 적재 러너 | `app/test/test_5.py` |
| 백테스트 러너 | `app/test/test_backtest.py` |
| DTO | `app/domain/dto/userCoinInfo.py`, `app/domain/dto/userOptionMeta.py` |
| s1_* 마이그레이션 | `migrate_user_options_s1.sql` |
