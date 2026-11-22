"""
트레이닝 차트 퀴즈 DAO — sql/yangbong/014 의 표. 커밋은 호출자(라우터)가 한다.

⚠ training_question.stock_code · base_date 는 내부 전용이다. 여기서 화면용으로 돌려주는 dict 에는 넣지 않는다.
"""
import json
from datetime import date, datetime

from sqlalchemy import bindparam, text


def _j(v):
    return v if isinstance(v, (dict, list)) else json.loads(v)


class TrainingQuizDao:
    _table_cache = {}

    def has_tables(self, session) -> bool:
        """014 적용 여부. 없을 때는 캐시하지 않는다(적용 즉시 쓰이게)."""
        schema = session.execute(text("SELECT DATABASE()")).scalar()
        if not self._table_cache.get(schema):
            self._table_cache[schema] = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() "
                "AND table_name IN ('training_question', 'training_attempt', 'training_daily_set', 'training_hint_log', "
                "'pattern', 'pattern_stat')")).scalar() == 6
        return self._table_cache[schema]

    # ── 문제 ──────────────────────────────────────────────────
    def question(self, session, qid: int):
        """내부용 전체 행(stock_code 포함) — 라우터가 응답을 만들 때 필요한 열만 골라 쓴다."""
        r = session.execute(text(
            "SELECT q.id, q.pattern_id, q.level, q.snapshot_json, q.outcome_json, q.explanation, q.hint, "
            "p.name AS pattern_name, p.tier, p.is_public "
            "FROM training_question q JOIN pattern p ON p.id = q.pattern_id WHERE q.id = :id"), {"id": qid}).first()
        if r is None:
            return None
        return {"id": r.id, "pattern_id": r.pattern_id, "level": int(r.level), "snapshot": _j(r.snapshot_json),
                "outcome": _j(r.outcome_json), "explanation": r.explanation, "hint": r.hint,
                "pattern_name": r.pattern_name, "public": r.tier == 'BASIC' and bool(r.is_public)}

    def pick_new(self, session, user_id: int, max_level: int, n: int, exclude: list[int]) -> list[int]:
        """아직 안 푼 문제 n개. 최근 출제분 위주로 섞어 고르고, 난이도 오름차순으로 돌려준다.
        공개(BASIC) 패턴이고 통계(12개월) 발생 건수가 있는 문제만."""
        q = text(
            "SELECT q.id, q.level FROM training_question q "
            "JOIN pattern p ON p.id = q.pattern_id AND p.tier = 'BASIC' AND p.is_public = 1 "
            "JOIN pattern_stat s ON s.pattern_id = q.pattern_id AND s.window_months = 12 AND s.occurrences > 0 "
            "LEFT JOIN training_attempt a ON a.question_id = q.id AND a.user_id = :uid "
            "WHERE a.id IS NULL AND q.level <= :lv AND q.id NOT IN :ex "
            "ORDER BY RAND() LIMIT :n").bindparams(bindparam('ex', expanding=True))
        rows = session.execute(q, {"uid": user_id, "lv": max_level, "ex": exclude or [0], "n": n}).all()
        return [r.id for r in sorted(rows, key=lambda r: (r.level, r.id))]

    # ── 일일 세트 ─────────────────────────────────────────────
    def daily_set(self, session, user_id: int, d: date):
        r = session.execute(text(
            "SELECT question_ids FROM training_daily_set WHERE user_id = :uid AND set_date = :d"), {"uid": user_id, "d": d}).first()
        return [int(x) for x in _j(r.question_ids)] if r else None

    def save_daily_set(self, session, user_id: int, d: date, ids: list[int]) -> None:
        session.execute(text(
            "INSERT INTO training_daily_set (user_id, set_date, question_ids) VALUES (:uid, :d, :ids) "
            "ON DUPLICATE KEY UPDATE question_ids = VALUES(question_ids)"), {"uid": user_id, "d": d, "ids": json.dumps(ids)})

    def ever_in_sets(self, session, user_id: int, qid: int) -> bool:
        """이 사람에게 출제된 적이 있는 문제인가(세트에 들어간 적)."""
        return session.execute(text(
            "SELECT 1 FROM training_daily_set WHERE user_id = :uid AND JSON_CONTAINS(question_ids, :q) LIMIT 1"),
            {"uid": user_id, "q": str(int(qid))}).first() is not None

    # ── 응답 ──────────────────────────────────────────────────
    def attempt(self, session, user_id: int, qid: int):
        r = session.execute(text(
            "SELECT id, answer, used_hint, is_match, score, answered_at FROM training_attempt "
            "WHERE user_id = :uid AND question_id = :q"), {"uid": user_id, "q": qid}).first()
        return r

    def attempted_ids(self, session, user_id: int, ids: list[int]) -> set:
        if not ids:
            return set()
        rows = session.execute(text(
            "SELECT question_id FROM training_attempt WHERE user_id = :uid AND question_id IN :ids").bindparams(
            bindparam('ids', expanding=True)), {"uid": user_id, "ids": ids}).all()
        return {r[0] for r in rows}

    def recent_matches(self, session, user_id: int, limit: int = 10) -> list[bool]:
        rows = session.execute(text(
            "SELECT is_match FROM training_attempt WHERE user_id = :uid ORDER BY answered_at DESC, id DESC LIMIT :n"),
            {"uid": user_id, "n": limit}).all()
        return [bool(r[0]) for r in rows]

    def insert_attempt(self, session, user_id: int, qid: int, answer: str, used_hint: bool, is_match: bool, score: int):
        """같은 문제를 두 번 내면 0행(uk_ua) — 점수는 처음 한 번만 쌓인다."""
        res = session.execute(text(
            "INSERT IGNORE INTO training_attempt (user_id, question_id, answer, used_hint, is_match, score, answered_at) "
            "VALUES (:uid, :q, :a, :h, :m, :s, :at)"),
            {"uid": user_id, "q": qid, "a": answer, "h": int(used_hint), "m": int(is_match), "s": score,
             "at": datetime.now().replace(microsecond=0)})
        return res.rowcount, getattr(res, "lastrowid", None)

    def total_score(self, session, user_id: int) -> int:
        return int(session.execute(text(
            "SELECT COALESCE(SUM(score), 0) FROM training_attempt WHERE user_id = :uid"), {"uid": user_id}).scalar() or 0)

    def answered_days(self, session, user_id: int, limit: int = 400) -> set:
        rows = session.execute(text(
            "SELECT DISTINCT DATE(answered_at) FROM training_attempt WHERE user_id = :uid "
            "ORDER BY 1 DESC LIMIT :n"), {"uid": user_id, "n": limit}).all()
        return {r[0] for r in rows}

    def history(self, session, user_id: int, only_mismatch: bool, limit: int = 100) -> list:
        cond = "AND a.is_match = 0" if only_mismatch else ""
        rows = session.execute(text(
            f"SELECT a.question_id, a.answer, a.is_match, a.score, a.answered_at, q.level, p.name AS pattern_name "
            f"FROM training_attempt a JOIN training_question q ON q.id = a.question_id JOIN pattern p ON p.id = q.pattern_id "
            f"WHERE a.user_id = :uid {cond} ORDER BY a.answered_at DESC, a.id DESC LIMIT :n"),
            {"uid": user_id, "n": limit}).all()
        return rows

    # ── 힌트 ──────────────────────────────────────────────────
    def mark_hint(self, session, user_id: int, qid: int) -> None:
        session.execute(text(
            "INSERT IGNORE INTO training_hint_log (user_id, question_id, used_at) VALUES (:uid, :q, :at)"),
            {"uid": user_id, "q": qid, "at": datetime.now().replace(microsecond=0)})

    def hint_used(self, session, user_id: int, qid: int) -> bool:
        return session.execute(text(
            "SELECT 1 FROM training_hint_log WHERE user_id = :uid AND question_id = :q"), {"uid": user_id, "q": qid}).first() is not None

    # ── 통계 ──────────────────────────────────────────────────
    def pattern_stat(self, session, pattern_id: int, window: int = 12):
        return session.execute(text(
            "SELECT occurrences, up_count, down_count, flat_count FROM pattern_stat "
            "WHERE pattern_id = :p AND window_months = :w"), {"p": pattern_id, "w": window}).first()
