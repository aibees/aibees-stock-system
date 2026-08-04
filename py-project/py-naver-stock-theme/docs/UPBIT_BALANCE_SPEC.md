# Upbit Balance 조회 API — 개발 적용 명세서

> 프로젝트: `py-naver-stock-theme`
> 작성일: 2026-07-21
> 목적: 다른 프로젝트(서버)가 Upbit 거래소 잔고를 조회하도록 서버간 API를 신규 추가한 내역 정리 (핸드오프용)

---

## 1. 개요

`upbitEngine`(ccxt 기반) 위에 **router → service → engine** 계층을 얹어, 특정 사용자의 Upbit 잔고를 조회하는 서버간 API를 추가했다.

- 인증정보(access/secret)는 `user_detail` 테이블에 사용자별로 저장하고, `UserOptionMeta` VO에 실어 엔진에 전달한다.
- 엔드포인트는 다른 프로젝트가 호출하는 **서버간 API**이며, `maria-Authorization` 헤더의 공유 시크릿으로 보호한다.
- 기존 KIS 연동 패턴(`KisEngine` + `user_detail.kis_*` + `select_kis_credentials`)을 그대로 미러링했다.

---

## 2. 엔드포인트

```
GET /api/v1/upbit/balance
```

### 요청

| 항목 | 위치 | 필수 | 설명 |
|------|------|------|------|
| `maria-Authorization` | Header | ✅ | 서버간 공유 시크릿 (`MARIA_AUTH_TOKEN`과 일치해야 함) |
| `user_id` | Query | ✅ | 조회 대상 사용자 ID (정수) |
| `coin` | Query | ❌ | 특정 코인 심볼(예: `BTC`). 미지정 시 계좌 전체 요약 |

### 응답

성공 포맷은 프로젝트 공통 `ApiResponse.success` 규약을 따른다: `{ "success": true, "data": ... }`

**coin 미지정 — 계좌 요약**
```json
{
  "success": true,
  "data": {
    "krw_balance": 152340.0,
    "holdings": [
      { "coin": "BTC", "free": 0.01, "used": 0.0, "total": 0.01 },
      { "coin": "ETH", "free": 0.5,  "used": 0.0, "total": 0.5 }
    ]
  }
}
```
- `krw_balance`: KRW 예수금(free)
- `holdings`: `total > 0` 인 코인만 포함 (KRW 제외)

**coin 지정 — 단일 코인**
```json
{
  "success": true,
  "data": { "coin": "BTC", "free": 0.01, "used": 0.0, "total": 0.01 }
}
```

**에러**
```json
{ "success": false, "error": { "message": "..." } }
```
| 상황 | HTTP | 메시지 |
|------|------|--------|
| maria-Authorization 불일치/누락 | 401 | 서버간 인증 토큰이 유효하지 않습니다. |
| 서버 토큰 미설정(fail-closed) | 401 | 서버 인증 설정 오류입니다. |
| `user_id` 누락 | 400 | user_id 는 필수입니다. |
| 사용자 없음 / Upbit 키 미설정 | 400 | (상세 메시지) |
| 기타 예외 | 400 | (예외 메시지) |

### 호출 예시
```bash
curl -H "maria-Authorization: <MARIA_AUTH_TOKEN>" \
  "https://<host>/api/v1/upbit/balance?user_id=1&coin=BTC"
```

---

## 3. 아키텍처 / 데이터 흐름

```
[다른 프로젝트]
   │  GET /api/v1/upbit/balance  (maria-Authorization 헤더)
   ▼
router_upbit.py  ── require_maria_auth (헤더 검증, 상수시간 비교)
   │  g.db, user_id, coin
   ▼
UpbitService.get_balance(session, user_id, coin)
   │  1) UserDetailDao.select_upbit_credentials → {access, secret}
   │  2) UserOptionMeta.access_key / secret_key 세팅
   │  3) CcxtUpbit(access, secret)
   ▼
CcxtUpbit.get_current_balance(coin)  ── ccxt → Upbit REST
   │  잔고 원본
   ▼
UpbitService 응답 정형화 → ApiResponse.success
```

---

## 4. 변경/추가 파일

| 파일 | 유형 | 내용 |
|------|------|------|
| `app/ext_services/upbit/upbitEngine.py` | 기존 | `CcxtUpbit` — ccxt Upbit 래퍼 (`get_current_balance`) |
| `app/domains/models/userDetail.py` | 수정 | `upbit_access_key`, `upbit_secret_key` 컬럼 + `to_dict` 반영 |
| `app/domains/dao/userDetailDao.py` | 수정 | `select_upbit_credentials(session, user_id)` 추가 |
| `app/services/upbit/__init__.py` | 신규 | 패키지 초기화 |
| `app/services/upbit/upbitService.py` | 신규 | `UpbitService` — 키 로드 → 엔진 호출 → 응답 정형화 |
| `app/flask_app/routers/router_upbit.py` | 신규 | `upbit_bp`, `require_maria_auth`, `GET /balance` |
| `app/flask_app/routers/__init__.py` | 수정 | `upbit_bp` 등록 (`url_prefix="/api/v1/upbit"`) |
| `pyproject.toml` | 수정 | `ccxt = "^4.4.0"` 의존성 추가 |
| `.env.mcp`, `.env.mcp.example` | 수정 | `MARIA_AUTH_TOKEN` 항목 추가 |

---

## 5. DB 스키마

`user_detail` 테이블에 Upbit 인증 컬럼 2개를 추가한다. (모델은 반영됨, **실 DB ALTER는 별도 수행 필요**)

```sql
ALTER TABLE user_detail
  ADD COLUMN upbit_access_key VARCHAR(200) NULL AFTER kis_secret_key,
  ADD COLUMN upbit_secret_key VARCHAR(200) NULL AFTER upbit_access_key;
```

- 사용자별로 본인 Upbit access/secret을 저장.
- 값은 개인설정 화면(`PATCH /api/v1/user-options`)을 통해 저장하도록 확장하려면 `router_user_options.py`의 `WHITELIST['user_detail']` 및 `UserOptionsDao.update_user_detail` ALLOWED 집합에 두 컬럼을 추가해야 한다. (이번 범위에는 미포함 — 필요 시 후속 작업)

---

## 6. 인증 (maria-Authorization)

### 배경
기존에는 `maria-Authorization` 검증 로직이 `runner.py`에 주석 처리된 채로 **실제 동작하지 않았다**. 이번에 서버간 인증을 실체화했다.

### 방식
- 사전 공유 시크릿을 env `MARIA_AUTH_TOKEN`으로 주입.
- `require_maria_auth` 데코레이터가 요청 헤더 `maria-Authorization`을 `hmac.compare_digest`로 **상수시간 비교**.
- 서버에 토큰이 설정돼 있지 않으면 **fail-closed**(401)로 막는다.
- 호출측과 서버가 **반드시 동일한 값**을 공유해야 한다.

### 설정
`.env.mcp`:
```
MARIA_AUTH_TOKEN=<강한 랜덤 시크릿>
```

### 적용 범위 (주의)
현재 이 인증은 **`/api/v1/upbit/*` 에만** 적용된다. 배치 등 다른 서버간 라우터는 여전히 인증이 없다. 전 구간을 묶으려면 `runner.py`의 주석된 `before_request` 필터를 살려 `/api/v1/*` 전역에 적용하는 별도 작업이 필요하다.

---

## 7. 배포 전 체크리스트

1. **DB 마이그레이션**: 위 `ALTER TABLE` 실행 (`upbit_access_key`, `upbit_secret_key`).
2. **의존성 설치**: `poetry lock && poetry install` — `ccxt`가 기존 미등록 상태였음. 미설치 시 blueprint import 단계에서 앱 부팅 크래시.
3. **env 설정**: 운영/호출측 양쪽에 동일한 `MARIA_AUTH_TOKEN` 배포.
4. **사용자 키 적재**: 대상 `user_id`의 `upbit_access_key/upbit_secret_key` 값이 채워져 있는지 확인.
5. **스모크 테스트**:
   ```bash
   curl -H "maria-Authorization: <TOKEN>" \
     "http://localhost:<port>/api/v1/upbit/balance?user_id=1"
   ```

---

## 8. 참고 코드 스니펫

**Service 핵심 (`upbitService.py`)**
```python
def _load_user_info(self, session, user_id):
    creds = self.userDetailDao.select_upbit_credentials(session, user_id)
    if creds is None:
        raise ValueError(f"user_detail(user_id={user_id}) 레코드를 찾을 수 없습니다.")
    access, secret = creds.get('access'), creds.get('secret')
    if not access or not secret:
        raise ValueError(f"user_detail(user_id={user_id})에 UPBIT 인증키가 설정되지 않았습니다.")
    ui = UserOptionMeta()
    ui.user_id = str(user_id)
    ui.access_key, ui.secret_key = access, secret
    return ui

def get_balance(self, session, user_id, coin=None):
    ui = self._load_user_info(session, user_id)
    engine = CcxtUpbit(ui.access_key, ui.secret_key)
    ...
```

**Router 인증 (`router_upbit.py`)**
```python
MARIA_AUTH_TOKEN = os.getenv("MARIA_AUTH_TOKEN", "<default>")

def require_maria_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not MARIA_AUTH_TOKEN:
            return ApiResponse.unauthorized("서버 인증 설정 오류입니다.")
        token = request.headers.get('maria-Authorization', '')
        if not hmac.compare_digest(token, MARIA_AUTH_TOKEN):
            return ApiResponse.unauthorized("서버간 인증 토큰이 유효하지 않습니다.")
        return f(*args, **kwargs)
    return decorated
```
