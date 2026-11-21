"""
트레이닝 학습 기록(user_training_progress) DAO — 양봉상회 전용(sql/yangbong/011).

마친 단계 1개당 1행이고 지우지 않는다. 기기에서 마친 기록을 올리면 없는 것만 더한다(INSERT IGNORE).
커밋은 호출자(라우터)가 한다.

테이블이 아직 없는 DB(011 미적용)에서는 조회는 빈 목록, 저장은 건너뛴다 — 화면은 기기 기록으로 계속 동작하고,
API 오류 알림(aibeesApi 인터셉터의 alert)이 뜨지 않게 하려는 것이다. 있는지는 스키마별로 한 번만 확인한다.
"""
from datetime import datetime

from sqlalchemy import text

TABLE = "user_training_progress"


class UserTrainingDao:
    _table_cache = {}

    def has_table(self, session) -> bool:
        schema = session.execute(text("SELECT DATABASE()")).scalar()
        if not self._table_cache.get(schema):
            # 없을 때는 캐시하지 않는다 — SQL 을 적용하면 서버를 다시 띄우지 않아도 바로 쓰이게
            self._table_cache[schema] = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :t"), {"t": TABLE}).scalar() > 0
        return self._table_cache[schema]

    def select_done(self, session, user_id: int) -> list[dict]:
        """마친 단계 [{stage_key, done_at(epoch ms)}], 마친 순서대로."""
        if not self.has_table(session):
            return []
        rows = session.execute(text(
            f"SELECT stage_key, done_at FROM {TABLE} WHERE user_id = :uid ORDER BY done_at, stage_key"),
            {"uid": user_id}).all()
        return [{"stage_key": r.stage_key, "done_at": int(r.done_at.timestamp() * 1000)} for r in rows]

    def add_done(self, session, user_id: int, stage_keys: list[str]) -> int:
        """없는 단계만 더한다. 더한 행 수. 테이블이 없으면 0."""
        if not stage_keys or not self.has_table(session):
            return 0
        now = datetime.now().replace(microsecond=0)
        added = 0
        for key in stage_keys:
            added += session.execute(text(
                f"INSERT IGNORE INTO {TABLE} (user_id, stage_key, done_at) VALUES (:uid, :key, :at)"),
                {"uid": user_id, "key": key, "at": now}).rowcount
        return added
