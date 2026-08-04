## pytnon-batch
## NAVER STOCK THEME Crawling

FROM python:3.12.3

ENV POETRY_VERSION=1.8.2
RUN pip install -U "poetry==$POETRY_VERSION"

WORKDIR /workdir

# copy source code
# shared 를 먼저 복사한다 (poetry path dependency '../shared' 해석에 필요).
# 빌드 컨텍스트는 py-project/ 이므로 'docker build -f <이 파일> .' 을
# py-project 디렉터리에서 실행해야 한다.
COPY shared /shared

COPY py-stock-batch/pyproject.toml py-stock-batch/poetry.lock /workdir/

RUN poetry lock
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

COPY py-stock-batch/ /workdir/

# Python 경로 설정
ENV PYTHONPATH=/usr/local/bin/python3.12

# Poetry 바이너리 권한 확인 및 설정
RUN chmod +x /usr/local/bin/poetry

# Poetry가 설치된 Python을 사용하도록 설정
RUN sed -i '1s|^.*$|#!/usr/local/bin/python3.12|' /usr/local/bin/poetry

# 권한과 바이너리 위치 확인
RUN ls -l /usr/local/bin/poetry

# run command (메인 진입점 — 스케줄러 ON)
# 기존 app.main:flaskApp 은 심볼 미정의라 app.flask_app.wsgi:app 으로 교체.
# ※ 트레이딩 worker 는 이 이미지가 아니라 별개 이미지(Dockerfile.worker → py-stock-worker)로 배포한다.
CMD ["poetry", "run", "gunicorn", "-w", "1", "-b", "0.0.0.0:5557", "app.flask_app.wsgi:app"]