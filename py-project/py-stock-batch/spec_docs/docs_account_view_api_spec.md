# 계좌·거래내역 조회 명세 (web/api)

trade_worker(유저별 실매매 daemon)가 적재하는 **계좌 스냅샷 / 매수·매도 포지션 / 거래·운영 로그**를
web 화면에서 조회하기 위한 데이터 모델 매핑 + REST API 설계.

- 데이터 출처: `app/trade_worker/` (repository.py 가 write, web/api 는 read-only).
- 대상 유저: `user_id` = `KIS_USER_ID`. 모든 조회는 `user_id` 스코프 필수.
- 관련 마이그레이션: `sql/20260730_*.sql`, `sql/20260731_create_trade_worker_position.sql`.
- 배경: [[trade-worker-architecture]], `docs_pykis_service_design.md`, `docs_trade_worker_review.md`.

---

## 0. 개념 요약 — 무엇을 조회하는가

worker 가 만들어낸 상태는 4개 테이블/뷰로 나뉜다. web 메뉴는 이 4개를 3개 화면(계좌요약 / 보유·포지션 / 거래로그)으로 묶어 보여준다.

| # | 대상 | 실체 | 성격 | web 용도 |
|---|------|------|------|----------|
| A | 계좌 요약 | `user_wallet` | 유저 1행 스냅샷(예수금·주식평가·총자산) | 상단 요약 카드 |
| B | 종목별 보유 | `user_holdings` (+ 뷰 `v_user_portfolio`) | 실제 KIS 계좌 보유 snapshot(부팅/체결 시 전량 교체) | 보유종목 그리드 |
| C | 매수·매도 포지션/이력 | `trade_worker_position` | worker 가 **직접 매수한** 포지션. HOLDING→SOLD 로 이력화 | 포지션 상세 / 매매 이력 |
| D | 거래·운영 로그 | `trade_log`(체결) + `trade_worker_log`(운영 INFO/WARN) | 시간순 append | 거래내역 로그 탭 |

> **B vs C 구분(중요).** `user_holdings` 는 KIS 계좌 실제 보유(수동매수·타채널 포함)를 그대로 미러링한 것이고,
> `trade_worker_position` 은 worker 엔진이 직접 매수해 매도감시 중인 포지션만 담는다.
> 화면에서 "내 계좌에 뭐가 있나"는 B, "worker 가 뭘 사고팔았나(손절/익절/트레일 근거 포함)"는 C 를 쓴다.
>
> **수동매수 종목은 C 에 들어오지 않는다.** 과거 `_reconcile_positions()` 가 부팅 시 계좌
> 보유종목을 C 로 흡수(adopt)해 worker 가 자동매도까지 하던 동작은 **폐기**했다
> (`RECONCILE_HOLDINGS_ON_BOOT` 설정도 함께 제거). 부팅 시 대조는 C 에 이미 있는
> worker 포지션에 한해 ① 수량 보정 ② 실제 미보유 시 `EXTERNAL_CLOSED` 정리만 수행한다.
> 따라서 B 에는 있고 C 에는 없는 종목 = 수동보유이며, worker 는 이를 감시·매도하지 않는다.
> `1포지션 원칙`(매수 skip 판정)도 C 기준이라 수동보유는 자동매수를 막지 않는다(예수금만 공유).

---

## 1. 데이터 모델 · 화면 필드 매핑

### 1-A. 계좌 요약 — `user_wallet`

| 컬럼 | 타입 | 의미 | 화면 라벨 |
|------|------|------|-----------|
| `user_id` | INT (PK) | 유저 | — |
| `user_balance` | DECIMAL(18,8) | 예수금(현금) | 예수금 |
| `stock_amount` | DECIMAL(18,8) | 보유주식 평가금액 합계 | 주식평가액 |
| `total_asset` | DECIMAL(18,8) | 총자산(예수금+주식평가) | 총자산 |
| `updated_at` | DATETIME | 마지막 동기화 시각 | 기준시각 |

### 1-B. 종목별 보유 — `user_holdings` / 뷰 `v_user_portfolio`

`user_holdings` (PK = user_id + stock_code):

| 컬럼 | 타입 | 의미 | 화면 라벨 |
|------|------|------|-----------|
| `stock_code` | VARCHAR(20) | 종목코드 | 종목코드 |
| `stock_name` | VARCHAR(45) | 종목명 | 종목명 |
| `qty` | DECIMAL(18,8) | 보유수량 | 수량 |
| `avg_price` | DECIMAL(18,8) | 평균단가 | 매입가 |
| `cur_price` | DECIMAL(18,8) | 현재가 | 현재가 |
| `eval_amount` | DECIMAL(18,8) | 평가금액 | 평가금액 |
| `profit` | DECIMAL(18,8) | 평가손익 | 평가손익 |
| `updated_at` | DATETIME | 동기화 시각 | — |

**뷰 `v_user_portfolio`** — 종목행들 + 합계행 1개를 한 번에. `row_type` 으로 구분:
- `row_type='STOCK'` : 종목별 행(위 컬럼 그대로, `cash`/`total_asset` = NULL)
- `row_type='TOTAL'` : 합계행. `stock_name='합계'`, `eval_amount`=주식평가합, `cash`=예수금, `total_asset`=총자산

> 그리드에서 이 뷰 하나만 조회하면 종목 리스트 + 하단 합계까지 끝난다. 정렬 `ORDER BY row_type, stock_code` → STOCK 먼저, TOTAL 마지막.

### 1-C. 매수·매도 포지션/이력 — `trade_worker_position`

PK = `position_id`. `status` = `HOLDING`(보유중) / `SOLD`(청산). 필드 그룹:

진입(매수 체결 기준):

| 컬럼 | 의미 |
|------|------|
| `entry_ymd` | 매수 체결 영업일 YYYYMMDD (bars_held 기준) |
| `entry_at` | 매수 체결 시각 |
| `entry_price` | 진입 평균단가 |
| `entry_atr` | 진입 시점 ATR (초기 손절 고정용) |
| `qty` | 보유수량 |

포지션 추적(일별 갱신):

| 컬럼 | 의미 |
|------|------|
| `bars_held` | 보유 봉수(일봉) |
| `peak_close` / `peak_high` | 진입 후 종가/장중 최고 |
| `bars_since_peak` | 신고가 후 경과 봉수 |
| `last_check_ymd` | 마지막 일별 갱신일(중복증가 방지) |

매도 라인·판정(KospiStrategy1 산출):

| 컬럼 | 의미 |
|------|------|
| `stop_price` | 손절가 |
| `target_price` | 익절가 |
| `trail_line` | 트레일링 스탑 라인 |
| `action_type` | HOLD / SELL_* |
| `profit_pct` | 수익률 |
| `sell_reason` | 매도 근거 |

청산(매도 체결):

| 컬럼 | 의미 |
|------|------|
| `status` | HOLDING / SOLD |
| `exit_at` / `exit_price` / `exit_reason` | 매도 체결 시각/가/사유 |
| `pnl` | 실현손익 = (exit_price − entry_price) × qty |

### 1-D. 로그

**거래(체결) 로그 — `trade_log`** (PK `trade_id`, 시간순 append):

| 컬럼 | 의미 | 비고 |
|------|------|------|
| `user_id` | 유저 | |
| `coin_symbol` | 종목코드 | 컬럼명은 coin_symbol 이나 주식코드가 들어감 |
| `action_type` | BUY / SELL | VARCHAR(5) |
| `order_time` / `exec_time` | 주문/체결 시각 | |
| `price` / `quantity` / `total_amount` | 체결가 / 수량 / 금액(price×qty) | |
| `remain_qty` / `fee` / `pnl` | 잔량 / 수수료 / 손익 | |
| `krw_balance` | 체결 후 현금잔고 | |
| `note` | 비고 | |

**운영 로그 — `trade_worker_log`** (PK `log_id`, worker 동작 로그):

| 컬럼 | 의미 |
|------|------|
| `user_id` | 담당 유저 |
| `source` | buy / sell |
| `level` | INFO / WARN |
| `message` | 로그 본문(≤500) |
| `created_at` | 기록 시각 |

인덱스: `idx_twl_user_time(user_id, created_at)`, `idx_twl_time`, `idx_twl_src_time(source, created_at)`.

---

## 2. 조회 쿼리 레퍼런스 (api 구현용)

```sql
-- A. 계좌 요약
SELECT user_id, user_balance, stock_amount, total_asset, updated_at
FROM   user_wallet WHERE user_id = :uid;

-- B. 보유 포트폴리오(종목 + 합계) : 뷰 한 방
SELECT * FROM v_user_portfolio WHERE user_id = :uid ORDER BY row_type, stock_code;

-- C1. 현재 보유 포지션(worker)
SELECT * FROM trade_worker_position
WHERE user_id = :uid AND status = 'HOLDING' ORDER BY entry_at DESC;

-- C2. 매매 이력(HOLDING+SOLD, 페이지네이션)
SELECT * FROM trade_worker_position
WHERE user_id = :uid
  AND (:status IS NULL OR status = :status)
ORDER BY entry_at DESC LIMIT :limit OFFSET :offset;

-- D1. 거래(체결) 로그
SELECT * FROM trade_log
WHERE user_id = :uid
  AND (:from IS NULL OR exec_time >= :from)
  AND (:to   IS NULL OR exec_time <  :to)
  AND (:code IS NULL OR coin_symbol = :code)
  AND (:action IS NULL OR action_type = :action)
ORDER BY exec_time DESC LIMIT :limit OFFSET :offset;

-- D2. 운영 로그
SELECT * FROM trade_worker_log
WHERE user_id = :uid
  AND (:source IS NULL OR source = :source)
  AND (:level  IS NULL OR level = :level)
  AND (:from IS NULL OR created_at >= :from)
ORDER BY created_at DESC LIMIT :limit OFFSET :offset;
```

---

## 3. REST API 엔드포인트 설계

### 공통 규약
- Base: `/api/v1`
- 인증: 기존 web 세션/토큰 재사용. `user_id` 는 인증 주체에서 도출(경로에 노출하되 권한체크 필수).
- 금액 필드: 문자열(DECIMAL 정밀도 보존) 반환. 프론트에서 숫자 변환.
- 시간: ISO8601 (`YYYY-MM-DDTHH:mm:ss`).
- 목록 응답 공통 envelope:

```json
{ "data": [ ... ], "page": { "limit": 50, "offset": 0, "total": 123 } }
```

- 에러: `{ "error": { "code": "NOT_FOUND", "message": "..." } }`, HTTP status 동반.

### 3-1. 계좌 요약
```
GET /api/v1/users/{userId}/account
```
응답:
```json
{
  "user_id": 1,
  "user_balance": "1250000.00000000",
  "stock_amount": "3480000.00000000",
  "total_asset": "4730000.00000000",
  "updated_at": "2026-07-31T09:05:12"
}
```

### 3-2. 보유 포트폴리오 (종목 + 합계)
```
GET /api/v1/users/{userId}/portfolio
```
`v_user_portfolio` 기반. 종목행 배열 + 합계 객체로 분리해 반환(프론트 편의):
```json
{
  "holdings": [
    {
      "stock_code": "005930", "stock_name": "삼성전자",
      "qty": "10", "avg_price": "72000.00000000", "cur_price": "74100.00000000",
      "eval_amount": "741000.00000000", "profit": "21000.00000000",
      "updated_at": "2026-07-31T09:05:12"
    }
  ],
  "summary": {
    "cash": "1250000.00000000",
    "stock_amount": "3480000.00000000",
    "total_asset": "4730000.00000000",
    "updated_at": "2026-07-31T09:05:12"
  }
}
```
> 구현: 뷰를 조회해 `row_type='STOCK'` → holdings, `row_type='TOTAL'` → summary 로 매핑.

### 3-3. worker 포지션 — 보유중
```
GET /api/v1/users/{userId}/positions?status=HOLDING
```
쿼리 파라미터:
- `status` : `HOLDING` | `SOLD` | 생략(전체)
- `limit`(기본 50) / `offset`(기본 0)

응답 item:
```json
{
  "position_id": 42, "stock_code": "005930", "stock_name": "삼성전자",
  "status": "HOLDING",
  "entry_ymd": "20260728", "entry_at": "2026-07-28T09:00:03",
  "entry_price": "72000.00000000", "entry_atr": "1500.00000000", "qty": "10",
  "bars_held": 3, "peak_close": "75000.00000000", "peak_high": "75800.00000000",
  "bars_since_peak": 1,
  "stop_price": "69000.00000000", "target_price": "80000.00000000",
  "trail_line": "73200.00000000",
  "action_type": "HOLD", "profit_pct": "2.9%", "sell_reason": null,
  "exit_at": null, "exit_price": null, "exit_reason": null, "pnl": null
}
```

### 3-4. worker 매매 이력 (청산 포함)
```
GET /api/v1/users/{userId}/positions/history?status=SOLD&limit=50&offset=0
```
- 3-3 과 동일 스키마. SOLD 행은 `exit_*` / `pnl` 채워짐.
- 정렬 `entry_at DESC`.

### 3-5. 거래(체결) 로그
```
GET /api/v1/users/{userId}/trade-logs
```
쿼리 파라미터:
- `from` / `to` : `exec_time` 범위(ISO8601 또는 YYYY-MM-DD)
- `stock_code` : coin_symbol 필터
- `action` : `BUY` | `SELL`
- `limit` / `offset`

응답 item:
```json
{
  "trade_id": 1001, "user_id": 1, "stock_code": "005930", "action_type": "BUY",
  "order_time": "2026-07-28T09:00:01", "exec_time": "2026-07-28T09:00:03",
  "price": "72000.00000000", "quantity": "10", "total_amount": "720000.00000000",
  "remain_qty": "0", "fee": "0", "pnl": "0",
  "krw_balance": "530000.00000000", "note": ""
}
```
> `coin_symbol` 은 응답에서 `stock_code` 로 노출(주식 도메인 명칭 통일). 프론트에 coin_ 접두어 노출 금지.

### 3-6. 운영 로그
```
GET /api/v1/users/{userId}/worker-logs
```
쿼리 파라미터: `source`(buy|sell), `level`(INFO|WARN), `from`, `limit`, `offset`.
응답 item:
```json
{
  "log_id": 5001, "user_id": 1, "source": "sell", "level": "INFO",
  "message": "005930 트레일 라인 73,200 이탈 → 시장가 매도 요청",
  "created_at": "2026-07-31T10:12:44"
}
```

---

## 4. 화면 ↔ 엔드포인트 매핑 (web 참고)

| web 화면 영역 | 엔드포인트 |
|---------------|-----------|
| 상단 계좌 요약 카드 | `GET .../account` |
| 보유종목 그리드(+합계행) | `GET .../portfolio` |
| worker 보유 포지션 상세(손절/익절/트레일) | `GET .../positions?status=HOLDING` |
| 매매 이력 탭 | `GET .../positions/history` |
| 거래내역 로그 탭 | `GET .../trade-logs` |
| worker 운영 로그 탭 | `GET .../worker-logs` |

---

## 5. 구현 주의사항

1. **read-only.** web/api 는 이 테이블들을 조회만 한다. 갱신은 trade_worker 전담(부팅/체결/일별 cron). API 에 write 엔드포인트를 두지 않는다.
2. **user_id 권한.** 유저 3명 멀티테넌시. 모든 쿼리에 `user_id` 강제, 인증 주체와 경로 `userId` 일치 검증.
3. **정밀도.** DECIMAL(18,8) 은 문자열로 직렬화(부동소수 반올림 방지).
4. **B/C 혼동 금지.** 계좌 실제 보유는 `user_holdings`(B), worker 매매·매도라인은 `trade_worker_position`(C). 수동매수 종목은 C 에 없을 수 있음.
5. **coin_symbol 네이밍.** `trade_log.coin_symbol` 은 레거시 컬럼명. 주식코드 저장/주식코드 반환. API 응답 키는 `stock_code`.
6. **스냅샷 시점.** `user_wallet.updated_at` / `user_holdings.updated_at` 은 마지막 KIS 동기화 시각. 화면에 "기준시각" 노출 권장(실시간 아님).
7. **인덱스.** 로그 조회는 `(user_id, created_at)` / `(user_id, exec_time)` 인덱스 타게 정렬·필터 구성.
