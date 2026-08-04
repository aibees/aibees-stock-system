#!/usr/bin/env bash
# MCP OAuth 2.1 로컬 테스트 스크립트
# 사용: bash test_mcp_oauth.sh
# 서버가 먼저 실행 중이어야 합니다:
#   MCP_CLIENT_ID=test-client MCP_CLIENT_SECRET=test-secret poetry run python -m app.mcp_server

BASE="http://localhost:5558"
CLIENT_ID="test-client"
CLIENT_SECRET="test-secret"

echo "================================================"
echo "  MCP OAuth 2.1 로컬 테스트"
echo "  서버: $BASE"
echo "================================================"
echo ""

# ── STEP 1: OAuth 메타데이터 확인 ──────────────────
echo "▶ STEP 1. OAuth 메타데이터 discovery"
echo "  GET $BASE/.well-known/oauth-authorization-server"
echo ""
curl -s "$BASE/.well-known/oauth-authorization-server" | python3 -m json.tool
echo ""

# ── STEP 2: 인증 없이 /mcp 접근 → 401 확인 ─────────
echo "▶ STEP 2. 인증 없이 /mcp 접근 (401 기대)"
echo ""
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
echo "  HTTP Status: $HTTP_STATUS  (401이면 정상)"
echo ""

# ── STEP 3: 토큰 발급 ───────────────────────────────
echo "▶ STEP 3. client_credentials 토큰 발급"
echo "  POST $BASE/oauth/token"
echo ""
TOKEN_RESPONSE=$(curl -s -X POST "$BASE/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET")

echo "$TOKEN_RESPONSE" | python3 -m json.tool
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ 토큰 발급 실패. 서버가 실행 중인지, CLIENT_ID/SECRET이 맞는지 확인하세요."
  exit 1
fi
echo ""
echo "  ✅ 토큰 발급 성공: ${ACCESS_TOKEN:0:40}..."
echo ""

# ── STEP 4: 토큰으로 MCP tools/list 호출 ───────────
echo "▶ STEP 4. Bearer 토큰으로 MCP tools/list 호출"
echo ""
curl -s -X POST "$BASE/mcp" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 -m json.tool
echo ""

# ── STEP 5: tool 실제 호출 ──────────────────────────
echo "▶ STEP 5. get_buy_target_stocks tool 호출"
echo ""
curl -s -X POST "$BASE/mcp" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_buy_target_stocks",
      "arguments": {}
    }
  }' | python3 -m json.tool
echo ""

# ── STEP 6: 잘못된 토큰으로 접근 → 401 확인 ────────
echo "▶ STEP 6. 잘못된 토큰으로 접근 (401 기대)"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/mcp" \
  -H "Authorization: Bearer invalid.token.here" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list"}')
echo "  HTTP Status: $HTTP_STATUS  (401이면 정상)"
echo ""

echo "================================================"
echo "  테스트 완료"
echo "================================================"
