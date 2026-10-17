"""
로그인 / 메뉴 접근 기록 DAO (sql/37_user_access_log.sql).

요청 세션(g.db)이 아니라 엔진에서 별도 커넥션을 열어 바로 commit 한다.
  - 로그인 실패 시 라우터가 g.db 를 rollback 해도 실패 기록은 남아야 한다.
  - 기록이 실패해도(테이블 미적용 등) 로그인·화면 이동은 막지 않는다 → 예외는 로그만 남기고 삼킨다.
"""
import logging

from flask import request
from sqlalchemy import text

from stock_shared.db.database import dbConn


def client_ip() -> str | None:
    """프록시 뒤라면 X-Forwarded-For 첫 값, 아니면 remote_addr."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.remote_addr
    return (ip or None) and ip[:45]


def _user_agent() -> str | None:
    ua = request.headers.get('User-Agent')
    return ua[:500] if ua else None


class AccessLogDao:
    def __init__(self):
        self.name = 'AccessLogDao'

    def _insert(self, sql: str, params: dict) -> None:
        try:
            with dbConn.engine.begin() as conn:
                conn.execute(text(sql), params)
        except Exception as e:
            logging.error(f"[AccessLogDao] 기록 실패: {e}")

    def insert_login_log(self, login_type: str, result: str, user_id=None,
                         login_key: str | None = None, fail_reason: str | None = None) -> None:
        self._insert(
            "INSERT INTO user_login_log "
            "(user_id, login_type, result, login_key, fail_reason, client_ip, user_agent) "
            "VALUES (:user_id, :login_type, :result, :login_key, :fail_reason, :client_ip, :user_agent)",
            {
                'user_id': int(user_id) if user_id else None,
                'login_type': login_type,
                'result': result,
                'login_key': (login_key or None) and login_key[:200],
                'fail_reason': (fail_reason or None) and fail_reason[:300],
                'client_ip': client_ip(),
                'user_agent': _user_agent(),
            },
        )

    def insert_menu_access_log(self, user_id: int, menu_path: str, menu_code: str | None) -> None:
        self._insert(
            "INSERT INTO user_menu_access_log (user_id, menu_code, menu_path, client_ip, user_agent) "
            "VALUES (:user_id, :menu_code, :menu_path, :client_ip, :user_agent)",
            {
                'user_id': user_id,
                'menu_code': (menu_code or None) and menu_code[:100],
                'menu_path': menu_path[:200],
                'client_ip': client_ip(),
                'user_agent': _user_agent(),
            },
        )
