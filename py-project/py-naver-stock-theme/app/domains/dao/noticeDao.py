"""
공지사항 조회 DAO (sql/48_notice.sql). 읽기 전용 — 등록·수정은 DB 에 직접 한다.

enabled_flag='Y' 인 행만 보인다. 목록은 본문(content)을 싣지 않는다.
"""
from sqlalchemy import text


class NoticeDao:
    def __init__(self):
        self.name = 'NoticeDao'

    def select_notice_page(self, session, page: int, size: int):
        """공지 목록(작성일자 최신순) + total."""
        total = session.execute(
            text("SELECT COUNT(*) FROM notice WHERE enabled_flag = 'Y'")
        ).scalar() or 0

        rows = session.execute(
            text("""
                SELECT notice_id, title, category, created_date
                FROM   notice
                WHERE  enabled_flag = 'Y'
                ORDER BY created_date DESC, notice_id DESC
                LIMIT :limit OFFSET :offset
            """),
            {'limit': size, 'offset': page * size},
        ).mappings().all()
        return [dict(r) for r in rows], total

    def select_notice(self, session, notice_id: int):
        """공지 1건(본문 포함). 없거나 숨김이면 None."""
        row = session.execute(
            text("""
                SELECT notice_id, title, category, content, created_date
                FROM   notice
                WHERE  notice_id = :notice_id AND enabled_flag = 'Y'
            """),
            {'notice_id': notice_id},
        ).mappings().first()
        return dict(row) if row else None
