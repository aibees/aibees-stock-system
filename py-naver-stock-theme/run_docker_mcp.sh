#!/usr/bin/env bash
# MCP 서버 Docker 빌드 & 재시작 스크립트
# 사용: bash run_docker_mcp.sh

set -e

IMAGE="py-stock-mcp"
CONTAINER="stock-web-mcp-server"

echo "▶ MCP Docker stopping..."
docker stop $CONTAINER 2>/dev/null && echo "  stopped $CONTAINER" || echo "  (not running)"

echo "▶ MCP Docker removing container..."
docker rm $CONTAINER 2>/dev/null && echo "  removed $CONTAINER" || echo "  (not found)"

echo "▶ MCP Docker image removing..."
docker rmi $IMAGE 2>/dev/null && echo "  removed $IMAGE" || echo "  (not found)"

echo "▶ Building new $IMAGE from Dockerfile.mcp ..."
docker build -f Dockerfile.mcp -t $IMAGE .

echo "▶ Starting MCP server via docker-compose.mcp.yml ..."
docker-compose -f docker-compose.mcp.yml up -d

echo ""
echo "✅ MCP server started"
echo "   Container : $CONTAINER"
echo "   Internal  : http://172.21.1.5:5558/mcp"
echo "   External  : https://stock.aibeesworld.com/mcp"
echo ""
echo "   Log 확인  : docker logs -f $CONTAINER"
