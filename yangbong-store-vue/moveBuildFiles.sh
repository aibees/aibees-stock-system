#!/usr/bin/env bash
# stock-vue 배포. 빌드 컨텍스트는 이 디렉토리(stock-vue/) 다.
# 어디서 실행하든 스크립트 위치로 이동한 뒤 동작한다.
set -euo pipefail  # 에러/미정의 변수/파이프 실패 시 즉시 중단

cd "$(dirname "$0")" || exit 1

BRANCH="${BRANCH:-main}"
CONTAINER="stock-vue-app"

trap 'echo ">>> [ERROR] 배포 실패 (line $LINENO). 기존 컨테이너는 유지됩니다." >&2' ERR

# docker compose(v2) 우선, 없으면 docker-compose(v1) 폴백
if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo ">>> [ERROR] docker compose / docker-compose 둘 다 없음" >&2
  exit 1
fi

echo ">>> GIT PULL (origin/$BRANCH)"
git pull origin "$BRANCH"

echo '>>> DOCKER BUILD & RECREATE'
# 옛 컨테이너를 살려둔 채 새 이미지를 빌드하고,
# 빌드 성공 시에만 컨테이너를 교체 → 다운타임 최소화 + 실패 시 자동 롤백
"${DC[@]}" up --build -d

echo '>>> PRUNE DANGLING IMAGES'
docker image prune -f

echo '>>> HEALTH CHECK'
# 컨테이너가 실제로 Up 인지 확인. 아니면 로그 남기고 실패로 종료.
for i in $(seq 1 10); do
  STATUS="$(docker ps --filter "name=^/${CONTAINER}$" --format '{{.Status}}')"
  case "$STATUS" in
    Up*) echo ">>> $CONTAINER $STATUS"; echo '>>> DONE'; exit 0 ;;
  esac
  sleep 2
done

echo ">>> [ERROR] $CONTAINER 기동 실패 (status='${STATUS:-none}')" >&2
docker logs --tail 50 "$CONTAINER" 2>&1 || true
exit 1
