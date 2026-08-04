"""
메인 앱 WSGI 진입점.

gunicorn 대상:
    gunicorn -w 1 -b 0.0.0.0:5557 app.flask_app.wsgi:app

메인은 스케줄러를 켠 상태로 뜬다(SCHEDULER_ENABLED 기본 true).
worker 진입점은 app.worker_app.wsgi 를 사용한다(자동 스케줄 off).

※ 기존 Dockerfile 은 app.main:flaskApp 을 참조했으나 해당 심볼이 정의돼 있지
   않았다. 진입점을 이 모듈로 일원화한다.
"""
from app.flask_app.runner import FlaskApp

app = FlaskApp(None).get_app()
