#!/usr/bin/env bash
# =============================================================================
# 비밀상회 API 배포 (홈 서버) — git pull → 필수 파일 확인 → 이미지 빌드 → 컨테이너 교체 → 헬스체크
#
#   ./py-project/py-secret-api/deploy.sh            전부
#   ./py-project/py-secret-api/deploy.sh --no-pull  git pull 생략(지금 받은 코드로)
#
#   이미지 py-stock-web · 컨테이너 stock-web-flask-app(docker-compose.yml, 프로젝트 이름 py-naver-stock-theme 고정)
#   MCP 서버(stock-web-mcp-server)는 따로 — run_docker_mcp.sh
#
# 옛 build_docker.sh 와 달리 컨테이너를 먼저 지우지 않는다. 빌드가 성공한 뒤에만 교체하므로
# 빌드가 깨지면 기존 서버가 그대로 남는다(GitHub 워크플로 deploy-web-be.yml 과 같은 방식).
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"      # py-project/py-secret-api
PY_PROJECT="$(dirname "$HERE")"             # py-project (도커 빌드 컨텍스트)
REPO="$(dirname "$PY_PROJECT")"             # 저장소 루트
# shellcheck source=../scripts/deploy_lib.sh
source "$PY_PROJECT/scripts/deploy_lib.sh"

DO_PULL=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pull) DO_PULL=0; shift ;;
    -h|--help) sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "알 수 없는 옵션: $1 (--help 참고)" ;;
  esac
done

IMAGE="py-stock-web"
CONTAINER="stock-web-flask-app"
COMPOSE="$HERE/docker-compose.yml"
PORT=5556

# ── 1) git pull ──
if [[ $DO_PULL -eq 1 ]]; then git_pull "$REPO"; else step "git pull 생략(--no-pull)"; fi

# ── 2) 필수 파일·환경 확인 ──
step "필수 파일 확인"
need_cmd docker; need_cmd git; need_cmd curl
docker compose version >/dev/null 2>&1 || die "docker compose(v2) 가 없습니다."

OLD="$PY_PROJECT/py-naver-stock-theme"   # 2026-11-19 폴더 이름 변경 전 위치 — git 이 무시 파일은 옮기지 않는다
for f in .env .env.mcp app/config/keys/anthropic.env; do
  if [[ ! -e "$HERE/$f" && -f "$OLD/$f" ]]; then
    fail "$f 가 옛 폴더에만 있습니다 → cp -a '$OLD/$f' '$HERE/$f'"
  fi
done

need_file "$HERE/.env" ".env (JWT 서명 키 등)"
JWT="$(env_value "$HERE/.env" JWT_SECRET_KEY)"
if [[ -z "$JWT" ]]; then fail "JWT_SECRET_KEY 가 비어 있습니다(.env) — 없으면 로그인·인증 API 가 모두 거절됩니다"
elif [[ ${#JWT} -lt 32 ]]; then fail "JWT_SECRET_KEY 가 32자보다 짧습니다"
else ok "JWT_SECRET_KEY (${#JWT}자)"; fi

BATCH_JWT="$(env_value "$PY_PROJECT/py-stock-batch/.env" JWT_SECRET_KEY)"
if [[ -n "$BATCH_JWT" && -n "$JWT" && "$BATCH_JWT" != "$JWT" ]]; then
  warn "배치 서버(py-stock-batch/.env)의 JWT_SECRET_KEY 와 다릅니다 — 관리 화면의 배치 실행이 인증 실패로 막힙니다"
fi

if [[ -n "$(env_value "$HERE/.env" SECRET_KEY)" ]]; then ok "Anthropic 키 (.env 의 SECRET_KEY)"
else need_file "$HERE/app/config/keys/anthropic.env" "Anthropic 키 (app/config/keys/anthropic.env — 이미지에 복사됨)"; fi

need_network aibees
checks_done

# ── 3) 이미지 빌드 ──
step "이미지 빌드 ($IMAGE)"
cd "$PY_PROJECT"
docker build -f py-secret-api/Dockerfile -t "$IMAGE" .
ok "빌드 완료"

# ── 4) 컨테이너 교체 ──
step "컨테이너 교체 ($CONTAINER)"
docker compose -f "$COMPOSE" up -d --no-build app

# ── 5) 헬스체크 ──
step "헬스체크"
FAILS=0
wait_up "$CONTAINER"
code="$(wait_http "http://127.0.0.1:$PORT/api/v1/stocks" "API")" || true
[[ "$code" == "200" ]] && ok "API 응답 (:$PORT /api/v1/stocks → $code)" || fail "API 가 응답하지 않습니다(:$PORT → $code)"
body="$(curl -s --max-time 10 "http://127.0.0.1:$PORT/api/v1/stocks/buy-target/performance" || true)"
if [[ "$body" == *'"success": true'* || "$body" == *'"success":true'* ]]; then ok "DB 조회 (매수추천 성과)"
else warn "DB 조회 응답이 이상합니다: ${body:0:160}"; fi

docker image prune -f >/dev/null 2>&1 || true
echo
if [[ $FAILS -gt 0 ]]; then die "배포는 됐지만 헬스체크에 실패했습니다. docker logs $CONTAINER 를 확인하세요."; fi
echo "$(_c 32)배포 완료$(_c 0) — $(git -C "$REPO" log -1 --format='%h %s')"
