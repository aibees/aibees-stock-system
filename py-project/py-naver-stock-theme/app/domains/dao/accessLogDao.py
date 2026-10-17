"""
로그인 / 메뉴 접근 기록 DAO (sql/37_user_access_log.sql).

요청 세션(g.db)이 아니라 엔진에서 별도 커넥션을 열어 바로 commit 한다.
  - 로그인 실패 시 라우터가 g.db 를 rollback 해도 실패 기록은 남아야 한다.
  - 기록이 실패해도(테이블 미적용 등) 로그인·화면 이동은 막지 않는다 → 예외는 로그만 남기고 삼킨다.
"""
import logging
from datetime import datetime, timedelta

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

    # 조회 — 접속 로그 관리자 화면 (router_access_log.py, ADMIN 전용)
    # ================================================================
    @staticmethod
    def _parse_from(value):
        """'YYYY-MM-DD' 또는 ISO8601 → datetime. 'YYYY-MM-DD' 는 00:00:00 으로 보정."""
        if not value:
            return None
        v = str(value).strip()
        return datetime.strptime(v, "%Y-%m-%d") if len(v) == 10 else datetime.fromisoformat(v)

    @staticmethod
    def _parse_to(value):
        """'to' 상한. 'YYYY-MM-DD' 로 오면 다음날 00:00:00 으로 보정(exclusive <)."""
        if not value:
            return None
        v = str(value).strip()
        if len(v) == 10:
            return datetime.strptime(v, "%Y-%m-%d") + timedelta(days=1)
        return datetime.fromisoformat(v)

    def select_login_log_page(self, session, page: int, size: int,
                               login_type=None, result=None, keyword=None,
                               date_from=None, date_to=None):
        """user_login_log 목록(최신순) + total. 조회는 요청 세션(g.db)을 그대로 쓴다(기록과 달리 분리 불필요)."""
        where = """
            WHERE (:login_type IS NULL OR l.login_type = :login_type)
              AND (:result     IS NULL OR l.result = :result)
              AND (:date_from  IS NULL OR l.created_date >= :date_from)
              AND (:date_to    IS NULL OR l.created_date <  :date_to)
              AND (:keyword    IS NULL OR l.login_key LIKE :keyword OR l.client_ip LIKE :keyword
                   OR um.user_name LIKE :keyword OR um.email LIKE :keyword)
        """
        params = {
            'login_type': login_type or None,
            'result': result or None,
            'keyword': f"%{keyword}%" if keyword else None,
            'date_from': self._parse_from(date_from),
            'date_to': self._parse_to(date_to),
        }

        total = session.execute(
            text(f"""
                SELECT COUNT(*)
                FROM   user_login_log l
                LEFT JOIN user_master um ON um.user_id = l.user_id
                {where}
            """), params
        ).scalar() or 0

        rows = session.execute(
            text(f"""
                SELECT l.log_id, l.user_id, um.user_name, um.email, l.login_type, l.result,
                       l.login_key, l.fail_reason, l.client_ip, l.user_agent, l.created_date
                FROM   user_login_log l
                LEFT JOIN user_master um ON um.user_id = l.user_id
                {where}
                ORDER BY l.log_id DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, 'limit': size, 'offset': page * size},
        ).mappings().all()
        return [dict(r) for r in rows], total

    def select_menu_access_log_page(self, session, page: int, size: int,
                                     menu_code=None, keyword=None,
                                     date_from=None, date_to=None):
        """user_menu_access_log 목록(최신순) + total."""
        where = """
            WHERE (:menu_code IS NULL OR m.menu_code = :menu_code)
              AND (:date_from IS NULL OR m.created_date >= :date_from)
              AND (:date_to   IS NULL OR m.created_date <  :date_to)
              AND (:keyword   IS NULL OR m.menu_path LIKE :keyword OR m.client_ip LIKE :keyword
                   OR um.user_name LIKE :keyword OR um.email LIKE :keyword)
        """
        params = {
            'menu_code': menu_code or None,
            'keyword': f"%{keyword}%" if keyword else None,
            'date_from': self._parse_from(date_from),
            'date_to': self._parse_to(date_to),
        }

        total = session.execute(
            text(f"""
                SELECT COUNT(*)
                FROM   user_menu_access_log m
                LEFT JOIN user_master um ON um.user_id = m.user_id
                {where}
            """), params
        ).scalar() or 0

        rows = session.execute(
            text(f"""
                SELECT m.log_id, m.user_id, um.user_name, um.email, m.menu_code, m.menu_path,
                       m.client_ip, m.user_agent, m.created_date
                FROM   user_menu_access_log m
                LEFT JOIN user_master um ON um.user_id = m.user_id
                {where}
                ORDER BY m.log_id DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, 'limit': size, 'offset': page * size},
        ).mappings().all()
        return [dict(r) for r in rows], total
