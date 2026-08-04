#!/usr/bin/env bash
# py-stock-worker (트레이딩 worker) 독립 빌드·배포 스크립트.
# 메인 py-stock-batch 와 별개 이미지라 따로 배포할 수 있다.
#
# 빌드 컨텍스트는 py-project/ 다. shared(공용 ORM/DAO) 가 컨텍스트에 포함되어야
# poetry 의 path dependency('../shared')가 해석된다.
# 이 스크립트는 어디서 실행하든 py-project/ 로 이동한 뒤 동작한다.
#
# 사용: DB_URL="mysql+pymysql://user:pw@host:port/db" ./build_worker.sh
set -e

cd "$(dirname "$0")/.."

PROJ="py-stock-batch"
COMPOSE="$PROJ/docker-compose.pykis.yml"

echo '▶ 기존 worker 정리...'
docker compose -f "$COMPOSE" down || true

echo '▶ py-stock-worker 이미지 빌드...'
docker build -f "$PROJ/Dockerfile.worker" -t py-stock-worker .

echo '▶ worker 기동...'
DB_URL="${DB_URL:-}" docker compose -f "$COMPOSE" up -d

echo '▶ 상태:'
docker compose -f "$COMPOSE" ps
echo '▶ 로그 확인: docker logs -f kis-user1  (부팅 잔고 동기화 로그 확인)'
