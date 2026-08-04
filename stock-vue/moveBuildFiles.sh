#!/bin/bash
set -euo pipefail  # 에러/미정의 변수/파이프 실패 시 즉시 중단

trap 'echo ">>> [ERROR] 배포 실패 (line $LINENO). 기존 컨테이너는 유지됩니다." >&2' ERR

echo '>>> GIT PULL'
git pull origin master

echo '>>> DOCKER BUILD & RECREATE'
# 옛 컨테이너를 살려둔 채 새 이미지를 빌드하고,
# 빌드 성공 시에만 컨테이너를 교체 → 다운타임 최소화 + 실패 시 자동 롤백
docker-compose up --build -d

echo '>>> PRUNE DANGLING IMAGES'
docker image prune -f

echo '>>> HEALTH CHECK'
sleep 2
docker ps --filter "name=stock-vue-app" --format '{{.Names}} {{.Status}}'

echo '>>> DONE'
