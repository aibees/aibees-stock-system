# MCP Server 설정 가이드

## 개요

`app/mcp_server.py`는 기존 Flask 서버의 서비스 레이어를 **MCP(Model Context Protocol) tool**로 노출합니다.
**Streamable HTTP transport + OAuth 2.1** 인증으로 동작하며, Flask(5556)와 별도 포트로 독립 실행됩니다.

## 엔드포인트

| 경로 | 설명 |
|---|---|
| `POST/GET /mcp` | MCP 통신 (인증 필요) |
| `GET /.well-known/oauth-authorization-server` | OAuth 메타데이터 (public) |
| `POST /oauth/token` | 토큰 발급 (public) |
| `POST /oauth/register` | 동적 클라이언트 등록 (옵션) |
| `POST /oauth/revoke` | 토큰 폐기 (public) |

## OAuth 인증 흐름

### Authorization Code Flow (Claude Desktop — 권장)

```
Claude Desktop                    MCP Server
   │                                       │
   │── POST /mcp ──────────────────────────▶ 401 + WWW-Authenticate
   │── GET /.well-known/oauth-... ─────────▶ { authorization_endpoint, token_endpoint, ... }
   │── 브라우저 팝업 /mcp/oauth/authorize ──▶ API Secret 입력 폼
   │   (사용자가 API Secret 입력)           │
   │── POST /mcp/oauth/token ──────────────▶ { access_token, refresh_token, expires_in }
   │    (authorization_code + PKCE)        │
   │── POST /mcp (Bearer <token>) ─────────▶ 200 OK
   │                           ·
   │   (access_token 만료 시)              │
   │── POST /mcp/oauth/token ──────────────▶ { access_token, refresh_token, expires_in }
   │    (grant_type=refresh_token)         │  ← 브라우저 팝업 없이 자동 갱신
```

### Client Credentials Flow (M2M / 서버 간)

```
MCP Agent                         MCP Server
   │                                       │
   │── POST /mcp/oauth/token ─────────────▶ { access_token, expires_in }
   │    (client_id + client_secret)        │  (refresh_token 없음)
   │── POST /mcp (Bearer <token>) ─────────▶ 200 OK
```

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | 바인딩 주소 |
| `MCP_PORT` | `5558` | 포트 |
| `MCP_BASE_URL` | `http://localhost:5558` | 외부에서 보이는 URL |
| `MCP_JWT_SECRET` | (랜덤) | JWT 서명 키. **재시작 후에도 토큰 유지하려면 반드시 고정** |
| `MCP_CLIENT_ID` | (없음) | 사전 등록 클라이언트 ID |
| `MCP_CLIENT_SECRET` | (없음) | 사전 등록 클라이언트 시크릿 |
| `MCP_TOKEN_TTL` | `3600` | 액세스 토큰 유효시간(초) |
| `MCP_REFRESH_TOKEN_TTL` | `2592000` | 리프레시 토큰 유효시간(초, 기본 30일) |
| `MCP_ALLOW_DYNAMIC_REGISTRATION` | `false` | 동적 클라이언트 등록 허용 여부 |

## 의존성 설치

```bash
poetry install   # mcp ^1.9.0, uvicorn[standard] 포함
```

## 실행

```bash
# .env 예시
MCP_JWT_SECRET=your-256bit-secret
MCP_CLIENT_ID=claude-agent
MCP_CLIENT_SECRET=strong-random-secret
MCP_BASE_URL=http://localhost:5558

poetry run python -m app.mcp_server
```

---

## Claude Desktop 연결

Settings → Connectors → Add → URL 입력:
```
https://stock.aibeesworld.com/mcp
```
최초 연결 시 브라우저 팝업에서 API Secret 입력 → 이후 refresh_token으로 자동 갱신.

## Claude Code 연결 (.mcp.json)

```json
{
  "mcpServers": {
    "naver-stock": {
      "type": "http",
      "url": "https://stock.aibeesworld.com/mcp"
    }
  }
}
```
OAuth 흐름은 mcp-remote가 자동 처리합니다.

---

## Docker 구성

```yaml
services:
  flask-app:
    build: .
    command: poetry run python -m app.main
    ports:
      - "5556:5556"
    env_file: .env

  mcp-server:
    build: .
    command: poetry run python -m app.mcp_server
    ports:
      - "5558:5558"
    env_file: .env
    environment:
      - MCP_HOST=0.0.0.0
      - MCP_PORT=5558
      - MCP_BASE_URL=https://your-domain.com
```

`.env` 파일:
```
MCP_JWT_SECRET=your-256bit-secret-here
MCP_CLIENT_ID=claude-agent
MCP_CLIENT_SECRET=strong-random-secret-here
MCP_BASE_URL=http://localhost:5558
MCP_TOKEN_TTL=3600
MCP_REFRESH_TOKEN_TTL=2592000
MCP_ALLOW_DYNAMIC_REGISTRATION=false
```
