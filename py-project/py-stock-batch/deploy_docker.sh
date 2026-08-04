#!/usr/bin/env bash
# py-stock-batch 메인 이미지 빌드 & 기동.
#
# 빌드 컨텍스트는 py-project/ 다. shared(공용 ORM/DAO) 가 컨텍스트에 포함되어야
# poetry 의 path dependency('../shared')가 해석된다.
# 이 스크립트는 어디서 실행하든 py-project/ 로 이동한 뒤 동작한다.

cd "$(dirname "$0")/.." || exit 1

PROJ="py-stock-batch"

echo 'Docker stopping....'
docker stop stock-batch-flask-app

echo 'Docker removing....'
docker rm stock-batch-flask-app

echo 'Docker image removing....'
docker rmi py-stock-batch

echo 'Docker build new py-stock-batch'
docker build -f "$PROJ/Dockerfile" -t py-stock-batch .

docker compose -f "$PROJ/docker-compose.yml" up -d
