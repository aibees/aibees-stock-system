#!/usr/bin/env bash
# py-stock-web 이미지 빌드 & 기동.
#
# 빌드 컨텍스트는 py-project/ 다. shared(공용 ORM/DAO) 가 컨텍스트에 포함되어야
# poetry 의 path dependency('../shared')가 해석된다.
# 이 스크립트는 어디서 실행하든 py-project/ 로 이동한 뒤 동작한다.
#
# ── 구 스크립트가 배포를 망가뜨린 경위 ──────────────────────────────
#  1) 컨테이너 stop/rm 후 `docker rmi py-stock-web` 으로 **이미지까지 삭제**
#  2) 이어서 docker build 실행 → 실패
#  3) set -e 가 없어 그대로 `docker compose up -d` 까지 진행
#  4) 로컬에 이미지가 없으니 compose 가 레지스트리에서 pull 시도
#     → pull access denied for py-stock-web, repository does not exist
#  결국 되돌아갈 이미지도 없이 서비스가 내려간 채 끝난다.
#
#  → 새 이미지를 **먼저 빌드**하고 성공했을 때만 교체한다.
#    빌드가 실패하면 돌던 컨테이너는 손대지 않는다.
#    (compose 에도 build: 를 넣어 이미지가 없으면 pull 대신 빌드하도록 했다)
# ────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

PROJ="py-naver-stock-theme"
IMAGE="py-stock-web"
CONTAINER="stock-web-flask-app"
COMPOSE="$PROJ/docker-compose.yml"

echo "▶ [1/4] 이미지 빌드: $IMAGE:new"
# 실패하면 set -e 가 여기서 멈춘다 → 돌던 서비스는 그대로 유지된다.
docker build -f "$PROJ/Dockerfile" -t "$IMAGE:new" .

echo "▶ [2/4] 이미지 태깅"
if docker image inspect "$IMAGE:latest" >/dev/null 2>&1; then
    docker tag "$IMAGE:latest" "$IMAGE:rollback"
    echo "  이전 이미지 → $IMAGE:rollback 으로 보존"
fi
docker tag "$IMAGE:new" "$IMAGE:latest"
docker rmi "$IMAGE:new" >/dev/null 2>&1 || true

# compose 가 pull 로 새지 않도록, 교체 직전에 태그 존재를 한 번 더 확인한다.
if ! docker image inspect "$IMAGE:latest" >/dev/null 2>&1; then
    echo "  ❌ $IMAGE:latest 태그가 없다. 중단 (compose 가 pull 을 시도하게 두지 않는다)"
    exit 1
fi

echo "▶ [3/4] 컨테이너 교체"
# 수동 stop/rm 은 compose 상태와 어긋날 수 있어 쓰지 않는다.
docker compose -f "$COMPOSE" up -d --force-recreate

echo "▶ [4/4] 기동 확인"
sleep 5
if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
    echo "  ✅ $CONTAINER 기동됨"
    docker compose -f "$COMPOSE" logs --tail=30 app
else
    echo "  ❌ $CONTAINER 가 떠 있지 않다. 로그:"
    docker logs --tail=80 "$CONTAINER" 2>&1 || true
    echo
    echo "  롤백:"
    echo "    docker tag $IMAGE:rollback $IMAGE:latest"
    echo "    docker compose -f $COMPOSE up -d --force-recreate"
    exit 1
fi

# dangling 이미지 정리 (rollback 태그는 유지된다)
docker image prune -f >/dev/null 2>&1 || true
echo "완료."
