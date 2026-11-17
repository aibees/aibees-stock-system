"""
양봉상회 API 로컬 실행 — docker-compose.yangbong.yml 의 설정을 로컬 Flask 개발 서버로 재현한다.

    cd py-project/py-naver-stock-theme
    .venv/Scripts/python run_yangbong_local.py     (Windows)
    .venv/bin/python3 run_yangbong_local.py        (macOS/Linux)

.env.yangbong(gitignored, .env.yangbong.example 참고)을 먼저 읽는다.
app 모듈의 load_dotenv() 는 .env(비밀상회용)를 읽지만 이미 있는 값은 덮지 않으므로
여기서 넣은 양봉상회 값이 우선한다.
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

# docker-compose.yangbong.yml 의 environment 와 같게
os.environ['APP_SERVICE'] = 'yangbong'
os.environ.setdefault('TZ', 'Asia/Seoul')
os.environ.setdefault('DB_POOL_SIZE', '2')
os.environ.setdefault('DB_MAX_OVERFLOW', '1')

os.chdir(HERE)
sys.path.insert(0, str(HERE))

from app.main import process  # noqa: E402  (환경변수를 먼저 넣은 뒤 import 해야 한다)

process([sys.argv[0], 'flask'])
