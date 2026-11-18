"""
양봉상회 API 로컬 실행 — docker-compose.yml 의 설정을 로컬 Flask 개발 서버로 재현한다.

    cd py-project/py-yangbong-api
    poetry install                     (처음 한 번)
    .venv/Scripts/python run_local.py  (Windows)
    .venv/bin/python3 run_local.py     (macOS/Linux)

.env.yangbong(gitignored, .env.yangbong.example 참고)을 먼저 읽는다.
load_dotenv() 는 이미 있는 값을 덮지 않으므로 여기서 넣은 값이 우선한다.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / '.env.yangbong'

if not ENV_FILE.exists():
    sys.exit(f"[yangbong-local] {ENV_FILE.name} 가 없습니다. .env.yangbong.example 을 복사해 값을 채우세요.")

load_dotenv(ENV_FILE, override=True)

if '<' in (os.environ.get('DB_URL') or ''):
    sys.exit("[yangbong-local] .env.yangbong 의 DB_URL 자리표시(<비밀번호> 등)를 실제 값으로 바꾸세요.")

# docker-compose.yml 의 environment 와 같게
os.environ.setdefault('TZ', 'Asia/Seoul')
os.environ.setdefault('DB_POOL_SIZE', '2')
os.environ.setdefault('DB_MAX_OVERFLOW', '1')
# Anthropic 키 — compose 처럼 비밀상회 키 파일을 같이 쓴다(따로 두려면 .env.yangbong 에 ANTHROPIC_ENV_FILE)
os.environ.setdefault('ANTHROPIC_ENV_FILE', str(HERE.parent / 'py-secret-api' / 'app' / 'config' / 'keys' / 'anthropic.env'))

os.chdir(HERE)
sys.path.insert(0, str(HERE))

from app.main import flaskApp  # noqa: E402  (환경변수를 먼저 넣은 뒤 import 해야 한다)

print("[yangbong-local] http://0.0.0.0:5556")
flaskApp.run(host="0.0.0.0", port=5556)
