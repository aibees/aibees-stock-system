from contextlib import contextmanager

from stock_shared.db.database import dbConn

@contextmanager
def get_session():
    session = dbConn.get_session()
    try:
        yield session
    finally:
        session.close()
