# 매도 파라미터 조정 UI — FE 개발 스펙

worker 매도 로직(`KospiStrategy0`)의 유저별 튜닝 파라미터를 조정하는 설정 화면 스펙.

- 대상 전략: `shared/stock_shared/strategy/kospi0.py` (`get_action_in_active`)
- 실행 엔진: `app/trade_worker/sell_executor.py`, 설정: `app/trade_worker/config.py`
- 저장 위치: `user_options` 테이블의 `s1_*` 컬럼 (유저별 override)
- 적용 시점: worker `SellStrategy.__init__` → `KospiStrategy0.configure(user_meta)` 가 `s1_*` 값으로 클래스 기본값을 덮어씀. **null이면 전략 클래스 기본값 사용.**

---

## 0. 핵심 동작 (FE가 알아야 할 로직)

매도 판정 우선순위 (위에서부터 먼저 걸리면 즉시 전량 매도):

1. **손절** — 가격 손절 OR OBV 데드크로스
2. **익절** — +N% 도달
3. **트레일링 스탑** — 고점 − k·ATR 하회
4. **동적 타임스탑** — 보유 봉수 한도 도달

실시간(소켓)은 `stop_price / target_price / trail_line` 세 라인 돌파를 감시하고, 이 라인 값은 daily 평가(`evaluate`)가 미리 계산해 DB에 저장. 즉 **파라미터를 바꾸면 다음 daily 평가부터 라인이 갱신됨** (실시간 즉시 반영 아님) — UI에 이 점 안내 권장.

`null` 저장 = "기본값 따름". FE는 빈 입력을 0이 아니라 null로 전송해야 하고, placeholder로 전략 기본값을 회색 표시한다.

---

## 1. 변수 총집합

### 그룹 A — 손절 (Stop Loss)

| 필드(s1) | 라벨 | 타입 | 기본 | 범위 | step | UI |
|---|---|---|---|---|---|---|
| `s1_stop_loss_pct` | 손절 % | float | 0.05 | 0.02 ~ 0.15 | 0.005 | slider+% |
| `s1_obv_dead_min_bars` | OBV 데드크로스 무시 봉수 | int | 5 | 0 ~ 20 | 1 | stepper |

- `s1_stop_loss_pct`: 진입가 대비 −N% 하회 시 손절. UI는 % 표기(값 5 = 5%).
- `s1_obv_dead_min_bars`: 진입 후 이 봉수 이내의 OBV 데드크로스는 노이즈로 무시.
- **하드코딩 규칙(변수화 후보)**: 현재 "−N% 뚫려도 종가가 ema20 위면 손절 안 함"이 코드에 고정. 변수화하려면 `s1_stop_require_below_ema20`(bool, 기본 true) 신설 필요 — 백엔드 작업 선행. 이번 UI에는 **미노출** 또는 disabled로 표시.

### 그룹 B — 익절 (Take Profit)

| 필드(s1) | 라벨 | 타입 | 기본 | 범위 | step | UI |
|---|---|---|---|---|---|---|
| `s1_take_profit_pct` | 익절 % | float | 0.30 | 0.05 ~ 1.0 | 0.05 | slider+% |

- 진입가 대비 +N% 도달 시 전량 익절.

### 그룹 C — 트레일링 스탑 (Chandelier)

| 필드(s1) | 라벨 | 타입 | 기본 | 범위 | step | UI |
|---|---|---|---|---|---|---|
| `s1_use_trailing` | 트레일링 사용 | bool | true | on/off | — | toggle (그룹 마스터) |
| `s1_trail_basis` | 고점 기준 | enum | 'close' | close / high | — | radio |
| `s1_trail_activate_pct` | 활성화 수익 % | float | 0.08 | 0.0 ~ 0.5 | 0.01 | slider+% |
| `s1_k_trail_atr` | ATR 배수(k) | float | 3.0 | 1.0 ~ 6.0 | 0.5 | slider |
| `s1_trail_floor_pct` | ATR 미산출 대체 % | float | 0.10 | 0.03 ~ 0.30 | 0.01 | slider+% |

- `s1_use_trailing` off → 하위 4개 필드 **disable**.
- `s1_trail_basis`: 'close'=종가 고점 기준(장중 꼬리에 둔감), 'high'=장중 고점 기준.
- `s1_k_trail_atr`: 작을수록 타이트(빨리 매도). 종목별 튜닝 포인트.
- `s1_trail_activate_pct`: 고점수익이 이 값 이상일 때만 트레일링 ON.
- `s1_trail_floor_pct`: ATR을 못 구할 때만 쓰는 fallback(고점 −N%).

### 그룹 D — 동적 타임스탑 (Time Stop)

| 필드(s1) | 라벨 | 타입 | 기본 | 범위 | step | UI |
|---|---|---|---|---|---|---|
| `s1_max_hold_bars` | 보유 한도 봉수 | int | 12 | 3 ~ 60 | 1 | slider |
| `s1_time_stop_extend` | 추세생존 시 연장 | bool | true | on/off | — | toggle (하위 마스터) |
| `s1_time_stop_band` | 정체 판정 수익밴드 % | float | 0.02 | 0.0 ~ 0.10 | 0.005 | slider+% |
| `s1_time_stop_grace` | 신고가 grace 봉수 | int | 3 | 0 ~ 10 | 1 | stepper |
| `s1_max_hold_bars_hard` | 절대 보유 한도 봉수 | int | 20 | (max_hold_bars) ~ 120 | 1 | slider |

- `s1_max_hold_bars` 도달 시 타임스탑 평가 시작.
- `s1_time_stop_extend`=true면 (수익 > band) & (ema20 위) & (최근 grace봉 내 신고가)일 때 매도 보류 → 트레일/손절에 위임. off면 하위 band/grace/hard 개념 무의미하므로 band·grace **disable**.
- `s1_max_hold_bars_hard`: 연장 포함 절대 상한.

### 그룹 E — 실행·안전 (worker config / env, 판정과 분리)

> 이건 전략 판정이 아니라 주문 실행/재시도 정책. **화면 섹션을 분리**하고, 현재는 env로만 주입됨(`user_options` 컬럼 아님). DB 컬럼화 여부는 백엔드와 협의 — 컬럼 없으면 read-only로 현재값만 표시.

| env | 라벨 | 타입 | 기본 | 범위 | UI |
|---|---|---|---|---|---|
| `SELL_RETRY_COOLDOWN_SEC` | 매도 실패 재시도 쿨다운(초) | int | 60 | 10 ~ 600 | number |
| `SELL_MAX_FAILS` | 연속 실패 자동 비활성 임계 | int | 5 | 1 ~ 20 | number |
| `EXCHANGE` | 주문 라우팅 | enum | SOR | KRX/NXT/SOR | select |
| `DRY_RUN` | 모의(로그만) | bool | false | on/off | toggle (강조/경고색) |
| `lookback_days` | 지표 계산 조회 기간(일) | int | 250 | 60 ~ 500 | number |

---

## 2. 화면 구성

- 유저별 설정 페이지. 상단에 대상 유저 선택(id 1/2/3).
- **매도 단계별 4개 카드**: A 손절 / B 익절 / C 트레일링 / D 타임스탑.
  - 각 카드 상단에 우선순위 배지: `1 손절 > 2 익절 > 3 트레일링 > 4 타임스탑`.
- **하단 별도 섹션**: E 실행·안전 (경고색 구분).
- 각 필드: 라벨 + 컨트롤 + 현재 저장값 + placeholder(기본값) + 단위.

### 컨트롤 규칙
- % 계열: slider ↔ 숫자입력 양방향 동기화. 표시는 %(내부 저장은 소수, 예 5% → 0.05).
- 봉수/횟수: stepper 또는 slider(정수).
- enum: radio/select.
- bool: toggle.

### 조건부 활성화 (disable)
- `s1_use_trailing` = false → `trail_basis`, `trail_activate_pct`, `k_trail_atr`, `trail_floor_pct` disable.
- `s1_time_stop_extend` = false → `time_stop_band`, `time_stop_grace` disable.

### 검증 (client)
- `s1_max_hold_bars_hard ≥ s1_max_hold_bars` (위반 시 저장 차단 + 인라인 에러).
- 각 필드 범위 clamp.
- 빈값 → null 전송(기본값 따름).

---

## 3. 저장/전송 (제안 payload)

```json
PUT /api/users/{userId}/sell-params
{
  "s1_stop_loss_pct": 0.05,
  "s1_obv_dead_min_bars": 5,
  "s1_take_profit_pct": 0.30,
  "s1_use_trailing": true,
  "s1_trail_basis": "close",
  "s1_trail_activate_pct": 0.08,
  "s1_k_trail_atr": 3.0,
  "s1_trail_floor_pct": 0.10,
  "s1_max_hold_bars": 12,
  "s1_time_stop_extend": true,
  "s1_time_stop_band": 0.02,
  "s1_time_stop_grace": 3,
  "s1_max_hold_bars_hard": 20
}
```

- 각 값 `null` 허용 = 기본값 따름.
- bool은 DB에서 TINYINT(1) (`configure`가 `bool(int(val))`로 파싱). 전송은 true/false 또는 1/0 — 백엔드와 합의.
- enum(`s1_trail_basis`, `s1_macd/obv_signal_mode` 등)은 빈 문자열이 아니라 null로.

---

## 4. 미리보기 (선택, 강추)

값 변경 시 특정 진입가 기준 라인을 즉시 계산해 보여주면 튜닝 직관성 ↑.

- 입력: 가상 진입가, (선택) ATR.
- 출력:
  - `stop_price = entry * (1 - stop_loss_pct)`
  - `target_price = entry * (1 + take_profit_pct)`
  - `trail_line = peak - k_trail_atr * atr` (ATR 있을 때) / `peak * (1 - trail_floor_pct)` (없을 때)
- 백엔드 `SellStrategy.initial_lines(code, entry_price)` 재사용 가능.
- 여력되면 백테스트 1회 트리거 → 승률/MDD 비교까지.

---

## 5. 주의사항

- 파라미터 변경은 **다음 daily 평가부터 라인 반영**(실시간 즉시 아님) — 저장 후 토스트로 안내.
- `DRY_RUN` toggle은 실거래 스위치라 강조 + 확인 모달.
- E 그룹(env)은 프로세스 재시작 필요할 수 있음 — 백엔드 확인.
- 참고 문서: `docs_buy_target_sim_spec.md`(판정 규칙 근거), `docs_pykis_service_design.md`.
