"""
MCP OAuth 2.1 Authorization Server
=====================================
MCP HTTP transport 스펙이 요구하는 OAuth 2.1 엔드포인트를 구현합니다.

지원 Grant:
    - authorization_code + PKCE  (mcp-remote 브라우저 플로우)
    - client_credentials          (M2M)

엔드포인트:
    GET  /.well-known/oauth-authorization-server   — 메타데이터 discovery
    GET/POST /mcp/oauth/authorize                  — Authorization Code 승인 페이지
    POST /mcp/oauth/register                       — Dynamic Client Registration (RFC 7591)
    POST /mcp/oauth/token                          — 토큰 발급
    POST /mcp/oauth/revoke                         — 토큰 폐기 (optional)

클라이언트 인증 방식:
    - mcp-remote: 브라우저 열림 → API Secret 입력 → JWT 발급 (최초 1회)
    - M2M: client_credentials grant (client_id / client_secret)
    - 직접: Authorization: Bearer <MCP_CLIENT_SECRET>

토큰 서명:
    PyJWT + HS256, 서명키 = MCP_JWT_SECRET 환경변수
"""
from __future__ import annotations

import hashlib
import base64
import os
import secrets
import time
import uuid
from typing import Optional
from urllib.parse import urlencode

import jwt
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
JWT_SECRET         = os.getenv("MCP_JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM      = "HS256"
TOKEN_TTL          = int(os.getenv("MCP_TOKEN_TTL", "3600"))        # 1시간
REFRESH_TOKEN_TTL  = int(os.getenv("MCP_REFRESH_TOKEN_TTL", "2592000"))  # 30일
BASE_URL           = os.getenv("MCP_BASE_URL", "http://localhost:8001")

# 사전 등록 클라이언트 (환경변수)
_PRESET_CLIENT_ID     = os.getenv("MCP_CLIENT_ID", "jun-stock-mcp")
_PRESET_CLIENT_SECRET = os.getenv("MCP_CLIENT_SECRET", "ngnbiegfidebvgikdhrtbtbklrdvfhjrkitlhrkicjrh")

# ──────────────────────────────────────────────
# 인메모리 저장소
# ──────────────────────────────────────────────
# { client_id: { client_secret, client_name, grant_types, scope } }
_CLIENT_REGISTRY: dict[str, dict] = {}

# { code: { client_id, redirect_uri, scope, code_challenge, expires_at } }
_AUTH_CODES: dict[str, dict] = {}

# { refresh_token: { client_id, scope, expires_at } }
_REFRESH_TOKENS: dict[str, dict] = {}

if _PRESET_CLIENT_ID and _PRESET_CLIENT_SECRET:
    _CLIENT_REGISTRY[_PRESET_CLIENT_ID] = {
        "client_secret": _PRESET_CLIENT_SECRET,
        "client_name": "preset-client",
        "grant_types": ["client_credentials", "authorization_code"],
        "scope": "mcp",
    }


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────
def _issue_token(client_id: str, scope: str = "mcp", include_refresh: bool = True) -> dict:
    now = int(time.time())
    payload = {
        "iss": BASE_URL,
        "sub": client_id,
        "iat": now,
        "exp": now + TOKEN_TTL,
        "jti": str(uuid.uuid4()),
        "scope": scope,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    result = {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": TOKEN_TTL,
        "scope": scope,
    }
    if include_refresh:
        refresh_token = secrets.token_urlsafe(48)
        _REFRESH_TOKENS[refresh_token] = {
            "client_id": client_id,
            "scope": scope,
            "expires_at": now + REFRESH_TOKEN_TTL,
        }
        result["refresh_token"] = refresh_token
    return result


def verify_token(token: str) -> Optional[dict]:
    """
    Bearer 토큰 검증. 유효하면 payload 반환, 실패하면 None.
    mcp_server.py의 미들웨어에서 호출합니다.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    """S256 PKCE 검증."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return expected == code_challenge


def _parse_basic_auth(request: Request) -> tuple[str, str]:
    import base64 as b64
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        decoded = b64.b64decode(auth[6:]).decode()
        parts = decoded.split(":", 1)
        return (parts[0], parts[1]) if len(parts) == 2 else ("", "")
    return "", ""


# ──────────────────────────────────────────────
# 엔드포인트 핸들러
# ──────────────────────────────────────────────
async def oauth_metadata(request: Request) -> JSONResponse:
    """
    GET /.well-known/oauth-authorization-server
    RFC 8414 Authorization Server Metadata
    mcp-remote는 authorization_endpoint / registration_endpoint 가 string이어야 합니다.
    """
    return JSONResponse({
        "issuer": BASE_URL,
        "authorization_endpoint": f"{BASE_URL}/mcp/oauth/authorize",
        "token_endpoint": f"{BASE_URL}/mcp/oauth/token",
        "registration_endpoint": f"{BASE_URL}/mcp/oauth/register",
        "revocation_endpoint": f"{BASE_URL}/mcp/oauth/revoke",
        "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
        "response_types_supported": ["code"],
        "token_endpoint_auth_methods_supported": [
            "none",
            "client_secret_post",
            "client_secret_basic",
        ],
        "scopes_supported": ["mcp"],
        "code_challenge_methods_supported": ["S256"],
    })


async def oauth_authorize(request: Request) -> Response:
    """
    GET/POST /mcp/oauth/authorize
    Authorization Code 발급 페이지.
    - GET: API Secret 입력 폼 표시
    - POST: 폼 검증 → authorization code 발급 → redirect_uri 로 리다이렉트
    """
    # GET 파라미터는 query string에서, POST는 form에서 꺼냄
    if request.method == "POST":
        form = await request.form()
        client_id            = form.get("client_id", "")
        redirect_uri         = form.get("redirect_uri", "")
        state                = form.get("state", "")
        code_challenge       = form.get("code_challenge", "")
        code_challenge_method = form.get("code_challenge_method", "S256")
        scope                = form.get("scope", "mcp")
        api_secret           = form.get("api_secret", "")

        if api_secret != _PRESET_CLIENT_SECRET:
            return _authorize_form(
                client_id, redirect_uri, state,
                code_challenge, code_challenge_method, scope,
                error="API Secret이 올바르지 않습니다.",
            )

        code = secrets.token_urlsafe(32)
        _AUTH_CODES[code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "expires_at": time.time() + 300,  # 5분 유효
        }

        params: dict = {"code": code}
        if state:
            params["state"] = state
        return RedirectResponse(f"{redirect_uri}?{urlencode(params)}", status_code=302)

    # GET — 폼 표시
    q = request.query_params
    return _authorize_form(
        client_id=q.get("client_id", ""),
        redirect_uri=q.get("redirect_uri", ""),
        state=q.get("state", ""),
        code_challenge=q.get("code_challenge", ""),
        code_challenge_method=q.get("code_challenge_method", "S256"),
        scope=q.get("scope", "mcp"),
    )


def _authorize_form(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str,
    error: str = "",
) -> HTMLResponse:
    error_html = f'<p style="color:red">{error}</p>' if error else ""
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>jun-stock-mcp 인증</title>
  <style>
    body {{ font-family: sans-serif; max-width: 400px; margin: 80px auto; padding: 0 20px; }}
    h2 {{ margin-bottom: 8px; }}
    p  {{ color: #555; font-size: 14px; }}
    input[type=password] {{
      width: 100%; padding: 10px; font-size: 16px;
      border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box;
    }}
    button {{
      margin-top: 12px; width: 100%; padding: 10px;
      background: #1a73e8; color: white; border: none;
      border-radius: 4px; font-size: 16px; cursor: pointer;
    }}
    button:hover {{ background: #1558b0; }}
  </style>
</head>
<body>
  <h2>jun-stock-mcp 접근 승인</h2>
  <p>MCP 서버에 접근하려면 API Secret을 입력하세요.</p>
  {error_html}
  <form method="post">
    <input type="hidden" name="client_id"             value="{client_id}">
    <input type="hidden" name="redirect_uri"           value="{redirect_uri}">
    <input type="hidden" name="state"                  value="{state}">
    <input type="hidden" name="code_challenge"         value="{code_challenge}">
    <input type="hidden" name="code_challenge_method"  value="{code_challenge_method}">
    <input type="hidden" name="scope"                  value="{scope}">
    <input type="password" name="api_secret" placeholder="API Secret" autofocus required>
    <button type="submit">승인</button>
  </form>
</body>
</html>"""
    return HTMLResponse(html)


async def oauth_register(request: Request) -> JSONResponse:
    """
    POST /mcp/oauth/register
    RFC 7591 Dynamic Client Registration — 항상 활성화.
    mcp-remote는 이 엔드포인트로 자신을 등록합니다.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    client_id = str(uuid.uuid4())
    # Authorization Code + PKCE public client → client_secret 불필요
    client_secret = secrets.token_urlsafe(32)

    _CLIENT_REGISTRY[client_id] = {
        "client_secret": client_secret,
        "client_name": body.get("client_name", "unnamed"),
        "grant_types": body.get("grant_types", ["authorization_code"]),
        "scope": body.get("scope", "mcp"),
        "redirect_uris": body.get("redirect_uris", []),
    }

    return JSONResponse({
        "client_id": client_id,
        "client_secret": client_secret,
        "client_name": _CLIENT_REGISTRY[client_id]["client_name"],
        "grant_types": _CLIENT_REGISTRY[client_id]["grant_types"],
        "redirect_uris": _CLIENT_REGISTRY[client_id]["redirect_uris"],
        "token_endpoint_auth_method": "none",
    }, status_code=201)


async def oauth_token(request: Request) -> JSONResponse:
    """
    POST /mcp/oauth/token
    authorization_code + PKCE, client_credentials 처리
    """
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    grant_type = form.get("grant_type", "")

    # ── Authorization Code + PKCE ──────────────────────────
    if grant_type == "authorization_code":
        code         = form.get("code", "")
        redirect_uri = form.get("redirect_uri", "")
        code_verifier = form.get("code_verifier", "")

        stored = _AUTH_CODES.pop(code, None)
        if not stored or stored["expires_at"] < time.time():
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        if stored["redirect_uri"] != redirect_uri:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "redirect_uri 불일치"},
                status_code=400,
            )

        # PKCE 검증
        if stored.get("code_challenge"):
            if not code_verifier:
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "code_verifier 필요"},
                    status_code=400,
                )
            if not _verify_pkce(code_verifier, stored["code_challenge"]):
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "PKCE 검증 실패"},
                    status_code=400,
                )

        return JSONResponse(_issue_token(stored["client_id"], stored["scope"]))

    # ── Refresh Token ──────────────────────────────────────
    if grant_type == "refresh_token":
        refresh_token = form.get("refresh_token", "")
        stored = _REFRESH_TOKENS.pop(refresh_token, None)
        if not stored or stored["expires_at"] < time.time():
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "refresh_token이 만료되었거나 유효하지 않습니다."},
                status_code=400,
            )
        # Refresh Token Rotation: 새 access_token + 새 refresh_token 발급
        return JSONResponse(_issue_token(stored["client_id"], stored["scope"]))

    # ── Client Credentials ─────────────────────────────────
    if grant_type == "client_credentials":
        client_id     = form.get("client_id", "")
        client_secret = form.get("client_secret", "")
        if not client_id:
            client_id, client_secret = _parse_basic_auth(request)

        if not client_id or not client_secret:
            return JSONResponse(
                {"error": "invalid_client", "error_description": "client_id / client_secret 필요"},
                status_code=401,
            )

        registered = _CLIENT_REGISTRY.get(client_id)
        if not registered or registered["client_secret"] != client_secret:
            return JSONResponse(
                {"error": "invalid_client", "error_description": "인증 실패"},
                status_code=401,
            )

        scope = form.get("scope", registered.get("scope", "mcp"))
        # client_credentials는 refresh_token 없이 발급 (M2M은 직접 재발급)
        return JSONResponse(_issue_token(client_id, scope, include_refresh=False))

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


async def oauth_revoke(request: Request) -> Response:
    """POST /mcp/oauth/revoke — RFC 7009 stub."""
    return Response(status_code=200)


# ──────────────────────────────────────────────
# Starlette Route 목록 (mcp_server.py에서 import)
# ──────────────────────────────────────────────
oauth_routes = [
    # RFC 8414 표준 경로 (mcp-remote가 여기로 discovery 요청)
    Route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]),
    # /mcp 하위 경로도 유지 (하위 호환)
    Route("/mcp/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"]),
    Route("/mcp/oauth/authorize", oauth_authorize, methods=["GET", "POST"]),
    Route("/mcp/oauth/register",  oauth_register,  methods=["POST"]),
    Route("/mcp/oauth/token",     oauth_token,     methods=["POST"]),
    Route("/mcp/oauth/revoke",    oauth_revoke,    methods=["POST"]),
]
