#!/usr/bin/env bash
# =============================================================================
# 양봉상회 API + AI 워커 배포 (홈 서버) — git pull → 필수 파일 확인 → 이미지 빌드 → 컨테이너 기동/교체 → 헬스체크
#
#   ./py-project/py-yangbong-api/deploy.sh               API + AI 워커
#   ./py-project/py-yangbong-api/deploy.sh --api-only    API 만
#   ./py-project/py-yangbong-api/deploy.sh --worker-only AI 워커만
#   ./py-project/py-yangbong-api/deploy.sh --no-pull     git pull 생략
#
#   이미지 py-yangbong-web 하나로 두 컨테이너: yangbong-web-flask-app(:5558) · yangbong-ai-worker
#   처음 띄울 때도 이 스크립트를 쓴다(GitHub 워크플로는 이미 떠 있는 컨테이너만 교체한다).
#   빌드가 성공한 뒤에만 교체하므로 빌드가 깨지면 기존 컨테이너가 그대로 남는다.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"      # py-project/py-yangbong-api
PY_PROJECT="$(dirname "$HERE")"             # py-project (도커 빌드 컨텍스트)
REPO="$(dirname "$PY_PROJECT")"             # 저장소 루트
# shellcheck source=../scripts/deploy_lib.sh
source "$PY_PROJECT/scripts/deploy_lib.sh"

DO_PULL=1
SERVICES=(app ai-worker)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-pull)     DO_PULL=0; shift ;;
    --api-only)    SERVICES=(app); shift ;;
    --worker-only) SERVICES=(ai-worker); shift ;;
    -h|--help) sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "알 수 없는 옵션: $1 (--help 참고)" ;;
  esac
done
has() { [[ " ${SERVICES[*]} " == *" $1 "* ]]; }

IMAGE="py-yangbong-web"
COMPOSE="$HERE/docker-compose.yml"
PORT=5558

# ── 1) git pull ──
if [[ $DO_PULL -eq 1 ]]; then git_pull "$REPO"; else step "git pull 생략(--no-pull)"; fi

# ── 2) 필수 파일·환경 확인 ──
step "필수 파일 확인 (${SERVICES[*]})"
need_cmd docker; need_cmd git; need_cmd curl
docker compose version >/dev/null 2>&1 || die "docker compose(v2) 가 없습니다."

ENVF="$HERE/.env.yangbong"
need_file "$ENVF" ".env.yangbong (DB 계정·JWT 키 — .env.yangbong.example 참고)"

DB_URL="$(env_value "$ENVF" DB_URL)"
if [[ -z "$DB_URL" ]]; then fail "DB_URL 이 비어 있습니다"
elif [[ "$DB_URL" == *"<"* ]]; then fail "DB_URL 에 자리표시(<…>)가 남아 있습니다"
elif [[ "$DB_URL" != */yangbong* ]]; then warn "DB_URL 이 yangbong 스키마를 가리키지 않는 것 같습니다: ${DB_URL%%@*}@…"
else ok "DB_URL (${DB_URL#*@})"; fi

JWT="$(env_value "$ENVF" JWT_SECRET_KEY)"
SECRET_JWT="$(env_value "$PY_PROJECT/py-secret-api/.env" JWT_SECRET_KEY)"
if [[ -z "$JWT" ]]; then fail "JWT_SECRET_KEY 가 비어 있습니다 — 만들기: python3 -c \"import secrets; print(secrets.token_hex(32))\""
elif [[ ${#JWT} -lt 32 ]]; then fail "JWT_SECRET_KEY 가 32자보다 짧습니다"
elif [[ -n "$SECRET_JWT" && "$JWT" == "$SECRET_JWT" ]]; then fail "JWT_SECRET_KEY 가 비밀상회(py-secret-api/.env)와 같습니다 — 반드시 다른 값이어야 합니다"
else ok "JWT_SECRET_KEY (${#JWT}자, 비밀상회와 다름)"; fi

# compose 가 마운트하는 파일(없으면 docker 가 빈 폴더를 만들어 버린다)
need_file "$PY_PROJECT/py-secret-api/app/config/keys/anthropic.env" "Anthropic 키 (py-secret-api/app/config/keys/anthropic.env 마운트)"

if has ai-worker; then
  KIS="$HERE/secrets/kis-yangbong.json"
  need_file "$KIS" "AI 워커 KIS 키 (secrets/kis-yangbong.json)"
  if [[ -f "$KIS" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      if miss="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); m=[k for k in ("id","account","app_key","sec_key") if not str(d.get(k) or "").strip()]; print(",".join(m)); sys.exit(1 if m else 0)' "$KIS" 2>&1)"; then
        ok "KIS 키 JSON 형식·항목 4개"
      else fail "kis-yangbong.json 이 올바르지 않습니다(빠진 항목/형식 오류: $miss)"; fi
    else
      grep -q '"sec_key"' "$KIS" && ok "KIS 키 파일(형식 검사는 python3 가 없어 생략)" || fail "kis-yangbong.json 에 sec_key 가 없습니다"
    fi
    perm="$(stat -c '%a' "$KIS" 2>/dev/null || stat -f '%Lp' "$KIS")"
    [[ "$perm" == "600" || "$perm" == "400" ]] || warn "kis-yangbong.json 권한이 $perm 입니다 — chmod 600 권장"
  fi
  need_file "$PY_PROJECT/py-stock-batch/firebase-service-account.json" "푸시용 Firebase 서비스 계정 (py-stock-batch/firebase-service-account.json 마운트)"
fi

need_network aibees
checks_done

# ── 3) 이미지 빌드 ──
# compose build 를 쓰지 않는다 — 빌드에는 .env 가 필요 없는데 compose 는 env_file 이 없으면 빌드 전에 멈춘다.
step "이미지 빌드 ($IMAGE)"
cd "$PY_PROJECT"
docker build -f py-yangbong-api/Dockerfile -t "$IMAGE" .
ok "빌드 완료"

# ── 4) 컨테이너 기동/교체 ──
# AI 워커는 교체 때 돌던 AI 호출이 끝나길 최대 160초 기다린다(stop_grace_period) — 여기서 잠시 멈춘 것처럼 보일 수 있다.
step "컨테이너 기동/교체 (${SERVICES[*]})"
ADOPT=()
for svc in "${SERVICES[@]}"; do
  case "$svc" in app) ADOPT+=(yangbong-web-flask-app) ;; ai-worker) ADOPT+=(yangbong-ai-worker) ;; esac
done
adopt_container "$COMPOSE" "${ADOPT[@]}"
docker compose -f "$COMPOSE" up -d --no-build "${SERVICES[@]}"

# ── 5) 헬스체크 ──
step "헬스체크"
FAILS=0
if has app; then
  wait_up yangbong-web-flask-app
  code="$(wait_http "http://127.0.0.1:$PORT/api/v1/stocks" "API")" || true
  [[ "$code" == "200" ]] && ok "API 응답 (:$PORT /api/v1/stocks → $code)" || fail "API 가 응답하지 않습니다(:$PORT → $code)"
  body="$(curl -s --max-time 10 "http://127.0.0.1:$PORT/api/v1/stocks/buy-target/performance" || true)"
  if [[ "$body" == *'"success": true'* || "$body" == *'"success":true'* ]]; then ok "DB 조회 (시장 데이터 뷰)"
  elif [[ "$body" == *"doesn't exist"* ]]; then fail "양봉 스키마에 시장 데이터 뷰가 없습니다 — sql/yangbong/003_market_views.sql 를 관리자 계정으로 적용하세요"
  else warn "DB 조회 응답이 이상합니다: ${body:0:160}"; fi
fi
if has ai-worker; then
  wait_up yangbong-ai-worker
  started=""
  for _ in $(seq 1 20); do
    docker logs --since 2m yangbong-ai-worker 2>&1 | grep -q "AI 워커 시작" && { started=1; break; }
    sleep 1
  done
  [[ -n "$started" ]] && ok "AI 워커 시작 로그 확인" || { fail "AI 워커 시작 로그가 없습니다"; docker logs --tail 40 yangbong-ai-worker 2>&1 | sed 's/^/    /'; }
fi

docker image prune -f >/dev/null 2>&1 || true
echo
if [[ $FAILS -gt 0 ]]; then die "기동은 했지만 헬스체크에 실패했습니다. 위 메시지와 docker logs 를 확인하세요."; fi
echo "$(_c 32)배포 완료$(_c 0) — $(git -C "$REPO" log -1 --format='%h %s')"
