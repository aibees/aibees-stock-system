from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


#: 프로세스당 연결 풀. DB 서버 max_connections 가 50 이라(2026-11-12 실측) 프로세스마다
#: 10+20 을 잡던 예전 값으로는 인증 서버(gunicorn 4워커)만으로 한도를 넘길 수 있었다
#: → 'Too many connections' 로 기동 실패. 평소 열어 두는 연결(pool_size)을 줄이고,
#: 배치의 KIS 엔진 스레드(사용자 수만큼) + 메인 세션이 동시에 써도 모자라지 않게 최대 10 으로 둔다.
#: 워커가 여러 개인 프로세스는 환경변수로 더 줄인다 (py-naver-stock-theme/docker-compose.yml).
DB_POOL_SIZE = _env_int("DB_POOL_SIZE", 3)
DB_MAX_OVERFLOW = _env_int("DB_MAX_OVERFLOW", 7)


class Database:
    def __init__(self):
        self.engine = create_engine(
            os.getenv("DB_URL", "mysql+pymysql://stock:stock123!!@210.100.177.162:3333/stock"),
            echo=False,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_timeout=60,
            connect_args={"connect_timeout": 60},
        )
        self.SessionLocal = scoped_session(sessionmaker(bind=self.engine))

    def get_session(self):
        return self.SessionLocal

dbConn = Database()
