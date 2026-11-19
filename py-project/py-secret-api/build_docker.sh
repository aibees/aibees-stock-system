#!/usr/bin/env bash
# py-stock-web 이미지 빌드 & 기동.
#
# ⚠ 2026-11-19 부터는 deploy.sh 를 쓴다(git pull·필수 파일 확인·헬스체크 포함, 빌드 성공 뒤에만 교체).
#   이 스크립트는 컨테이너를 먼저 지우고 빌드하므로, 빌드가 실패하면 API 가 내려간 채로 남는다.
#
# 빌드 컨텍스트는 py-project/ 다. shared(공용 ORM/DAO) 가 컨텍스트에 포함되어야
# poetry 의 path dependency('../shared')가 해석된다.
# 이 스크립트는 어디서 실행하든 py-project/ 로 이동한 뒤 동작한다.

cd "$(dirname "$0")/.." || exit 1

PROJ="py-secret-api"

echo 'Docker stopping....'
docker stop stock-web-flask-app

echo 'Docker removing....'
docker rm stock-web-flask-app

echo 'Docker image removing....'
docker rmi py-stock-web

echo 'Docker build new py-stock-web'
docker build -f "$PROJ/Dockerfile" -t py-stock-web .

docker compose -f "$PROJ/docker-compose.yml" up -d
