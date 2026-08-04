# 📈 py-stock-batch

> 국내 주식 · 가상자산(코인) 자동 분석/매매 신호를 위한 Python 배치 & API 서버

`py-stock-batch`는 한국투자증권(KIS) · 키움증권 · 업비트 등 외부 거래소/데이터 API를 연동하여
**종목·테마 마스터 수집 → 캔들 데이터 적재 → 전략 기반 매수 후보 산출 → 알림 발송**까지의 파이프라인을
APScheduler 기반 배치로 자동 실행하고, Flask REST API로 배치를 제어할 수 있는 서버입니다.

---

## ✨ 주요 기능

- **종목/테마 마스터 수집** — KOSPI·KOSDAQ 종목코드 마스터, 키움 테마 그룹/구성종목 자동 갱신
- **시세·캔들 데이터 적재** — OHLCV 캔들 데이터 수집 및 DB 저장
- **전략 기반 매수 후보 산출** — KOSPI 전략(`KospiStrategy1`), 업비트 전략(`UpbitStrategy1/2`)으로 매수 타겟 종목 스코어링
- **사용자별 자동 점검** — 사용자 옵션/관심종목 기준으로 매수 신호 점검 및 이메일 알림 발송
- **배치 스케줄링** — DB의 배치 마스터(`batchJobMaster`)에 등록된 cron 설정으로 작업 자동 실행
- **REST API 제어** — 배치 즉시 실행, 상태 조회, 실행 중 작업 확인, 스케줄 리로드

---

## 🏗️ 아키텍처

```
                ┌─────────────────────────────────────────────┐
                │              Flask App (port 5557)           │
                │   /api/v1/jobs  ──  배치 제어 REST API        │
                └───────────────┬─────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        │            APScheduler (ProcessPool)            │
        │   batchJobMaster(DB)의 cron 설정으로 Job 등록    │
        └───────────────────────┬───────────────────────┘
                                │  process()
        ┌───────────────────────┴───────────────────────┐
        │                    Batch Jobs                   │
        │  StockCodeMaster · StockThemeMaster             │
        │  StockBuyCheck · StockFinCheck · UpbitBuyCheck  │
        └───────────────────────┬───────────────────────┘
                                │
   ┌────────────────┬───────────┴─────────┬───────────────────┐
   │  ext_services  │      services       │      domain        │
   │  KIS / Kiwoom  │  Stock / User       │  DAO · Model (ORM) │
   │  Upbit / yfin  │  전략 · 스코어링     │  SQLAlchemy        │
   └────────────────┴─────────────────────┴───────────────────┘
                                │
                          ┌─────┴─────┐
                          │   MySQL    │
                          └───────────┘
```

---

## 📁 프로젝트 구조

```
app/
├── main.py                  # 엔트리포인트 (Flask 인스턴스 노출)
├── flask_app/               # Flask 앱 · 라우터 · 응답 유틸
│   ├── runner.py            # FlaskApp 정의, DB 세션 라이프사이클, 스케줄러 기동
│   └── router/router_job.py # 배치 제어 API (/api/v1/jobs)
├── scheduler_app/
│   └── runner.py            # APScheduler(ProcessPool) 기반 배치 스케줄러
├── batches/
│   ├── jobs/                # 배치 Job 정의 (Job 추상클래스 상속)
│   │   ├── StockCodeMasterJob.py    # 종목코드 마스터 갱신
│   │   ├── StockThemeMasterJob.py   # 키움 테마 마스터 갱신
│   │   ├── StockBuyCheckJob.py      # 주식 매수 신호 점검
│   │   ├── StockFinCheckJob.py      # 재무 점검
│   │   └── UpbitBuyCheckJob.py      # 업비트 매수 신호 점검
│   └── services/            # StockService · UserService (비즈니스 로직)
├── ext_services/            # 외부 거래소/데이터 API 연동
│   ├── kis/                 # 한국투자증권(KIS) · DART 엔진, 전략
│   ├── kiwoom/              # 키움증권 엔진
│   ├── upbit/               # 업비트(ccxt) 엔진, 전략, 스코어링
│   └── yfinance/            # yfinance 엔진
├── domain/
│   ├── model/               # SQLAlchemy ORM 모델
│   ├── dao/                 # 데이터 액세스 객체
│   └── dto/                 # 데이터 전송 객체
├── config/                  # DB 연결 · 컨텍스트 매니저
└── common/                  # 상수 · 유틸 (AES, SMTP, 메일 템플릿 등)
```

---

## 🛠️ 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| 언어 | Python 3.13 |
| 웹 | Flask, Flask-CORS, Gunicorn |
| 스케줄러 | APScheduler (ProcessPoolExecutor) |
| DB / ORM | MySQL, SQLAlchemy 2.0, PyMySQL |
| 데이터 | pandas, numpy, scipy, matplotlib |
| 거래소/데이터 API | python-kis(KIS), 키움 REST, ccxt(Upbit), yfinance, FinanceDataReader, OpenDartReader |
| 기타 | BeautifulSoup4, lxml, pycryptodome(AES), python-dotenv |
| 패키지 관리 | Poetry |

---

## 🚀 시작하기

### 1. 사전 요구사항

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- MySQL 인스턴스
- 거래소/데이터 API 키 (KIS, 키움, 업비트 등)

### 2. 설치

```bash
poetry install
```

### 3. 환경 변수

DB 연결 정보는 `DB_URL` 환경 변수로 주입합니다. (미설정 시 기본값 사용)

```bash
export DB_URL="mysql+pymysql://<user>:<password>@<host>:<port>/<database>"
```

API 키 파일(`kis.key`, `kw.key`, `dart.key`, `smtp.key`, `aes.key` 등)은
루트 디렉터리에 위치시킵니다. **민감 정보이므로 절대 커밋하지 마세요.**

### 4. 실행

```bash
# 개발 실행
poetry run python -m app.main

# 운영 실행 (Gunicorn)
poetry run gunicorn -w 1 -b 0.0.0.0:5557 app.main:flaskApp
```

서버 기동 시 APScheduler가 자동으로 시작되어 DB에 등록된 배치를 스케줄링합니다.

---

## 🐳 Docker 실행

```bash
# 이미지 빌드 + 기동 (어느 디렉터리에서 실행해도 됨)
sh build_docker.sh
```

수동으로 할 경우, 빌드 컨텍스트는 상위 `py-project/` 입니다.
공용 패키지 `shared` 가 컨텍스트에 포함되어야 poetry path dependency 가 해석됩니다.

```bash
cd ..                                    # py-project/
docker build -f py-stock-batch/Dockerfile -t py-stock-batch .
docker compose -f py-stock-batch/docker-compose.yml up -d   # 포트 5557
```

> `docker-compose.yml`은 외부 네트워크 `aibees`를 사용합니다. 환경에 맞게 조정하세요.

---

## 🔌 API

Base URL: `http://<host>:5557/api/v1/jobs`

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET`  | `/status` | 등록된 모든 배치의 상태(다음 실행시각·트리거) 조회 |
| `GET`  | `/running` | 현재 실행 중인 배치 조회 |
| `GET`  | `/reload` | DB의 배치 마스터를 다시 읽어 스케줄 재등록 |
| `POST` | `/once/<job_id>` | 지정한 배치를 백그라운드에서 즉시 1회 실행 (JSON body로 파라미터 전달 가능) |

**예시 — 배치 즉시 실행**

```bash
curl -X POST http://localhost:5557/api/v1/jobs/once/StockCodeMasterJob \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## ⚙️ 배치 동작 원리

- 모든 배치는 `Job` 추상 클래스를 상속하며 `run_batch(**kwargs)`에 로직을 구현합니다.
- 배치 시작/종료/실패는 `batchLog`에 자동 기록되며, 예외 발생 시 롤백 후 `FAIL` 상태로 마감합니다.
- 스케줄러는 `ProcessPoolExecutor`로 동작하므로, 자식 프로세스 진입 시 부모로부터 fork된 DB 커넥션 풀을
  `engine.dispose()`로 폐기하여 커넥션 공유로 인한 쿼리 오염을 방지합니다.
- bound method 대신 module-level 래퍼(`_execute_job`)를 등록하여 직렬화 불가 객체로 인한 `PicklingError`를 회피합니다.

---

## 📝 라이선스

내부 프로젝트입니다. 별도 명시가 없는 한 외부 배포를 금합니다.
