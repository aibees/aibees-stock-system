## py-yangbong-api — 양봉상회 API + AI 워커 (2026-11-19 py-secret-api 에서 분리)
##
## 빌드 컨텍스트는 py-project/ 다. shared(stock_shared·web_shared)가 컨텍스트에 있어야
## poetry 의 path dependency('../shared')가 해석된다.
##   docker build -f py-yangbong-api/Dockerfile -t py-yangbong-web .   (py-project/ 에서)
##
## 같은 이미지로 두 가지를 띄운다(이 폴더 docker-compose.yml):
##   API      : 아래 CMD (gunicorn)
##   AI 워커  : command: python -m app.workers.ai_job_worker
##
## Anthropic 키: docker-compose.yml 이 비밀상회 키 파일을 /workdir/secrets/anthropic.env 로 마운트하고 ANTHROPIC_ENV_FILE 로 알려 준다.
##   (그 밖의 방법: 환경변수 SECRET_KEY, 또는 /workdir/app/config/keys/anthropic.env — web_shared.config.anthropicConfig 참고)

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

COPY py-yangbong-api/pyproject.toml py-yangbong-api/poetry.lock /workdir/

# poetry.lock 의 고정 버전을 유지한 채 메타데이터만 갱신(py-secret-api Dockerfile 과 같은 방식).
RUN poetry lock --no-update \
 && poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi

COPY py-yangbong-api/ /workdir/

EXPOSE 5556

CMD ["poetry", "run", "gunicorn", "-k", "gevent", "--timeout", "180", "-w", "4", "-b", "0.0.0.0:5556", "app.main:flaskApp"]
