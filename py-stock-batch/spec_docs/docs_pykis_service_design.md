# pykis 서비스 분리 설계안

작성일: 2026-07-24 (구현 반영: 2026-07-27)
대상 프로젝트: py-stock-batch

---

## 0. 최종 구현 요약 (실제 반영된 것)

> 설계가 두 번 정정됐다. 최종은 **유저별 실매매(주문/체결) worker(상시 daemon)** 다.
> 아래 3~13장은 초기 "조회 proxy" 검토(참고용). 실제 코드는 이 0장을 따른다.

### 역할 분담
- **메인 py-stock-batch** (현행 유지, daily 배치): `StockBuyCheckJob`(종목 마스터 스캔 → 매수타겟 선정,
  `trade_buy_target_stock`), `StockSellCheckJob`(보유 종목 매도 기준선·상태 갱신 = stop/target/trail,
  bars_held, action_type → `trade_sell_target_stock`). **주문은 안 함.**
- **유저별 worker** (같은 이미지, 상시 daemon, 유저당 1 프로세스 — `KIS_USER_ID` 만 다름):
  - **매수 엔진** (09:00 cron): `user_wallet` 잔고>0(현금/watch) & 무보유면 → 전날 타겟 중 과열최저 1종목 →
    시장가 전량 매수 → 체결 → active 등록·잔고 차감.
  - **매도 엔진** (실시간 소켓): active 보유를 pykis 실시간 구독 → 체결가가 stop/target/trail **라인 돌파 시
    즉시 매도**. OBV·타임스탑 등 **일봉 신호는 개장 시** 정리(`apply_open_signals`).
- **부팅 시 잔고 확인**: worker 기동 직후 `broker.account_cash()`로 **실제 KIS 예수금**을 조회해 DB `user_wallet`
  과 대조하고, 다르면 실제값으로 동기화(`SYNC_WALLET_ON_BOOT`, 기본 true). 조회 실패 시 DB 값 유지.
  체결 직후에도 재동기화(`SYNC_WALLET_ON_TRADE`, 기본 true, `wallet_sync.reconcile_wallet`).
- **체결 알림**: 매수/매도 체결 시 `notifier.Notifier` 가 **텔레그램 우선**(user_detail.tele_*), 실패/미설정 시
  **이메일 fallback**(user_master.email, smtpUtils). 이메일은 `smtp.key` 마운트 필요(compose). DRY_RUN/모의도
  모드 태그 붙여 발송.
- **worker 로그 DB 적재**: 매수/매도 executor 의 모든 로그는 `log.info` 대신 `worklog.WorkerLogger` 로
  `trade_worker_log` 테이블에 시간순 적재(user_id·source(buy/sell)·level·message·created_at). 콘솔에도 echo.
  스키마: `sql/20260730_create_trade_worker_log.sql`.
- **안전장치**: `DRY_RUN=true`(로그만)·`KIS_VIRTUAL=true`(모의)가 기본. 실주문은 env 를 명시적으로 바꿔야 함.

### 신규/변경 파일

| 파일 | 내용 |
|------|------|
| `app/ext_services/kis/keyLoader.py` (신규) | `KIS_USER_ID`→`user_detail` 조회+AES 복호화, 없으면 `kis.key` 파일. DB 실패 시 fallback |
| `app/ext_services/kis/KisEngine.py` | `user_id` 인자 추가 → keyLoader 위임. secret 로그출력 제거 |
| `app/trade_worker/` (신규) | 데몬: `main.py`(진입점·cron·소켓), `config.py`, `broker.py`(pykis 주문/소켓+DRY_RUN), `repository.py`(DB), `buy_executor.py`, `sell_executor.py` |
| `app/flask_app/wsgi.py` (신규) | 메인 진입점(스케줄러 ON). 기존 미정의 `app.main:flaskApp` 대체 |
| `Dockerfile` | 메인 CMD 를 `app.flask_app.wsgi:app` 로 교정 |
| `Dockerfile.worker` (신규) | **worker 전용 이미지 `py-stock-worker`**. 메인과 별개로 독립 빌드·배포. `COPY app` 만(시크릿 안 굽음), CMD=데몬 |
| `.dockerignore` (신규) | 빌드 컨텍스트 슬림화(.venv/.git/*.png). `*.key` 는 제외 안 함(메인 유지) |
| `build_worker.sh` (신규) | worker 독립 빌드·기동 스크립트 |
| `docker-compose.pykis.yml` | worker 3개 = **`py-stock-worker` 이미지**(+build), `KIS_USER_ID`만 상이 |
| `sql/20260727_add_kis_keys.sql` | `user_detail` KIS 컬럼 8개 |
| `scripts/import_kis_key.py` | `kis.key`→DB 이관(1회성) |

> 이전 실험(분석 job 유저 스코프·`KIS_BUY_SCAN` guard·`app/worker_app` flask 진입점)은 이 모델과 안 맞아 **롤백**함.

### 적용 순서
① `sql/20260727_add_kis_keys.sql` → ② `python -m scripts.import_kis_key --user-id N --key-file kis.key`(유저별)
→ ③ `docker build -f Dockerfile.worker -t py-stock-worker .` (또는 `./build_worker.sh`)
→ ④ `DB_URL=... docker compose -f docker-compose.pykis.yml up -d`
→ ⑤ `docker logs -f kis-user1` 로 부팅 잔고 동기화·매수/매도 로그 확인(DRY_RUN) → ⑥ 모의(`KIS_VIRTUAL`)로 실주문 검증 → ⑦ 실전 전환.

> 메인 py-stock-batch(`Dockerfile`→`docker-compose.yml`)와 worker(`Dockerfile.worker`→`docker-compose.pykis.yml`)는 **완전히 별개 이미지·배포 파이프라인**이다.

### 체결 확인 (구현됨)
- `broker.start_fill_tracking()` 이 **실시간 체결통보**(`kis.on('execution')`, 실전·모의 모두 지원)를 구독해
  주문번호별 체결수량/가중평균가를 누적. `pending_orders()` 는 **모의 미지원**이라 실전에서만 보조 폴링.
- `wait_fill()` 이 `FILLED / PARTIAL / REJECTED / PENDING` 판정. 매수/매도 executor 는 체결수량·평균가로
  포지션·잔고·`trade_log` 반영하고, 거부/미체결이면 반영하지 않음(유령 포지션 방지).

### 남은 작업 (실계좌 검증 단계)
- 실계좌에서 체결통보 필드 실측 검증(주문번호 매칭·부분체결 누적).
- 부분체결 잔여수량 재주문/정정, 주문 타임아웃 시 취소 정책.
- 장중 포지션 상태(peak_close/high, bars) 실시간 갱신 여부 — 현재는 spec 대로 daily 배치가 갱신.
- 매수 수량/예산 정책 상세(호가단위, 최소수량, 복수 종목 분산 등).

---

## 1. 목적

- 유저가 3명으로 늘어남에 따라, pykis(python-kis) 로직을 **별도 컨테이너**로 분리한다.
- **같은 이미지**를 3개 인스턴스로 띄우고, 각 인스턴스가 유저 1명의 KIS key를 물게 한다.
- 라우팅 목표는 **둘 다**:
  - (A) **유저별 계좌 격리** — sell 계열/주문 계열은 요청의 `user_id`에 맞는 컨테이너로 라우팅.
  - (B) **조회 처리량 분산** — buy check 전체 스캔은 3개 key로 나눠서 rate limit을 우회, 속도 최대 3배.

---

## 2. 현재 구조 (as-is)

- `app/ext_services/kis/KisEngine.py` — pykis를 감싸는 유일한 진입점. 로컬 `kis.key` **하나만** `json.load`로 읽어 `PyKis` 세션 생성.
- 현재 노출 메서드는 조회 전용: `getOHLCV(code, start, end)`, `get_finance_info(code)`. **주문 로직은 아직 없음.**
- 사용처:
  - `app/batches/jobs/StockBuyCheckJob.py` → `KisEngine(virtual=False)` 1개 생성, 전체 종목 스캔.
  - `app/batches/jobs/StockSellCheckJob.py` → `KisEngine(virtual=False)` 1개 생성, 유저별 루프(`get_all_sell_target_users`)를 돌지만 KIS 호출은 공유 엔진 1개 사용.
- 배포: Flask + gunicorn 단일 컨테이너(`Dockerfile`, `docker-compose.yml`, network `aibees`, `172.21.1.5:5557`).

### 문제점
- KIS API rate limit은 **app_key 단위**. 유저 3명이 한 key를 공유하면 병목 + 상호 간섭.
- 계좌 주문을 붙이는 순간, 한 프로세스가 3명 계좌 세션을 섞어 들고 있는 건 위험(토큰 갱신, 격리, 장애 전파).

---

## 3. 목표 구조 (to-be)

```
                     ┌──────────────────────────────────────┐
                     │  py-stock-batch (main, Flask/batch)   │
                     │                                       │
   batch jobs ──────▶│  KisRouter                            │
   (buy/sell)        │   ├─ get_client(user_id)  ← 격리(A)   │
                     │   └─ get_scan_clients()   ← 분산(B)   │
                     │        │        │        │            │
                     └────────┼────────┼────────┼────────────┘
                        HTTP  │  HTTP  │  HTTP  │
                     ┌────────▼─┐ ┌────▼─────┐ ┌▼─────────┐
                     │kis-user1 │ │kis-user2 │ │kis-user3 │  ← 같은 이미지
                     │KIS_USER  │ │KIS_USER  │ │KIS_USER  │     env의 user_id만 다름
                     │  _ID=1   │ │  _ID=2   │ │  _ID=3   │
                     │ PyKis    │ │ PyKis    │ │ PyKis    │     부팅 시 DB에서
                     │ key(DB)  │ │ key(DB)  │ │ key(DB)  │     자기 user_id의 key 조회
                     └────┬─────┘ └────┬─────┘ └────┬─────┘
                          └────────────┼────────────┘
                                    ┌──▼──┐
                                    │ DB  │ user_detail (KIS key, AES 암호화)
                                    └─────┘
```

- **pykis-service**: FastAPI(권장) 마이크로서비스. 이미지 1개, 인스턴스 3개.
  - 각 인스턴스는 **`KIS_USER_ID` env 하나만 다름**. 부팅 시 이 값으로 DB(`user_detail`)에서 자기 유저 KIS key를 조회·AES 복호화 → `PyKis` 세션 1개 생성.
  - key 파일 마운트 불필요. 이미지·설정·공통 aes.key까지 전부 동일하고 오직 env `KIS_USER_ID`만 상이 → 진짜 "동일한 형태 모듈 3개".
  - 각자 자기 key만 독자 사용하므로 **rate limit 병목 없음**.
  - 엔드포인트로 조회를 노출. 추후 주문/잔고 엔드포인트 추가.
- **main app**: `KisEngine`을 HTTP client(`KisClient`)로 대체. 배치 코드는 거의 그대로.
- **KisRouter**: user_id → 컨테이너 매핑(A), 스캔용 클라이언트 풀(B) 제공.

FastAPI 권장 이유: 타입 검증(pydantic), async, 자동 문서(/docs). Flask로 해도 무방하나 신규 서비스이므로 가볍게 시작 권장.

---

## 4. 디렉토리 구조 (신규 서비스)

기존 레포와 분리하거나 모노레포 하위 폴더로 둘 수 있음. 모노레포 하위 예시:

```
py-stock-batch/
├─ app/                         # 기존 메인 배치 (변경 최소)
│   └─ ext_services/kis/
│       ├─ KisClient.py         # (신규) HTTP client — 기존 KisEngine 인터페이스 유지
│       └─ KisRouter.py         # (신규) user_id 라우팅 + 스캔 풀
│
├─ pykis-service/               # (신규) 별도 컨테이너 소스
│   ├─ Dockerfile
│   ├─ pyproject.toml           # pykis, fastapi, uvicorn, pandas, sqlalchemy, pymysql, pycryptodome
│   └─ svc/
│       ├─ main.py              # FastAPI app + 라우트
│       ├─ engine.py            # 기존 KisEngine 로직 이식 (getOHLCV/get_finance_info)
│       ├─ config.py            # KIS_USER_ID env → DB 조회 → AES 복호화 → PyKis 생성
│       ├─ db.py               # DB 세션 + kis key 조회 DAO (aesUtils 재사용)
│       └─ schemas.py           # 요청/응답 pydantic 모델
│
├─ docker-compose.yml           # main + kis-user1/2/3 정의
└─ ...
```

포인트: pykis 의존성(python-kis, pandas 등)이 **신규 서비스 이미지에만** 필요. 메인 이미지에서 pykis 제거 가능 → 이미지 슬림화.

---

## 5. API 스펙 (pykis-service)

베이스: 각 인스턴스 동일. 포트 예: 5561.

| Method | Path              | Body / Query                                  | 응답                                   |
|--------|-------------------|-----------------------------------------------|----------------------------------------|
| GET    | `/health`         | -                                             | `{"status":"ok","user":"user1"}`       |
| GET    | `/whoami`         | -                                             | key가 물고 있는 유저/계좌 정보          |
| POST   | `/ohlcv`          | `{code, start_date, end_date}`                | OHLCV records (list) 또는 `null`       |
| POST   | `/finance`        | `{code}`                                       | `{eps,per,pbr,roe,peg}`                |
| POST   | `/order` (추후)   | `{code, side, qty, price, order_type}`        | 주문 결과                              |
| GET    | `/balance` (추후) | -                                             | 계좌 잔고/보유 종목                     |

### 예시 응답 (/ohlcv)
```json
{
  "code": "005930",
  "count": 2,
  "records": [
    {"datetime":"2026-07-23 00:00:00","open":81000,"high":82000,"low":80500,"close":81500,"volume":12345678}
  ]
}
```
- 기존 `KisEngine.getOHLCV`가 DataFrame을 반환하므로, 서비스에서 `df.to_dict(orient="records")`로 직렬화하고, 클라이언트에서 다시 `pd.DataFrame(records)`로 복원.
- `KisNotFoundError` → HTTP 200 + `records: null` (기존 `None` 반환 시맨틱 유지) 또는 404. 기존 배치가 `None` 체크를 하므로 **`null`로 통일** 권장.

---

## 6. key 관리 — env user_id 고정 + DB 조회 (채택)

파일 마운트 대신, **컨테이너는 `KIS_USER_ID` env만 다르게** 하고 실제 key는 DB에서 조회한다. 기존 upbit key가 `user_detail`에 AES 저장되는 패턴과 동일하게 KIS key도 저장.

### 6-1. DB 스키마 추가 (`user_detail`)
현재 `user_detail`에는 upbit key만 있음. KIS 컬럼을 추가한다 (secret 계열은 AES 암호화 저장):

| 컬럼                   | 타입          | 비고                          |
|------------------------|--------------|-------------------------------|
| `kis_id`               | VARCHAR(50)  | 실전 id (kis.key의 `id`)      |
| `kis_account`          | VARCHAR(50)  | 실전 계좌번호                 |
| `kis_app_key`          | VARCHAR(200) | AES 암호화                    |
| `kis_sec_key`          | VARCHAR(500) | AES 암호화 (secret이 길어 여유) |
| `kis_virtual_id`       | VARCHAR(50)  | 모의 id                       |
| `kis_virtual_account`  | VARCHAR(50)  | 모의 계좌번호                 |
| `kis_vir_app_key`      | VARCHAR(200) | AES 암호화                    |
| `kis_vir_sec_key`      | VARCHAR(500) | AES 암호화                    |

> upbit는 현재 decrypt가 주석 처리되어 raw 저장 상태(userMasterDao 95번 라인). KIS는 처음부터 **암호화 저장 + 복호화 조회**로 일관되게 가는 걸 권장. 실전/모의 계좌번호·id는 민감도 낮아 평문도 무방.

### 6-2. 기존 kis.key → DB 이관 (1회)
3명분 `kis.key` JSON을 읽어 `aesUtils.encrypt`로 secret을 암호화한 뒤 `user_detail`에 UPSERT하는 일회성 마이그레이션 스크립트 작성. 이후 `kis.key` 파일은 폐기(레포에서 제거).

### 6-3. 서비스 부팅 로직 (`svc/config.py`)
```python
KIS_USER_ID = int(os.environ["KIS_USER_ID"])   # 컨테이너마다 1/2/3
row = select_kis_key(session, KIS_USER_ID)      # user_detail 조회
kis = PyKis(
    id=row["kis_id"],
    account=row["kis_account"],
    appkey=aesUtils.decrypt(row["kis_app_key"]),
    secretkey=aesUtils.decrypt(row["kis_sec_key"]),
    keep_token=True,
)  # virtual=True면 virtual_* 필드로
```

### 6-4. 서비스가 필요로 하는 것
- **DB 접근**: `db.py`에서 sqlalchemy 세션 생성(기존 `app/config/database.py`와 동일 접속 정보). → 서비스 pyproject에 sqlalchemy, pymysql 포함.
- **aes.key**: 복호화용. 3개 컨테이너 **공통**이므로 read-only 마운트 1개(또는 env `AES_KEY`)로 주입. user_id별로 다르지 않음 → "동일 이미지" 원칙 유지.
- **토큰 캐시**: `keep_token=True` 캐시를 컨테이너별 named volume에 저장해 재시작 시 재로그인 최소화.

### user_id ↔ 컨테이너 매핑 (메인 앱)
컨테이너 이름/URL과 user_id 매핑은 메인 앱 env로 관리:
```
KIS_ROUTE_MAP={"1":"http://kis-user1:5561","2":"http://kis-user2:5561","3":"http://kis-user3:5561"}
KIS_SCAN_POOL=http://kis-user1:5561,http://kis-user2:5561,http://kis-user3:5561
```

---

## 7. 라우팅 로직 (KisRouter, 메인 앱)

### (A) 유저별 계좌 격리 — sell/주문 계열
```python
class KisRouter:
    def get_client(self, user_id: int) -> KisClient:
        base = self.route_map[str(user_id)]
        return KisClient(base_url=base)
```
`StockSellCheckJob`의 유저 루프에서 `self.kisRouter.get_client(user.user_id)`로 해당 유저 컨테이너를 사용 → 계좌/주문이 자기 key로만 나감.

### (B) 조회 처리량 분산 — buy check 전체 스캔
```python
def get_scan_clients(self) -> list[KisClient]:
    return [KisClient(b) for b in self.scan_pool]
```
`StockBuyCheckJob`에서 종목 리스트를 3등분(또는 라운드로빈)하여 3개 클라이언트로 **병렬** 조회. 각 컨테이너가 독립 rate limit이라 `time.sleep(1.5)` 병목이 1/3로 감소.

> 병렬화는 기존 `app/common/utils/threadExecutor.py`(ThreadPoolExecutor)를 재사용하되, 클라이언트별로 스레드를 분리해 한 컨테이너에는 순차 호출(rate limit 준수)이 되도록 구성.

---

## 8. 메인 앱 변경점 (최소 침습)

`KisClient`가 기존 `KisEngine`과 **동일한 메서드 시그니처**(`getOHLCV`, `get_finance_info`)를 갖게 하면, 배치 잡 수정이 거의 없다.

```python
# as-is
self.kis = KisEngine(virtual=False)

# to-be (격리)
self.kisRouter = KisRouter()
kis = self.kisRouter.get_client(user_id)   # 유저 루프 안에서
ohlcv = kis.getOHLCV(code, start, end)     # 인터페이스 동일
```

`KisClient.getOHLCV`는 내부적으로 `POST /ohlcv` 호출 후 `pd.DataFrame(records)` 반환. 배치의 이후 로직(`compute_indicator_df` 등)은 무변경.

---

## 9. docker-compose (초안)

```yaml
services:
  app:
    image: py-stock-batch
    container_name: stock-batch-flask-app
    environment:
      - KIS_ROUTE_MAP=${KIS_ROUTE_MAP}
      - KIS_SCAN_POOL=${KIS_SCAN_POOL}
    ports: ["5557:5557"]
    networks: { aibees: { ipv4_address: 172.21.1.5 } }
    depends_on: [kis-user1, kis-user2, kis-user3]

  kis-user1:
    image: pykis-service
    container_name: kis-user1
    environment:
      - KIS_USER_ID=1            # ← 컨테이너마다 이 값만 다름
      - KIS_VIRTUAL=false
      - DB_URL=${DB_URL}          # 3개 공통
    volumes:
      - ./aes.key:/workdir/aes.key:ro   # 3개 공통 (복호화용)
      - kis1_token:/root/.pykis
    networks: { aibees: {} }

  kis-user2:
    image: pykis-service
    container_name: kis-user2
    environment: [ KIS_USER_ID=2, KIS_VIRTUAL=false, "DB_URL=${DB_URL}" ]
    volumes:
      - ./aes.key:/workdir/aes.key:ro
      - kis2_token:/root/.pykis
    networks: { aibees: {} }

  kis-user3:
    image: pykis-service
    container_name: kis-user3
    environment: [ KIS_USER_ID=3, KIS_VIRTUAL=false, "DB_URL=${DB_URL}" ]
    volumes:
      - ./aes.key:/workdir/aes.key:ro
      - kis3_token:/root/.pykis
    networks: { aibees: {} }

volumes: { kis1_token: {}, kis2_token: {}, kis3_token: {} }
networks: { aibees: { external: true } }
```
> 3개 컨테이너 모두 같은 `pykis-service` 이미지 + 같은 aes.key + 같은 DB. **다른 건 오직 `KIS_USER_ID`.** 이게 "동일한 형태 모듈 3개". key 파일 마운트 없음 — 각자 DB에서 자기 user_id로 조회.

---

## 10. Dockerfile (pykis-service 초안)

```dockerfile
FROM python:3.12.3
ENV POETRY_VERSION=1.8.2
RUN pip install -U "poetry==$POETRY_VERSION"
WORKDIR /workdir
COPY ../pyproject.toml poetry.lock /workdir/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi
COPY svc /workdir/svc
# key는 COPY 하지 않음 — 볼륨/시크릿 마운트
CMD ["uvicorn", "svc.main:app", "--host", "0.0.0.0", "--port", "5561", "--workers", "1"]
```
> `--workers 1` 권장: pykis 세션/토큰을 워커별로 중복 생성하지 않도록. 처리량은 컨테이너 수(3개)로 확보.

---

## 11. 마이그레이션 단계

1. **DB 스키마**: `user_detail`에 KIS 컬럼 8개 추가 (ALTER TABLE, sql/ 에 migration 파일).
2. **key 이관**: 3명분 `kis.key` JSON → `aesUtils.encrypt` → `user_detail` UPSERT 하는 1회성 스크립트 실행. 이후 `kis.key` 파일 폐기.
3. `pykis-service/` 스캐폴딩 + `KisEngine` 로직을 `svc/engine.py`로 이식. key 로딩만 파일 → DB(`svc/config.py`, `svc/db.py`)로 교체.
4. FastAPI 라우트(`/health`, `/whoami`, `/ohlcv`, `/finance`) 작성, DataFrame ↔ records 직렬화.
5. 단일 인스턴스(`KIS_USER_ID=1`)로 기동, `/ohlcv` 응답이 기존 `KisEngine.getOHLCV`와 동일한지 대조 검증. `/whoami`로 올바른 계좌 물었는지 확인.
6. 메인 앱에 `KisClient` + `KisRouter` 추가. `StockSellCheckJob`부터 라우터로 교체(격리 A 검증).
7. `StockBuyCheckJob`을 스캔 풀 분산으로 교체(분산 B 검증).
8. compose로 3인스턴스(`KIS_USER_ID=1/2/3`) 기동 → 라우팅/격리 실측.
9. 메인 이미지 `pyproject.toml`에서 `python-kis` 제거(선택).

---

## 12. 리스크 / 체크포인트

- **토큰 동시 갱신**: 컨테이너별 named volume로 토큰 캐시 분리 필수. 공유 시 401 루프 위험.
- **네트워크 홉 지연**: 조회당 HTTP 왕복 추가. 스캔 분산(B)의 병렬 이득이 이를 상쇄. 내부 네트워크(aibees)라 지연 미미.
- **부분 장애**: 컨테이너 1개 다운 시 해당 유저만 영향(격리 이점). 메인 앱은 `/health` 체크 후 라우팅 + 재시도.
- **rate limit 준수**: 한 컨테이너 내부는 여전히 순차 호출 유지(기존 sleep 로직을 서비스 or 클라이언트 한쪽에 유지).
- **주문 추가 시**: `/order`는 반드시 유저별 격리 경로(A)로만. 스캔 풀(B)로 주문 금지 → 라우터에서 물리적으로 분리.
- **key 보안**: 이미지에 key/aes.key COPY 금지. aes.key는 read-only 마운트만, 레포 커밋 금지. KIS secret은 DB에 AES 암호화 저장.
- **DB 의존**: 서비스가 부팅 시 DB를 읽으므로, DB 기동 후 서비스가 뜨도록 `depends_on`/헬스체크 + 조회 실패 시 재시도. key 없으면 fail-fast로 로그 남기고 종료.
- **버추얼/실전 스위치**: `KIS_VIRTUAL` env로 제어. 모의/실전 계좌를 컨테이너 단위로 분리 가능(예: kis-user1-vir).

---

## 13. 요약

가능하고, 방향은 "같은 pykis-service 이미지 3인스턴스 + 메인 앱 KisRouter"가 최적. **각 컨테이너는 `KIS_USER_ID` env만 다르고**, 부팅 시 DB(`user_detail`)에서 자기 유저 KIS key를 조회·복호화해 PyKis 세션을 만든다. key 파일 마운트가 사라져 이미지·aes.key·DB까지 전부 동일 → 진짜 "동일한 형태 모듈 3개". 각자 자기 key만 쓰므로 rate limit 병목 없음. 격리(A)와 분산(B)는 라우터의 `get_client(user_id)` / `get_scan_clients()`로 동시 충족. 배치 잡은 `KisClient`가 `KisEngine` 인터페이스를 흉내내 변경 최소.

선행 작업은 DB 스키마 추가 + kis.key→DB 이관(11번 1~2단계). 실제 스캐폴딩/코드 구현을 원하면 그 순서로 진행.
