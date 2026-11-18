#!/usr/bin/env bash
# MCP Inspector — 브라우저 GUI에서 tool 목록 확인 및 직접 호출
# 필요: node/npx
#
# 사용법:
#   bash test_mcp_inspector.sh
#
# Inspector가 뜨면:
#   1. Transport: Streamable HTTP 선택
#   2. URL: http://localhost:5558/mcp
#   3. Headers 탭 → Authorization: Bearer <아래에서 복사한 토큰>

BASE="http://localhost:5558"
CLIENT_ID="${MCP_CLIENT_ID:-test-client}"
CLIENT_SECRET="${MCP_CLIENT_SECRET:-test-secret}"

echo "토큰 발급 중..."
TOKEN=$(curl -s -X POST "$BASE/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token','ERROR'))")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Inspector 실행 후 아래 헤더를 추가하세요:"
echo ""
echo "  Authorization: Bearer $TOKEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

npx -y @modelcontextprotocol/inspector
