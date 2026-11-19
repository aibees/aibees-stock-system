"""
양봉상회 API (py-yangbong-api, 2026-11-19 py-secret-api 에서 분리).

    gunicorn app.main:flaskApp                 운영(Dockerfile CMD)
    python -m app.main                         로컬 실행(5556)
    python -m app.workers.ai_job_worker        AI 워커(같은 이미지, 다른 명령)
"""
from app.flask_app.runner import FlaskApp

# Flask WSGI 앱 (gunicorn 이 이 변수를 참조)
flaskApp = FlaskApp(None).get_app()


if __name__ == "__main__":
    print("[Flask] starting → http://0.0.0.0:5556")
    flaskApp.run(host="0.0.0.0", port=5556)
