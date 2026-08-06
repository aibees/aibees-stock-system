## py-stock-web — NAVER STOCK THEME / Flask API
##
## 빌드 컨텍스트는 py-project/ 다. shared(공용 ORM/DAO)가 컨텍스트에 포함되어야
## poetry 의 path dependency('../shared')가 해석된다.
##   docker build -f py-naver-stock-theme/Dockerfile -t py-stock-web .   (py-project/ 에서)
## build_docker.sh 가 알아서 py-project/ 로 이동해 실행한다.
##
## 베이스는 -slim 이 아니라 full 이미지를 쓴다.
## lxml / scipy / gevent 가 wheel 을 못 받는 상황에서 소스 빌드로 넘어가는데,
## slim 에는 컴파일러가 없어 그때 빌드가 통째로 실패한다.

FROM python:3.12.3

ENV POETRY_VERSION=1.8.2 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Seoul

# 컨테이너 기본 TZ 는 UTC 라 로그 시각이 9시간 어긋난다.
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip install -U "poetry==$POETRY_VERSION"

WORKDIR /workdir

# WORKDIR 가 /workdir 이므로 pyproject 의 '../shared' 는 /shared 로 해석된다.
COPY shared /shared

COPY py-naver-stock-theme/pyproject.toml py-naver-stock-theme/poetry.lock /workdir/

# poetry.lock 의 고정 버전을 유지한 채 메타데이터만 갱신.
# (--no-update 없이 'poetry lock' 을 돌리면 락이 무의미해져 빌드마다 버전이 달라진다)
#
# --no-root: 이 프로젝트는 라이브러리가 아니라 앱이라 설치할 패키지 디렉터리가 없다.
#   빼면 "No file/folder found for package n-theme" 경고가 뜨고,
#   Poetry 경고문 그대로 **다음 버전부터는 에러**가 된다. 미리 막는다.
RUN poetry lock --no-update \
 && poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

# CMD 와 **동일한 형태**로 실행 가능한지 빌드 단계에서 확인한다.
# 이게 없으면 진입점이 어긋났을 때 컨테이너가 기동하는 순간에야 터진다
#   (exec: "gunicorn": executable file not found in $PATH)
# 빌드에서 걸리면 돌던 서비스는 그대로 유지된다.
RUN poetry run gunicorn --version

COPY py-naver-stock-theme/ /workdir/

EXPOSE 5556

# 진입점은 app.flask_app.wsgi:app.
#   구 설정의 app.main:flaskApp 은 모듈 레벨에서 app.test.mcp_test_1(→ KisEngine
#   실전 인증)과 create_mcp_app() 을 함께 끌고 와 worker 부팅이 실패했다.
#   상세는 app/flask_app/wsgi.py 주석 참조.
#
# ⚠ 'poetry run' 을 벗기지 말 것.
#   위 RUN 에서 `poetry lock` 이 `poetry config virtualenvs.create false` **보다 먼저**
#   실행되는데, 그 시점에 poetry 가 프로젝트 venv 를 만들어버린다
#   (/root/.cache/pypoetry/virtualenvs/n-theme-*-py3.12).
#   이어지는 poetry install 은 그 venv 에 설치하므로 시스템 PATH 에는 gunicorn 이 없다.
#   맨 gunicorn 으로 바꾸면 컨테이너 기동 시 이렇게 죽는다:
#     exec: "gunicorn": executable file not found in $PATH
#   (순서를 바꾸거나 POETRY_VIRTUALENVS_CREATE 로 우회할 수도 있지만, 베이스 이미지의
#    PEP 668 정책에 따라 시스템 설치가 거부될 수 있어 검증된 이 형태를 유지한다.
#    PID 1 이 poetry 가 되는 문제는 compose 의 init: true 로 처리한다)
#
# --access-logfile - : 요청 로그를 stdout 으로. 없으면 docker logs 에 접근 기록이
#   전혀 안 남아 "배포는 됐는데 요청이 들어오는지" 조차 확인할 수 없다.
# --worker-tmp-dir /dev/shm : gunicorn heartbeat 파일이 느린 overlayfs 에 생기면
#   worker 가 오탐으로 죽는 알려진 이슈를 피한다.
CMD ["poetry", "run", "gunicorn", \
     "-k", "gevent", \
     "-w", "4", \
     "--timeout", "180", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "-b", "0.0.0.0:5556", \
     "app.flask_app.wsgi:app"]
