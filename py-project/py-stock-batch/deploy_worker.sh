#!/usr/bin/env bash
# py-stock-worker 배포 스크립트
#   git pull → worker 이미지 빌드(Dockerfile.worker) → 컨테이너 재기동(docker-compose.pykis.yml)
#
# 사용:
#   ./deploy_worker.sh            # 현재 브랜치 pull 후 배포
#   ./deploy_worker.sh main       # 지정 브랜치로 배포
#
# 전제: aibees 네트워크 존재, aes.key/smtp.key present, DB_URL 은 compose 에 하드코딩됨.

set -euo pipefail

# py-project/ 로 이동한다.
# 여기가 docker 빌드 컨텍스트이며, shared(공용 ORM/DAO)가 포함되어야
# poetry 의 path dependency('../shared')가 해석된다.
# (git 명령은 레포 어디서든 동작하므로 pull 에는 영향 없다)
cd "$(dirname "$0")/.."

PROJ="py-stock-batch"
IMAGE="py-stock-worker"
DOCKERFILE="$PROJ/Dockerfile.worker"
COMPOSE="$PROJ/docker-compose.pykis.yml"
BRANCH="${1:-}"

log() { echo -e "\n\033[1;32m▶ $*\033[0m"; }

# docker compose v2/v1 호환
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
else
  DC="docker-compose"
fi

log "1/4 git pull"
git fetch --all --prune
if [ -n "$BRANCH" ]; then
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
else
  git pull
fi
echo "  현재 커밋: $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"

log "2/4 worker 이미지 빌드 ($IMAGE)"
docker build -f "$DOCKERFILE" -t "$IMAGE" .

log "3/4 컨테이너 재기동"
$DC -f "$COMPOSE" up -d --force-recreate
# 떠 있지 않은(주석 처리된) 서비스는 무시됨

log "4/4 상태"
$DC -f "$COMPOSE" ps

# 사용하지 않는 dangling 이미지 정리(선택)
docker image prune -f >/dev/null 2>&1 || true

echo -e "\n\033[1;34m배포 완료. 로그 확인: docker logs -f kis-user1\033[0m"
echo -e "\033[1;34m부팅 로그에 '[부팅] 실제 예수금=... · DB user_wallet=...' 이 뜨면 정상\033[0m"
