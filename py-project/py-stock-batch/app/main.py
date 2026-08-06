import sys


# ※ 앱 생성을 모듈 레벨에서 하지 않는다(예전엔 여기서 바로 만들었다).
#   spawn 자식 프로세스는 부팅할 때 __main__ 모듈을 경로로 다시 실행한다
#   (multiprocessing.spawn._fixup_main_from_path).
#   즉 `python app/main.py` 로 띄운 상태에서 /once 를 때리면, 자식이
#   FlaskApp → scheduler_app.runner → StockScheduler() 를 통째로 다시
#   세우면서 job 은 시작도 못 한다. 가드 안으로 내려 그 경로를 끊는다.
#   (운영은 gunicorn app.flask_app.wsgi:app 을 쓴다 — wsgi.py 참고)
def process(args):
    from app.flask_app.runner import FlaskApp
    FlaskApp(None).get_app().run(host="0.0.0.0", port=5557, threaded=True)


if __name__ == "__main__":
    process(sys.argv)