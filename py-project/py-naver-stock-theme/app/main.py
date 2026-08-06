# main.py — CLI 진입점 (개발 실행 / MCP 서버 기동)
#
#   python -m app.main          → Flask 개발 서버 (운영은 gunicorn + wsgi.py)
#   python -m app.main mcp      → MCP 서버 (Dockerfile.mcp 의 CMD)
#   python -m app.main test     → 로컬 테스트 스크립트
#
# ※ import 는 전부 함수 안에서 한다. 모듈 레벨에 두면 아래 사고가 난다:
#     · app.test.mcp_test_1 이 import 되는 순간 KisEngine(virtual=False) 가 돌아
#       DB 조회 + PyKis 실전 인증(네트워크)이 발생한다. mcp 모드로 띄우든
#       gunicorn 이 붙든 무조건 실행돼 실패 지점이 된다.
#     · create_mcp_app() 이 Flask 기동 시에도 MCP 앱을 만들어버린다.
#   운영 WSGI 진입점은 app/flask_app/wsgi.py 로 분리했다.
import sys


def process(args):
    mode = args[1] if len(args) > 1 else "flask"

    if mode == "test":
        from app.test.mcp_test_1 import test as test_1
        test_1()

    elif mode == "mcp":
        import uvicorn
        from app.mcp_server import create_app as create_mcp_app

        print("[MCP] starting → http://0.0.0.0:5558/mcp", flush=True)
        uvicorn.run(create_mcp_app(), host="0.0.0.0", port=5558, log_level="info")

    else:
        from app.flask_app.wsgi import app as flask_app

        print("[Flask] starting → http://0.0.0.0:5556 (개발용)", flush=True)
        flask_app.run(host="0.0.0.0", port=5556)


if __name__ == "__main__":
    process(sys.argv)
