# buy_target 실전 시뮬레이션 로직 스냅샷

> 목적: `app/test/sim_buy_target.py` 의 현재 매수/매도 판정 로직을 **실전 매매 로직으로 이식**할 수 있도록 모든 분기조건을 기록한 스냅샷.
> 기준 시점: 2026-07 / 매도판단 = `KospiStrategy1`.
> ⚠️ `sim_buy_target.py` 파일 상단 docstring 은 구버전(당일 종가·rank_no) 서술이 남아있음. **실제 동작은 본 문서 기준**(당일추천·과열최저·다음날 시가).

---

## 1. 개요

| 항목 | 값 |
|---|---|
| 추천 소스 | `trade_buy_target_stock` (일별 매수추천 누적) |
| 캔들/지표 소스 | `trade_candle_data` (일봉 OHLCV + 지표) |
| 거래일 유니버스 | `master_stock.stock_type = 'KOSPI'` 종목의 `trade_candle_data.datetime` |
| 포지션 | 동시 **1종목**, **전량매수 / 전량매도** |
| 매도 판정 | `KospiStrategy1.get_action_in_active()` |
| 매수 체결 | 추천일 **다음 거래일 시가**(`ENTRY_PRICE='next_open'`) |
| 매도 체결(시뮬) | 신호 발생일 **당일 종가** |
| 수수료 가정 | 편도 0.11% (왕복 0.22%) |

---

## 2. 상태 머신 (핵심)

3개 상태를 하루 단위로 순회한다.

```
        추천 발생(오늘)                  다음 거래일 시가 체결
 FLAT ───────────────▶ PENDING ───────────────────────▶ HOLD
   ▲                      │  (갭업이면 폐기 → FLAT)         │
   │                      ▼                                │
   │◀──── 폐기(당일 추천 새로 스캔) ────                     │
   │                                                       │
   └──────────────── 매도 체결(SELL) ◀──────────────────────┘
```

- **FLAT**: 무포지션 대기. 그날 추천을 스캔.
- **PENDING**: 매수 예약(추천 다음 거래일 시가 체결 대기). **1일만 유효**.
- **HOLD**: 보유. 매일 매도판정.

일별 처리 순서(한 거래일 `d` 안에서): `HOLD 판정` → `PENDING 체결` → `FLAT 스캔`. 단, 각 분기는 `continue` 로 그날을 종료(같은 날 매수+매도 동시 발생 없음). PENDING 이 폐기되면 같은 날 곧바로 FLAT 스캔으로 흐른다.

---

## 3. 매수(진입) 분기조건 — 상세

### 3.1 후보 선정 (FLAT 상태, 매일)

순서대로 판정:

1. **당일 추천만 후보.** `reco[ymd]`(오늘 날짜 `YYYYMMDD` 추천)만 본다. **지나간 추천은 절대 고려하지 않음.** 오늘 추천 없으면 그날 pass.
2. **과열 최저 선택.** 그날 추천을 `rate`(당일 등락률) **오름차순**으로 정렬 → 가장 안 오른(과열 낮은) 종목 우선. `rate` 파싱 실패/None 은 `inf`(후순위).
3. **캔들 존재 확인.** 정렬 순서대로, `trade_candle_data` 에 그날(`d`) 캔들이 있는 첫 종목을 후보로 확정. (없으면 다음 순위)
4. 후보 확정 시:
   - `ENTRY_PRICE='next_open'` → **PENDING 전환**. `pend_ref = 추천일 종가`(갭업 판정 기준).
   - `ENTRY_PRICE='close'` → 그날 종가에 즉시 진입(HOLD).

### 3.2 체결 (PENDING 상태, 다음 거래일)

1. 후보 종목이 **다음 거래일에 캔들 있음**:
   - `SKIP_GAPUP=True` **AND** 시가 > `pend_ref`(추천일 종가) → **갭업 추격으로 판단 → 폐기(FLAT)**. 같은 날 오늘 추천 새로 스캔.
   - 그 외 → **다음날 시가에 매수 체결**(HOLD).
2. 후보가 다음 거래일에 캔들 없음(휴장/데이터 없음) → **폐기(FLAT)**. (PENDING 은 하루만 유효 → stale 추천 원천 차단)

### 3.3 진입 후 규칙

- 진입한 날(체결일)에는 **매도 판정을 하지 않음**(`bars_held=0`, 다음 거래일부터 매도판정).

### 3.4 진입 관련 파라미터

| 파라미터 | 기본값 | 의미 |
|---|---|---|
| `ENTRY_PRICE` | `'next_open'` | 매수 체결 시점. `'close'`=추천일 종가, `'next_open'`=다음 거래일 시가 |
| `SKIP_GAPUP` | `False` | `next_open` 시, 다음날 시가 > 추천일 종가면 스킵. **현재 False**(모멘텀 지속 살림 — §7 참조) |
| 선택 기준 | 과열최저 | `rate` 오름차순. (모멘텀 우선으로 변경 실험은 미적용) |

---

## 4. 매도(청산) 분기조건 — `KospiStrategy1.get_action_in_active`

보유 중 매일(진입일 제외) 판정. **우선순위 순서**대로 먼저 걸리는 것이 발동. (아래는 `KospiStrategy1` 기본값; `user_options.s1_*` 로 오버라이드 가능)

전제 계산:
- `entry` = `entry_price`(없으면 `avg_price`)
- `profit_pct = (close - entry) / entry`
- `stop_price = entry * (1 - stop_loss_pct)`
- `target_price = entry * (1 + take_profit_pct)`
- `is_above_ema20 = close > ema20`

**우선순위:**

1. **손절 `SELL_STOP_LOSS`** — 아래 둘 중 하나:
   - `price_stop_valid` = `close <= stop_price` **AND** `not is_above_ema20` (−5% 하회 + 20일선 이탈 동반)
   - `obv_dead_valid` = `obv_d_cross_n == 'D'` **AND** `bars_held >= obv_dead_min_bars`(5) (OBV 데드크로스, 초기 5봉 노이즈 무시)
2. **익절 `SELL_PROFIT`** — `close >= target_price` (+30%)
3. **트레일링 `SELL_TRAIL`** — `trail_on` **AND** `close <= trail_line`
   - `trail_on` = `use_trailing` **AND** `peak_gain >= trail_activate_pct`(0.08)  (`peak_gain = (peak_close - entry)/entry`)
   - `trail_line` = `peak_close - k_trail_atr*atr` (atr 있을 때, k=3.0) / 없으면 `peak_close*(1 - trail_floor_pct=0.10)`
4. **타임스탑 `SELL_TIME`** — `bars_held >= max_hold_bars`(12)
   - 단, `time_stop_extend` **AND** `trend_alive` **AND** `not over_hard` 면 **매도 보류(HOLD)**:
     - `trend_alive` = `profit_pct > time_stop_band`(0.02) **AND** `is_above_ema20` **AND** `bars_since_peak <= time_stop_grace`(3)
     - `over_hard` = `bars_held >= max_hold_bars_hard`(20)
5. 위 어느 것도 아니면 **HOLD**(계속 보유)

**매도 파라미터 기본값 (KospiStrategy1):**

| 파라미터 | 기본값 |
|---|---|
| `stop_loss_pct` | 0.05 (−5%) |
| `take_profit_pct` | 0.30 (+30%) |
| `obv_dead_min_bars` | 5 |
| `use_trailing` | True |
| `trail_basis` | `'close'` (종가 고점 기준) |
| `trail_activate_pct` | 0.08 |
| `k_trail_atr` | 3.0 |
| `trail_floor_pct` | 0.10 |
| `max_hold_bars` | 12 |
| `max_hold_bars_hard` | 20 |
| `time_stop_extend` | True |
| `time_stop_band` | 0.02 |
| `time_stop_grace` | 3 |

> 시뮬은 SELL 신호 발생 시 **당일 종가**에 매도 체결(시뮬 가정). 미청산분은 마지막 거래일 종가로 정산(`EOD`).

---

## 5. 포지션 상태 갱신 (매일, HOLD 중 — KisBacktester 와 동일)

진입 시:
```
entry_price = 체결가
entry_atr   = 체결일 atr
peak_high   = 체결일 high
peak_close  = 체결일 close
bars_since_peak = 0
bars_held   = 0
```
보유 매일(매도판정 전):
```
prev_peak = peak_high
peak_high  = max(peak_high, 오늘 high)
peak_close = max(peak_close, 오늘 close)
bars_since_peak = 0 if peak_high > prev_peak else bars_since_peak + 1
bars_held += 1
```

---

## 6. 실전(라이브) 매매 이식 가이드

시뮬 → 실전 매핑. **체결 시점**만 명확히 하면 그대로 이식 가능.

### 매수
1. 장 마감 후 `StockBuyCheckJob` 이 `trade_buy_target_stock` 에 그날 추천을 적재(기존 파이프라인).
2. 그날 추천 중 **과열 최저(`rate` 최소)** 1종목 선정(보유 종목 없을 때만).
3. **다음 거래일 개장 시 시가(또는 시가 근처 시장가)로 전량 매수.**
   - `SKIP_GAPUP=True` 로 운용할 경우: 개장 시가가 추천일 종가보다 높으면 매수 취소. (**현재 권장값 False** — §7)
4. 이미 보유 중이면 신규 매수 안 함(1포지션).

### 매도
1. 보유 종목에 대해 매일 장 마감 지표(`compute_indicator_df`)로 `KospiStrategy1.get_action_in_active` 판정(§4).
2. SELL 계열이면 전량 매도. **체결 시점은 정책 결정 필요**: 시뮬은 당일 종가 가정 → 실전은 (a) 당일 종가 동시호가, 또는 (b) 다음 거래일 시가 중 택1. 선택에 따라 성과가 달라지므로 명시 필요.
3. 매도한 날은 재매수 안 함(다음 거래일부터 신규 추천 탐색).

### 데이터 의존
- `rate`(당일 등락률): `trade_buy_target_stock.rate` 컬럼(예 `"12.5%"`). 과열최저 정렬의 핵심 → 실전에서도 이 값이 정확해야 함.
- 매도 판정에 필요한 지표: `ema20`, `atr`, `obv_d_cross_n`, `close` 등 `trade_candle_data`/실시간 지표.

---

## 7. 백테스트 스냅샷 & 핵심 통찰 (2026-04-01 ~ 2026-07-23, 77거래일)

| 설정 | trades | 승률 | 총수익 | PF | MDD |
|---|---|---|---|---|---|
| `SKIP_GAPUP=False` | 14 | 42.9% | **+58.9%** | 1.96 | −51.7% |
| `SKIP_GAPUP=True` | 12 | 33.3% | **−19.9%** | 0.93 | −58.4% |

**핵심 통찰 — 이 종목군의 엣지는 "모멘텀 지속"이다:**
- 추천은 거래량 급증/급등 모멘텀 신호. 다음날 **갭업 = 모멘텀 지속 = 승자**(예: 006110 04-01 종가 34,400 → 04-02 시가 35,450 갭업 → +38%).
- `SKIP_GAPUP=True` 는 이 갭업 승자들을 골라 버리고(역선택) 보합/하락 출발한 약한 종목만 취해 → 성과 급락.
- 따라서 **`SKIP_GAPUP=False` 가 맞다.** 초기 가정("급등 추격은 나쁘다 / 눌림 대기가 낫다")은 이 데이터에서 **틀렸음** — 눌림 대기·반등 확인 로직은 엣지를 거슬러 폐기됨.

**경고(과신 금지):**
- +58.9% 는 **큰 승자 4건(+34~39%)에 전적으로 의존**. 9건은 손절, 그중 −25% 도 존재.
- **MDD −51.7%** — 실전 감내 어려움. 1포지션 집중의 대가.
- 14건 / 4개월 = **소표본**. 다른 구간에서 재현 보장 없음.

---

## 8. 미해결 / 다음 실험 (우선순위)

1. **표본 확대**(최우선): 2025 구간까지 백필 후 재검증(`collect_buy_target_backfill`). 14건으론 통계적 신뢰 불가.
2. **선택 기준 재검토**: 엣지가 모멘텀 지속이라면 "과열 최저" 선택이 엣지와 상충. **모멘텀 우선(rate 내림차순 / rank_no)** 선택과 A/B 필요.
3. **MDD 완화**: 1포지션 → 분산, 또는 손절 강화/변동성 필터.
4. 매도 체결 시점(당일 종가 vs 다음날 시가) 실전 정책 확정.

---

## 부록: 현재 설정 스냅샷 (`sim_buy_target.py`)

```
START_DATE   = '2026-04-01'
END_DATE     = None
INIT_CASH    = 1_000_000
FEE_RATE     = 0.0011
ENTRY_PRICE  = 'next_open'
SKIP_GAPUP   = False
매도판정      = KospiStrategy1 (기본 파라미터, user_options.s1_* 오버라이드 가능)
선택기준      = 당일 추천, 과열최저(rate 오름차순), 캔들 존재 첫 종목
```
```
실행: poetry run python -m app.test.sim_buy_target [start] [end]
```
