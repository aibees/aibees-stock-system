## py-stock-web — NAVER STOCK THEME / Flask API
##
## 빌드 컨텍스트는 py-project/ 다. shared(공용 ORM/DAO)가 컨텍스트에 포함되어야
## poetry 의 path dependency('../shared')가 해석된다.
##   docker build -f py-naver-stock-theme/Dockerfile -t py-stock-web .   (py-project/ 에서)
## build_docker.sh 가 알아서 py-project/ 로 이동해 실행한다.

FROM python:3.12.3

ENV POETRY_VERSION=1.8.2 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
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
RUN poetry lock --no-update \
 && poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi

COPY py-naver-stock-theme/ /workdir/

EXPOSE 5556

CMD ["poetry", "run", "gunicorn", "-k", "gevent", "--timeout", "180", "-w", "4", "-b", "0.0.0.0:5556", "app.main:flaskApp"]
