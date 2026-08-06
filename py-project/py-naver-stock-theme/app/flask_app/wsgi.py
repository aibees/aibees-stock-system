"""Flask WSGI 진입점.

    gunicorn -k gevent -w 4 -b 0.0.0.0:5556 app.flask_app.wsgi:app

기존엔 Dockerfile 이 `app.main:flaskApp` 을 참조했는데, app/main.py 는 모듈
레벨에서 아래 두 가지를 함께 끌고 온다:

  1) `from app.test.mcp_test_1 import test`
     → mcp_test_1 이 모듈 레벨에서 `KisEngine(virtual=False)` 를 실행한다.
       DB 조회 + PyKis 실전 인증(네트워크) 이 gunicorn worker 부팅 중에 일어나고,
       실패하면 worker 가 그대로 죽는다. **테스트 모듈이 운영 진입점에 묶여 있었다.**
  2) `mcpApp = create_mcp_app()`
     → MCP(Starlette) 앱을 Flask 컨테이너 안에서 구성한다.
       MCP 는 docker-compose.mcp.yml 로 분리 운영하므로 여기서 만들 이유가 없다.

이 모듈은 Flask 앱만 만든다. MCP 진입점은 `python -m app.main mcp` 를 그대로 쓴다.
(py-stock-batch 의 app/flask_app/wsgi.py 와 동일한 구조)
"""
from app.flask_app.runner import FlaskApp

app = FlaskApp(None).get_app()
