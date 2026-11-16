# main.py
import sys
import uvicorn
from app.flask_app.runner import FlaskApp
from app.mcp_server import create_app as create_mcp_app

# ── Flask WSGI 앱 (gunicorn이 이 변수를 참조) ──────────────
flaskApp = FlaskApp(None).get_app()

# ── MCP ASGI 앱 ─────────────────────────────────────────────
mcpApp = create_mcp_app()


# ── 실행 모드 분기 ───────────────────────────────────────────
def process(args):
    mode = args[1] if len(args) > 1 else "flask"

    if mode == "test":
        # 테스트 모듈은 import 하는 순간 KisEngine(1번 사용자 KIS 키)을 만든다 → 서버(gunicorn app.main:flaskApp)가
        # 이 파일을 import 할 때 같이 끌려오지 않게 test 모드에서만 불러온다.
        from app.test.mcp_test_1 import test as test_1
        test_1()

    elif mode == "mcp":
        print(f"[MCP] starting → http://0.0.0.0:5558/mcp")
        uvicorn.run(mcpApp, host='0.0.0.0', port=5558, log_level="info")
    else:
        print(f"[Flask] starting → http://0.0.0.0:5556")
        flaskApp.run(host="0.0.0.0", port=5556)


if __name__ == "__main__":
    process(sys.argv)
