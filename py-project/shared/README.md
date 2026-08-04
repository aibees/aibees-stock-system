# stock-shared

`py-naver-stock-theme` 와 `py-stock-batch` 가 공용으로 쓰는 ORM 모델 / DAO 패키지.

모델은 **운영 DB(`stock`) 스키마를 정본**으로 삼아 생성했다. 두 프로젝트에 흩어져 있던
모델 정의가 서로, 그리고 DB와 어긋나 있었기 때문에 코드가 아니라 DB를 기준으로 통일했다.

## 구성

```
stock_shared/
├── base.py          공용 declarative Base (모든 모델이 이것 하나만 상속)
├── models/          ORM 모델 15개
├── dao/             공용 DAO 7개 (BaseDao + 6)
└── vo/              UserCoinInfo (DAO 시그니처에 필요)
```

## 포함된 모델 (15)

| 모델 | 테이블 | 컬럼 |
|---|---|---|
| BatchJobMaster | batch_job_master | 8 |
| MasterStock | master_stock | 10 |
| NStockBatchLog | stock_batch_log | 7 |
| StockSellRequest | stock_sell_request | 10 |
| TradeBuyTargetStock | trade_buy_target_stock | 24 |
| TradeCandleData | trade_candle_data | 50 |
| UserDetail | user_detail | 21 |
| UserInterestGroups | user_interest_groups | 4 |
| UserInterestStocks | user_interest_stocks | 6 |
| UserMaster | user_master | 6 |
| UserOptions | user_options | 44 |
| UserWallet | user_wallet | 5 |
| UserAuth | user_auth | 5 |
| UserLoginType | user_login_type | 3 |
| UserRole | user_role | 2 |

`trade_log` 는 제외했다. 운영(`stock`)과 개발(`stock_dev`) 스키마가 서로 다르고
(`stock` 은 `created_at` 보유 / `stock_dev` 는 `sma_checker` 등 6개 보유),
어느 쪽을 정본으로 할지 정리된 뒤에 합류시킨다.

## 설치

각 프로젝트 `pyproject.toml` 에 path dependency 를 추가한다.

```toml
[tool.poetry.dependencies]
stock-shared = { path = "../shared", develop = true }
```

## 사용

```python
from stock_shared.models import MasterStock, UserOptions
from stock_shared.dao import MasterStockDao

dao = MasterStockDao()
rows = dao.select_all_stocks(session)
```

## Docker

빌드 컨텍스트를 `py-project/` 로 올려야 `shared` 가 컨텍스트에 포함된다.
Docker 는 컨텍스트 밖(`../shared`)을 COPY 할 수 없다.

```dockerfile
COPY shared /shared
COPY py-stock-batch/pyproject.toml py-stock-batch/poetry.lock /workdir/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi
COPY py-stock-batch/ /workdir/
```

```bash
# py-project/ 에서 실행
docker build -f py-stock-batch/Dockerfile -t py-stock-batch .
```

`py-project/.dockerignore` 로 컨텍스트를 슬림하게 유지할 것.

## 모델 재생성

DB 스키마가 바뀌면 모델도 DB 기준으로 갱신한다. 손으로 고치지 말고
`information_schema` 를 읽어 재생성한 뒤, 컬럼명/타입/nullable/PK 를 대조 검증할 것.

## 통합 시 제외한 메서드

원본에 있었으나 호출 시 반드시 실패하는 코드라 shared 로 옮기지 않았다.

| 메서드 | 원본 | 사유 |
|---|---|---|
| `MasterStockDao.update_stock_finance_info` | py-stock-batch | `master_stock` 에 없는 `per`/`pbr`/`roe` 참조. 호출처 없음 |
| `UserMasterDao.select_user_by_phone` | py-naver-stock-theme | `user_master` 에 없는 `type` 컬럼 참조. **호출처 있음** (`authService.py:52`) |

`select_user_by_phone` 은 호출처가 살아 있으므로 마이그레이션 시 함께 정리해야 한다.
로그인 타입은 `user_login_type.login_type` 이므로 `select_user_authinfo()` 를 쓰거나
`UserLoginType` 을 조인하는 형태로 새로 구현할 것.

## 동작이 바뀐 부분

- `UserMasterDao.update_interest_stock` : 원본(py-stock-batch)은 내부에서
  `session.commit()` 을 호출했으나 DAO 가 트랜잭션 경계를 정하지 않도록 제거했다.
  **호출측에서 커밋해야 한다.**
- `StockSellRequestDao.update_enabled_flag` / `update_by_user_key` :
  `updated_at` 을 함께 갱신한다(py-stock-batch 동작 기준).
- `BatchJobMasterDao.select_batch_master_running` :
  `select_enabled_jobs` 의 별칭으로 유지했다(py-stock-batch 호환).
