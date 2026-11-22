"""
router_training_chart.py — 트레이닝 차트 퀴즈(양봉상회 전용, 2026-11-22).
명세: meetings/설계_2026-11-22_트레이닝-화면.md 7·8장 · sql/yangbong/014 · 문제 생성은 app/workers/training_worker.py

    GET  /api/v1/training/today                오늘 세트(무료 3문제) + 남은 수 + 연속 학습일
    POST /api/v1/training/<qid>/hint           힌트(이 문제 점수 ×0.8). 연 기록을 남긴다
    POST /api/v1/training/<qid>/answer         body {answer: UP|FLAT|DOWN, usedHint} → 대조 결과 + 이후 20봉
    GET  /api/v1/training/history              다시 풀기 목록(구독 전용 — 아니면 403 SUBSCRIPTION_REQUIRED)
    GET  /api/v1/training/questions/<qid>      다시 풀 문제 하나(구독 전용, 전에 출제된 문제만)

지킬 것
  - stock_code · base_date · normalizedBase(실제 가격)는 어떤 응답에도 넣지 않는다(실제 차트를 찾아 답을 알 수 있다).
  - 답을 내기 전에는 futureCandles · outcome 을 내려보내지 않는다.
  - 내부 값 isMatch 를 화면은 "같은 방향을 봤어요 / 다른 방향이었어요"로만 쓴다. direction 라벨은 응답하지 않는다.

구독: 아직 결제(6,900원 안)가 없다. 지금은 꿀 "프리미엄 하루 이용권"(honey_pass)을 쓰는 중이면 구독으로 본다.
  결제가 생기면 _is_subscriber 만 바꾼다.
모두 로그인 필요. 표(014)가 없으면 today 는 ready=false 로 빈 세트를 준다.
"""
import logging

import simplejson as json
from flask import Blueprint, Response, g, request
from sqlalchemy import text

from app.domains.dao.trainingQuizDao import TrainingQuizDao
from app.services import honey_service as honey
from app.services.training.scoring import ANSWERS, HINT_MULTIPLIER, score_of
from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse

training_chart_bp = Blueprint("training_chart", __name__)
dao = TrainingQuizDao()

FREE_DAILY = 3
FREE_MAX_LEVEL = 2
SUB_MAX_LEVEL = 4
STAT_WINDOW = 12
FREE_CASE_PREVIEW = 3        # 무료: 사례 요약 + 3건(사례 목록 화면은 아카이브와 함께 만든다)

ALL_INDICATORS = ["MA", "VOLUME", "RSI", "MACD", "BOLLINGER"]
DEFAULT_INDICATORS = {
    1: ["MA"],
    2: ["MA", "VOLUME"],
    3: ["MA", "VOLUME", "RSI", "MACD"],
    4: ALL_INDICATORS,
}


def _err(code: str, message: str, status: int):
    return Response(json.dumps({"success": False, "error": {"code": code, "message": message}}, ensure_ascii=False),
                    status=status, content_type='application/json; charset=utf-8')


def _today():
    return honey.now_kst().date()


def _is_subscriber(user_id: int) -> bool:
    try:
        return honey.active_pass_until(g.db, user_id) is not None
    except Exception:
        g.db.rollback()
        return False


def _question_payload(q: dict) -> dict:
    """문제 화면용. 과거 120봉과 그 구간 지표만 — 미래·실제 가격·종목은 넣지 않는다."""
    snap = q["snapshot"]
    candles = snap["candles"]
    last, prev = candles[-1], (candles[-2] if len(candles) > 1 else candles[-1])
    change = round((last["c"] / prev["c"] - 1) * 100, 1) if prev["c"] else 0.0
    return {
        "questionId": q["id"],
        "level": q["level"],
        "defaultIndicators": DEFAULT_INDICATORS.get(q["level"], ["MA"]),
        "availableIndicators": ALL_INDICATORS,
        "basePrice": last["c"],
        "baseChangeRate": change,
        "snapshot": {"candles": candles, "indicators": snap["indicators"]},
    }


def _streak_days(user_id: int) -> int:
    """연속 학습일: 오늘(또는 아직 안 풀었으면 어제)까지 하루도 빠짐없이 한 문제 이상 푼 날 수."""
    from datetime import timedelta
    days = dao.answered_days(g.db, user_id)
    cur = _today()
    if cur not in days:
        cur -= timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def _quota(user_id: int, sub: bool, ids: list[int]) -> dict:
    used = len(dao.attempted_ids(g.db, user_id, ids))
    if sub:
        return {"isSubscriber": True, "dailyLimit": None, "used": used, "remaining": None}
    limit = max(FREE_DAILY, len(ids))
    return {"isSubscriber": False, "dailyLimit": limit, "used": used, "remaining": max(0, limit - used)}


def _ensure_set(user_id: int, sub: bool) -> list[int]:
    """오늘 세트. 처음 여는 순간 정하고 그날은 바꾸지 않는다(첫날 3문제는 끝까지 보여 준다)."""
    d = _today()
    ids = dao.daily_set(g.db, user_id, d)
    if ids is None:
        ids = dao.pick_new(g.db, user_id, SUB_MAX_LEVEL if sub else FREE_MAX_LEVEL, FREE_DAILY, [])
        if ids:
            dao.save_daily_set(g.db, user_id, d, ids)
            g.db.commit()
    return ids


def _extend_set(user_id: int, ids: list[int]) -> int | None:
    """구독자: 세트를 다 풀면 한 문제를 더 붙인다."""
    more = dao.pick_new(g.db, user_id, SUB_MAX_LEVEL, 1, ids)
    if not more:
        return None
    dao.save_daily_set(g.db, user_id, _today(), ids + more)
    return more[0]


def _can_open(user_id: int, qid: int, q: dict, sub: bool, today_ids: list[int]):
    """(허용 여부, 오류 응답). 오늘 세트의 문제는 언제나 연다. 그 밖은 구독자가 전에 받은 문제(다시 풀기)만."""
    if not q["public"]:
        return False, _err("NOT_FOUND", "문제를 찾을 수 없어요.", 404)
    if qid in today_ids:
        return True, None
    if not sub:
        return False, _err("SUBSCRIPTION_REQUIRED", "구독하면 지난 문제를 다시 풀 수 있어요.", 403)
    if q["level"] > SUB_MAX_LEVEL or not dao.ever_in_sets(g.db, user_id, qid):
        return False, _err("NOT_FOUND", "문제를 찾을 수 없어요.", 404)
    return True, None


def _not_ready():
    return _err("NOT_READY", "트레이닝 문제를 준비하고 있어요.", 503)


# ── 오늘 ────────────────────────────────────────────────────────────────
@training_chart_bp.route("/training/today", methods=['GET'])
@require_auth
def get_today():
    uid = g.current_user_id
    try:
        if not dao.has_tables(g.db):
            return ApiResponse.success({"ready": False, "setDate": str(_today()), "questions": [],
                                        "quota": {"isSubscriber": False, "dailyLimit": FREE_DAILY, "used": 0, "remaining": FREE_DAILY},
                                        "streakDays": 0, "totalScore": 0})
        sub = _is_subscriber(uid)
        ids = _ensure_set(uid, sub)
        done = dao.attempted_ids(g.db, uid, ids)
        todo = [i for i in ids if i not in done]
        if sub and not todo:
            nxt = _extend_set(uid, ids)
            g.db.commit()
            if nxt:
                ids = ids + [nxt]
                todo = [nxt]
        questions = []
        for qid in todo:
            q = dao.question(g.db, qid)
            if q and q["public"]:
                questions.append(_question_payload(q))
        return ApiResponse.success({
            "ready": True,
            "setDate": str(_today()),
            "quota": _quota(uid, sub, ids),
            "streakDays": _streak_days(uid),
            "totalScore": dao.total_score(g.db, uid),
            "questions": questions,
        })
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("오늘의 문제를 불러오지 못했어요.")


# ── 힌트 ────────────────────────────────────────────────────────────────
@training_chart_bp.route("/training/<int:qid>/hint", methods=['POST'])
@require_auth
def post_hint(qid: int):
    uid = g.current_user_id
    try:
        if not dao.has_tables(g.db):
            return _not_ready()
        q = dao.question(g.db, qid)
        if q is None:
            return _err("NOT_FOUND", "문제를 찾을 수 없어요.", 404)
        sub = _is_subscriber(uid)
        ok, resp = _can_open(uid, qid, q, sub, dao.daily_set(g.db, uid, _today()) or [])
        if not ok:
            return resp
        if dao.attempt(g.db, uid, qid) is None:   # 이미 푼 문제(다시 풀기)는 점수와 무관하니 기록하지 않는다
            dao.mark_hint(g.db, uid, qid)
            g.db.commit()
        return ApiResponse.success({"hint": q["hint"], "scoreMultiplier": HINT_MULTIPLIER})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("힌트를 불러오지 못했어요.")


# ── 답 ──────────────────────────────────────────────────────────────────
@training_chart_bp.route("/training/<int:qid>/answer", methods=['POST'])
@require_auth
def post_answer(qid: int):
    uid = g.current_user_id
    body = request.get_json(silent=True) or {}
    answer = body.get('answer')
    if answer not in ANSWERS:
        return ApiResponse.error("answer 는 UP · FLAT · DOWN 중 하나여야 합니다.", status=400)
    try:
        if not dao.has_tables(g.db):
            return _not_ready()
        q = dao.question(g.db, qid)
        if q is None:
            return _err("NOT_FOUND", "문제를 찾을 수 없어요.", 404)
        sub = _is_subscriber(uid)
        today_ids = dao.daily_set(g.db, uid, _today()) or []
        ok, resp = _can_open(uid, qid, q, sub, today_ids)
        if not ok:
            return resp

        out = q["outcome"]
        is_match = answer == out["direction"]
        prev = dao.attempt(g.db, uid, qid)
        retry = prev is not None
        used_hint = bool(body.get('usedHint')) or dao.hint_used(g.db, uid, qid)
        streak = 0
        attempt_id = prev.id if prev else None
        score = 0
        if not retry:
            # 연속 일치(이번 것 포함). 점수 보너스용 — 출석 연속일(streakDays)과는 다르다.
            if is_match:
                streak = 1
                for m in dao.recent_matches(g.db, uid, 10):
                    if not m:
                        break
                    streak += 1
            score = score_of(is_match, used_hint, streak)
            n, attempt_id = dao.insert_attempt(g.db, uid, qid, answer, used_hint, is_match, score)
            if n == 0:   # 동시에 두 번 눌린 경우 — 먼저 들어간 기록이 있다
                retry, score = True, 0
                prev = dao.attempt(g.db, uid, qid)
                attempt_id = prev.id if prev else None

        # 같은 방향을 봤으면 꿀(처음 풀 때만, 하루 honey.CHART_QUIZ_DAILY_MAX 번). 꿀 표가 없거나 실패해도 답 저장은 그대로 성공이다.
        honey_gained = 0
        if is_match and not retry:
            try:
                g.db.execute(text("SAVEPOINT chart_quiz_honey"))
                honey_gained = honey.chart_quiz_credit(g.db, uid, qid)
            except Exception as e:  # noqa: BLE001
                g.db.execute(text("ROLLBACK TO SAVEPOINT chart_quiz_honey"))
                logging.warning(f"[honey] 차트 퀴즈 꿀 지급 실패: {e}")

        next_id = None
        if qid in today_ids:
            done = dao.attempted_ids(g.db, uid, today_ids)
            rest = [i for i in today_ids if i not in done and i != qid]
            next_id = rest[0] if rest else (_extend_set(uid, today_ids) if sub else None)
        g.db.commit()

        st = dao.pattern_stat(g.db, q["pattern_id"], STAT_WINDOW)
        snap = q["snapshot"]
        return ApiResponse.success({
            "attemptId": attempt_id,
            "isMatch": is_match,
            "score": score,
            "honeyGained": honey_gained,
            "usedHint": used_hint,
            "matchStreak": streak,
            "retry": retry,
            "outcome": {"returnRate": out["ret"], "maxDrawdown": out["maxDrawdown"], "maxGain": out["maxGain"]},
            "futureCandles": snap.get("futureCandles", []),
            "futureIndicators": snap.get("futureIndicators"),
            "explanation": q["explanation"],
            "pattern": {
                "patternId": q["pattern_id"],
                "name": q["pattern_name"],
                "stat": {"windowMonths": STAT_WINDOW,
                         "occurrences": int(st.occurrences) if st else 0,
                         "upCount": int(st.up_count) if st else 0,
                         "downCount": int(st.down_count) if st else 0,
                         "flatCount": int(st.flat_count) if st else 0},
                "caseListLocked": not sub,
                "casePreview": None if sub else FREE_CASE_PREVIEW,
            },
            "nextQuestionId": next_id,
            "quota": _quota(uid, sub, dao.daily_set(g.db, uid, _today()) or today_ids),
            "totalScore": dao.total_score(g.db, uid),
            "streakDays": _streak_days(uid),
        })
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("답을 저장하지 못했어요.")


# ── 다시 풀기(구독) ─────────────────────────────────────────────────────
@training_chart_bp.route("/training/history", methods=['GET'])
@require_auth
def get_history():
    uid = g.current_user_id
    try:
        if not dao.has_tables(g.db):
            return _not_ready()
        if not _is_subscriber(uid):
            return _err("SUBSCRIPTION_REQUIRED", "구독하면 지난 문제를 다시 풀 수 있어요.", 403)
        only_mismatch = request.args.get('all') != '1'
        rows = dao.history(g.db, uid, only_mismatch)
        return ApiResponse.success([{
            "questionId": r.question_id, "level": int(r.level), "patternName": r.pattern_name,
            "answer": r.answer, "isMatch": bool(r.is_match), "score": int(r.score),
            "answeredAt": int(r.answered_at.replace(tzinfo=honey.KST).timestamp() * 1000),
        } for r in rows])
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("기록을 불러오지 못했어요.")


@training_chart_bp.route("/training/questions/<int:qid>", methods=['GET'])
@require_auth
def get_question(qid: int):
    uid = g.current_user_id
    try:
        if not dao.has_tables(g.db):
            return _not_ready()
        q = dao.question(g.db, qid)
        if q is None:
            return _err("NOT_FOUND", "문제를 찾을 수 없어요.", 404)
        sub = _is_subscriber(uid)
        ok, resp = _can_open(uid, qid, q, sub, dao.daily_set(g.db, uid, _today()) or [])
        if not ok:
            return resp
        return ApiResponse.success(_question_payload(q))
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("문제를 불러오지 못했어요.")
