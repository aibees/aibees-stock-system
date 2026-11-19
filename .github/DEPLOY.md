# 배포 (GitHub Actions + self-hosted runner)

서비스 6개를 각각 따로 배포한다. 워크플로 하나 = 서비스 하나.

| 워크플로 | 대상 | 서버(runner 라벨) | 언제 |
|---|---|---|---|
| `deploy-yangbong-fe.yml` | 양봉상회 웹 `yangbong-vue-app` | 클라우드 (`cloud`) | `yangbong-store-vue/` push 시 자동 + 수동 |
| `deploy-secret-fe.yml` | 비밀상회 웹 `secret-vue-app` | 클라우드 (`cloud`) | `secret-store-vue/` push 시 자동 + 수동 |
| `deploy-web-be.yml` | 비밀상회 API `stock-web-flask-app` (이미지 `py-stock-web`) | 홈 (`home`) | `py-secret-api/`·`shared/` push 시 자동 + 수동 |
| `deploy-yangbong-be.yml` | 양봉상회 API `yangbong-web-flask-app` + AI 워커 `yangbong-ai-worker` (이미지 `py-yangbong-web`) — **떠 있을 때만 교체**, 처음 기동은 손으로 | 홈 (`home`) | `py-yangbong-api/`·`shared/` push 시 자동 + 수동 |
| `deploy-batch-be.yml` | 배치 `stock-batch-flask-app` | 홈 (`home`) | **수동만** (돌던 배치가 끊기므로) |
| `deploy-kis-workers.yml` | 워커 `kis-user1~4` | 워커 서버 (`worker`) | **수동만**, 평일 07:30~20:10 KST 차단(force 로 우회) |

## 동작 방식

- runner 가 저장소를 새로 받지 않는다. **서버에 이미 있는 clone 폴더**에서 `git pull` 후 빌드한다.
  그래서 gitignore 된 `.env`, `.env.prd`, `.env.yangbong`(이제 `py-yangbong-api/` 안), `aes.key`, `firebase-service-account.json` 등은 지금처럼 서버에만 두면 된다. GitHub Secrets 는 쓰지 않는다.
- 레지스트리를 쓰지 않는다. 이미지는 지금처럼 각 서버에서 로컬 빌드한다.
- 새 이미지 빌드가 성공한 뒤에만 컨테이너를 바꾼다. 빌드가 깨지면 기존 컨테이너가 그대로 남는다.
- runner 는 서버로 들어오는 포트가 필요 없다(GitHub 로 나가는 연결만 씀).
- `shared/` 가 바뀌면 웹 BE 두 개(비밀·양봉)가 자동 배포된다(`shared/web_shared` 는 두 웹서버 공용). 배치·워커도 `shared/stock_shared` 를 쓰므로 필요하면 수동으로 돌린다.
- 양봉 BE 는 이미지를 `docker build` 로 직접 만든다. compose build 는 `.env.yangbong` 이 없는 서버에서 빌드 전에 실패하기 때문이다.
- `sql/` 마이그레이션은 자동 적용하지 않는다. 배포 전에 손으로 적용한다.

## 서버에서 손으로 배포할 때 (2026-11-19)

워크플로를 쓰지 않거나 **양봉을 처음 띄울 때**는 홈 서버 clone 에서 스크립트 하나로 한다.
git pull → 필수 파일 확인 → 이미지 빌드 → 컨테이너 기동/교체 → 헬스체크까지 한 번에 하고, 빌드가 성공한 뒤에만 교체한다.

```bash
./py-project/py-secret-api/deploy.sh                 # 비밀상회 API
./py-project/py-yangbong-api/deploy.sh               # 양봉상회 API + AI 워커 (--api-only / --worker-only)
```

- 확인하는 것: `.env`·`.env.yangbong` 의 필수 값(JWT 키 길이, 양봉·비밀 JWT 가 서로 다른지, DB_URL 자리표시), Anthropic 키 파일,
  KIS 키 JSON 항목·권한, Firebase 파일, docker 네트워크 `aibees`, 폴더 이름 변경 뒤 옛 폴더에만 남은 시크릿.
- 헬스체크: 컨테이너 Up, API 응답, DB 조회(양봉은 sql 003 시장 뷰 누락을 따로 알려 줌), AI 워커 시작 로그.
- `--no-pull` 로 pull 없이 실행. 공통 함수는 `py-project/scripts/deploy_lib.sh`.

## 폴더 이름 변경 (2026-11-19 py-naver-stock-theme → py-secret-api)

`git pull` 은 git 이 추적하는 파일만 새 폴더로 옮긴다. gitignore 된 시크릿은 **옛 폴더에 남는다.**
그래서 이 변경을 push 하기 **전에** 홈 서버 clone 폴더(`$HOME_DEPLOY_ROOT/py-project`)에서 시크릿을 새 폴더로 먼저 복사해 둔다.

```bash
cd "$HOME_DEPLOY_ROOT/py-project"
mkdir -p py-secret-api/app/config/keys
cp -a py-naver-stock-theme/.env py-naver-stock-theme/.env.mcp py-secret-api/
cp -a py-naver-stock-theme/app/config/keys/anthropic.env py-secret-api/app/config/keys/
```

- 새 폴더에 무시 파일만 있어도 `git pull` 은 정상으로 된다(추적 파일과 겹치지 않는다).
- 먼저 복사하지 않고 push 하면 웹 BE 배포가 `.env` 를 못 찾아 **교체 단계에서 실패**한다. 기존 컨테이너는 그대로 돈다. 위 복사 후 워크플로를 다시 실행하면 된다.
- compose 프로젝트 이름은 `name: py-naver-stock-theme` 로 고정해 두었다. 폴더 이름이 바뀌어도 떠 있는 `stock-web-flask-app`·`stock-web-mcp-server` 를 같은 프로젝트로 보고 교체한다.
- 배포가 정상인 것을 확인한 뒤 옛 폴더(`py-naver-stock-theme/`, 이제 무시 파일만 남음)를 지운다.
- 양봉 compose 는 Anthropic 키를 `../py-secret-api/app/config/keys/anthropic.env` 에서 마운트한다.

## 처음 한 번 설정

### 1. 서버마다 runner 설치

GitHub → 저장소 Settings → Actions → Runners → **New self-hosted runner** (Linux) 의 안내대로 받고, `config.sh` 에서 라벨을 붙인다.

```bash
# 클라우드 서버
./config.sh --url https://github.com/aibees/aibees-stock-system --token <발급 토큰> --name cloud --labels cloud

# 홈 서버 (워커도 같은 서버면 worker 라벨도 같이)
./config.sh --url https://github.com/aibees/aibees-stock-system --token <발급 토큰> --name home --labels home,worker

# 서비스로 등록(재부팅 후에도 실행)
sudo ./svc.sh install <clone 폴더 주인 계정>
sudo ./svc.sh start
```

runner 계정 조건:
- **clone 폴더 주인과 같은 계정**이어야 한다(`git pull` 권한·자격 증명을 그대로 씀).
- `docker` 그룹에 속해야 한다: `sudo usermod -aG docker <계정>` 후 runner 재시작.

### 2. 저장소 변수(Variables) 등록

Settings → Secrets and variables → Actions → **Variables** 탭:

| 이름 | 값(예) |
|---|---|
| `CLOUD_DEPLOY_ROOT` | 클라우드 서버의 clone 경로 (예: `/home/aibees/aibees-stock-system`) |
| `HOME_DEPLOY_ROOT` | 홈 서버의 clone 경로 |
| `WORKER_DEPLOY_ROOT` | (선택) 워커가 홈과 다른 서버·경로일 때만. 없으면 `HOME_DEPLOY_ROOT` 사용 |

### 3. 확인

Actions 탭 → 각 워크플로 → **Run workflow** 로 한 번씩 수동 실행해 본다.
FE·웹 BE 부터 해 보고, 배치는 배치가 안 도는 시간에, 워커는 장 마감 뒤에.

## 주의

- 서버 clone 에 손으로 고친 파일이 있으면 `git pull --ff-only` 가 실패한다. 서버에서 직접 고치지 말 것.
- 워커 배포는 `deploy_worker.sh` 를 그대로 돌린다 — 4개를 한꺼번에 재시작한다.
  결과 요약에 각 워커의 `[부팅]` 로그가 찍히니 매수가능 금액·예수금을 확인한다.
- 공휴일은 장 시간 차단이 평일로 취급한다. 공휴일 낮에 워커를 배포하려면 force 를 켠다.
- 워크플로 문법 검사: `actionlint` (라벨 설정은 `.github/actionlint.yaml`).
