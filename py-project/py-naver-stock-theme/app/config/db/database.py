from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os

class Database:
    def __init__(self):
        self.engine = create_engine(
            os.getenv("DB_URL", "mysql+pymysql://stock:stock123!!@210.183.63.247:3333/stock_dev"),
            echo=False,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=20,
            pool_timeout=60,
            connect_args={"connect_timeout": 60},
        )
        self.SessionLocal = scoped_session(sessionmaker(bind=self.engine))

    def get_session(self):
        return self.SessionLocal

dbConn = Database()