# 배포 (GitHub Actions + self-hosted runner)

서비스 5개를 각각 따로 배포한다. 워크플로 하나 = 서비스 하나.

| 워크플로 | 대상 | 서버(runner 라벨) | 언제 |
|---|---|---|---|
| `deploy-yangbong-fe.yml` | 양봉상회 웹 `yangbong-vue-app` | 클라우드 (`cloud`) | `yangbong-store-vue/` push 시 자동 + 수동 |
| `deploy-secret-fe.yml` | 비밀상회 웹 `secret-vue-app` | 클라우드 (`cloud`) | `secret-store-vue/` push 시 자동 + 수동 |
| `deploy-web-be.yml` | 웹 API `stock-web-flask-app` (+ 떠 있으면 `yangbong-web-flask-app`, `yangbong-ai-worker`) | 홈 (`home`) | `py-naver-stock-theme/`·`shared/` push 시 자동 + 수동 |
| `deploy-batch-be.yml` | 배치 `stock-batch-flask-app` | 홈 (`home`) | **수동만** (돌던 배치가 끊기므로) |
| `deploy-kis-workers.yml` | 워커 `kis-user1~4` | 워커 서버 (`worker`) | **수동만**, 평일 07:30~20:10 KST 차단(force 로 우회) |

## 동작 방식

- runner 가 저장소를 새로 받지 않는다. **서버에 이미 있는 clone 폴더**에서 `git pull` 후 빌드한다.
  그래서 gitignore 된 `.env`, `.env.prd`, `.env.yangbong`, `aes.key`, `firebase-service-account.json` 등은 지금처럼 서버에만 두면 된다. GitHub Secrets 는 쓰지 않는다.
- 레지스트리를 쓰지 않는다. 이미지는 지금처럼 각 서버에서 로컬 빌드한다.
- 새 이미지 빌드가 성공한 뒤에만 컨테이너를 바꾼다. 빌드가 깨지면 기존 컨테이너가 그대로 남는다.
- runner 는 서버로 들어오는 포트가 필요 없다(GitHub 로 나가는 연결만 씀).
- `shared/` 가 바뀌면 웹 BE 만 자동 배포된다. 배치·워커도 `shared` 를 쓰므로 필요하면 수동으로 돌린다.
- `sql/` 마이그레이션은 자동 적용하지 않는다. 배포 전에 손으로 적용한다.

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
