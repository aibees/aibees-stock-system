"""
MCP OAuth 2.1 Python 통합 테스트
=================================
실제 MCP 클라이언트처럼 OAuth 흐름 전체를 시뮬레이션합니다.

실행:
    python test_mcp_oauth.py
    MCP_CLIENT_ID=my-id MCP_CLIENT_SECRET=my-secret python test_mcp_oauth.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import pprint

BASE        = os.getenv("MCP_BASE_URL", "https://stock.aibeesworld.com")
CLIENT_ID   = os.getenv("MCP_CLIENT_ID", "jun-stock-mcp")
CLIENT_SEC  = os.getenv("MCP_CLIENT_SECRET", "343886d0277d41f79dc2dc2ede82b7cdf9d88f4ef8e7ca1d1e2c4ae9f3800fa5")

PASS = "✅"
FAIL = "❌"

MCP_VERSION = "2025-03-26"   # MCP-Protocol-Version 헤더 (없으면 서버가 421 반환)


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────
def _parse_response_body(resp_bytes: bytes, content_type: str) -> dict:
    """
    MCP 서버 응답 파싱.
    - application/json        → 직접 파싱
    - text/event-stream (SSE) → data: 라인에서 JSON 추출
    """
    text = resp_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    if "text/event-stream" in content_type:
        # SSE 형식: "data: {...}\n\n" 에서 마지막 data 라인의 JSON 반환
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        return json.loads(payload)
                    except json.JSONDecodeError:
                        pass
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text}


def http(method: str, path: str, body=None, headers=None) -> tuple[int, dict]:
    url = BASE + path
    merged_headers = {**(headers or {})}
    content_type = merged_headers.get("Content-Type", "")

    if body is None:
        data = None
    elif content_type == "application/json" or not isinstance(body, dict):
        data = json.dumps(body).encode()
        if not content_type:
            merged_headers["Content-Type"] = "application/json"
    else:
        # dict + Content-Type 미지정 → form-urlencoded
        data = urllib.parse.urlencode(body).encode()
        merged_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    req = urllib.request.Request(url, data=data, headers=merged_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_bytes = resp.read()
            resp_ct = resp.headers.get("Content-Type", "")
            return resp.status, _parse_response_body(resp_bytes, resp_ct)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}



def section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print('─'*50)


def check(label: str, condition: bool, detail: str = ""):
    icon = PASS if condition else FAIL
    print(f"  {icon}  {label}", f"({detail})" if detail else "")
    if not condition:
        sys.exit(1)


# ──────────────────────────────────────────────
# 테스트
# ──────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  MCP OAuth 2.1 통합 테스트")
print(f"  서버: {BASE}")
print(f"  클라이언트: {CLIENT_ID}")
print('='*50)


# 1. Discovery
section("STEP 1. OAuth 메타데이터 discovery")
status, meta = http("GET", "/mcp/.well-known/oauth-authorization-server")
check("HTTP 200", status == 200, f"got {status}")
pprint.pprint(meta)
check("token_endpoint 존재", "token_endpoint" in meta, meta.get("token_endpoint"))
check("client_credentials 지원", "client_credentials" in meta.get("grant_types_supported", []))
print(f"  token_endpoint: {meta['token_endpoint']}")


# 2. 미인증 접근 → 401
section("STEP 2. 토큰 없이 /mcp 접근 → 401")
status, _ = http("POST", "/mcp",
    body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
             "MCP-Protocol-Version": MCP_VERSION})
check("HTTP 401 반환", status == 401, f"got {status}")


# 3. 잘못된 secret → 401
section("STEP 3. 잘못된 client_secret → 401")
status, body = http("POST", "/mcp/oauth/token", body={
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": "wrong-secret",
})
check("HTTP 401 반환", status == 401, f"got {status}")
check("error=invalid_client", body.get("error") == "invalid_client", body.get("error"))


# 4. 토큰 발급
section("STEP 4. 정상 토큰 발급 (client_credentials)")
status, token_resp = http("POST", "/mcp/oauth/token", body={
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SEC,
})
check("HTTP 200", status == 200, f"got {status}")
check("access_token 존재", "access_token" in token_resp)
check("token_type=bearer", token_resp.get("token_type") == "bearer")
check("expires_in 존재", "expires_in" in token_resp)
token = token_resp["access_token"]
print(f"  token: {token[:40]}...")


# 5. tools/list
section("STEP 5. Bearer 토큰으로 tools/list 호출")
status, resp = http("POST", "/mcp",
    body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_VERSION,
        "Authorization": f"Bearer {token}",
    })
check("HTTP 200", status == 200, f"got {status}")
tools = resp.get("result", {}).get("tools", [])
check("tools 목록 존재", len(tools) > 0, f"{len(tools)}개")
print(f"  등록된 tool 목록:")
for t in tools:
    print(f"    - {t['name']}: {t.get('description', '')[:50]}")


# 6. tool 호출
section("STEP 6. get_buy_target_stocks tool 호출")
status, resp = http("POST", "/mcp",
    body={
        "jsonrpc": "2.0", "id": 2,
        "method": "tools/call",
        "params": {"name": "get_buy_target_stocks", "arguments": { 'ymd': '20260604' }},
    },
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_VERSION,
        "Authorization": f"Bearer {token}",
    })
check("HTTP 200", status == 200, f"got {status}")
check("result 존재", "result" in resp or "error" not in resp)
print(f"  응답: {json.dumps(resp.get('result', resp), ensure_ascii=False)[:200]}")


# 7. get_stock_ohlcv tool 호출
section("STEP 7. get_stock_ohlcv tool 호출")
from datetime import datetime, timedelta
_today     = datetime.today()
_end_date  = (_today - timedelta(days=1)).strftime("%Y-%m-%d")
_start_date = (_today - timedelta(days=30)).strftime("%Y-%m-%d")

status, resp = http("POST", "/mcp",
    body={
        "jsonrpc": "2.0", "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_stock_ohlcv",
            "arguments": {
                "stock_code": "005930",       # 삼성전자
                "start_date": _start_date,
                "end_date":   _end_date,
            },
        },
    },
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_VERSION,
        "Authorization": f"Bearer {token}",
    })
check("HTTP 200", status == 200, f"got {status}")
check("result 존재", "result" in resp, str(resp.get("error", "")))

# tool 결과는 content[0].text 안에 JSON 문자열로 들어있음
_content = resp.get("result", {}).get("content", [])
check("content 존재", len(_content) > 0, f"{len(_content)}개")
_ohlcv_raw = _content[0].get("text", "[]")
_ohlcv = json.loads(_ohlcv_raw)
check("OHLCV 데이터 존재", len(_ohlcv) > 0, f"{len(_ohlcv)}행")

_first = _ohlcv[0]
check("ymd 컬럼 존재", "ymd" in _first or "datetime" in _first, str(list(_first.keys())[:5]))
check("close 컬럼 존재", "close" in _first, str(list(_first.keys())[:5]))
check("volume 컬럼 존재", "volume" in _first)
print(f"  기간: {_start_date} ~ {_end_date}  /  {len(_ohlcv)}행")
print(f"  첫 번째 row: {json.dumps(_first, ensure_ascii=False)}")


# 8. 존재하지 않는 종목코드 → error 없이 빈 결과
section("STEP 8. 존재하지 않는 종목코드 → error 없이 처리")
status, resp = http("POST", "/mcp",
    body={
        "jsonrpc": "2.0", "id": 4,
        "method": "tools/call",
        "params": {
            "name": "get_stock_ohlcv",
            "arguments": {
                "stock_code": "000000",
                "start_date": _start_date,
                "end_date":   _end_date,
            },
        },
    },
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_VERSION,
        "Authorization": f"Bearer {token}",
    })
check("HTTP 200", status == 200, f"got {status}")
_content2 = resp.get("result", {}).get("content", [])
if _content2:
    _text2 = json.loads(_content2[0].get("text", "{}"))
    check("error 메시지 반환", "error" in _text2, str(_text2))
    print(f"  응답: {_text2}")
else:
    print(f"  응답: {resp}")


# 9. 만료/위조 토큰 → 401
section("STEP 9. 위조 토큰으로 접근 → 401")
status, _ = http("POST", "/mcp",
    body={"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
    headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": MCP_VERSION,
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature",
    })
check("HTTP 401 반환", status == 401, f"got {status}")


print(f"\n{'='*50}")
print(f"  {PASS}  모든 테스트 통과")
print('='*50 + "\n")
