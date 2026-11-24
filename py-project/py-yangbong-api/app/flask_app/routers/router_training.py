"""
router_training.py — 트레이닝 학습 기록·주식분석 유의사항 동의(계정 저장). **양봉상회 전용**(2026-11-22).

    GET  /api/v1/training/progress     {done:[{stage_key, done_at(ms)}], stock_notice:{version, agreed_at(ms)}|null}
    POST /api/v1/training/progress     body {stage_keys:[...]} — 마친 단계를 더한다(이미 있는 건 그대로). 응답은 GET 과 같다.
    POST /api/v1/training/stock-notice body {version} — 주식분석 유의사항 동의. 응답은 GET 과 같다.
    GET  /api/v1/training/review       {items:{...}, updated_at(ms)|null} — 다시 보기(오답노트·헷갈린 용어·복습, sql/016)
    PUT  /api/v1/training/review       body {items:{...}} — 화면이 합친 결과를 통째로 저장(256KB 이하)

모두 로그인 필요. 화면(training-store.js · stockNotice.js)이 로그인할 때 기기 기록과 합치고(합집합),
로그인 중에 단계를 마치거나 동의하면 바로 올린다.

학습 기록: yangbong.user_training_progress (sql/yangbong/011). 표가 없으면 빈 목록으로 응답한다.
유의사항 동의: 기존 동의 표(user_consent + user_consent_history)에 consent_type 'STOCK_NOTICE' 로 남긴다.
  로그인 필수 동의(REQUIRED_CONSENTS)가 아니라 로그인 흐름에는 영향이 없다.
"""
import json
import logging
import re
from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy import text

from app.domains.dao.userTrainingDao import UserTrainingDao
from app.services import honey_service as honey
from web_shared.auth.decorators import require_auth
from web_shared.dao.socialLoginDao import SocialLoginDao
from web_shared.http.response import ApiResponse

training_bp = Blueprint("training", __name__)
userTrainingDaoImpl = UserTrainingDao()
socialLoginDaoImpl = SocialLoginDao()

STOCK_NOTICE = 'STOCK_NOTICE'   # user_consent.consent_type
# 단계 key "<장 slug>/<단계 id>". 목차는 화면 데이터라 여기서는 형식만 본다.
_STAGE_KEY_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,38}/[a-z0-9][a-z0-9-]{0,38}$')
_MAX_KEYS = 300


def _progress(user_id: int) -> dict:
    row = socialLoginDaoImpl.select_consent(g.db, user_id, STOCK_NOTICE)
    notice = None
    if row is not None:
        notice = {
            "version": row.version,
            "agreed_at": int(row.agreed_date.timestamp() * 1000) if row.agreed_date else None,
        }
    return {"done": userTrainingDaoImpl.select_done(g.db, user_id), "stock_notice": notice}


@training_bp.route("/training/progress", methods=['GET'])
@require_auth
def get_training_progress():
    try:
        return ApiResponse.success(_progress(g.current_user_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("학습 기록을 불러오지 못했어요.")


@training_bp.route("/training/progress", methods=['POST'])
@require_auth
def add_training_progress():
    body = request.get_json(silent=True) or {}
    keys = body.get('stage_keys')
    if not isinstance(keys, list) or not keys or len(keys) > _MAX_KEYS:
        return ApiResponse.error("stage_keys 가 올바르지 않습니다.", status=400)
    if not all(isinstance(k, str) and _STAGE_KEY_RE.match(k) for k in keys):
        return ApiResponse.error("stage_keys 형식이 올바르지 않습니다.", status=400)

    try:
        uniq = list(dict.fromkeys(keys))
        userTrainingDaoImpl.add_done(g.db, g.current_user_id, uniq)
        g.db.commit()
        # 수업 완료 꿀(단계당 1번, 목록에 있는 단계만). 꿀 표가 없거나 실패해도 학습 기록 저장은 그대로 성공이다.
        gained = 0
        try:
            for k in uniq:
                if k in honey.LESSON_KEYS:
                    gained += honey.credit(g.db, g.current_user_id, 'LESSON', k, honey.LESSON)
            g.db.commit()
        except Exception as e:
            g.db.rollback()
            logging.warning(f"[honey] 수업 꿀 지급 실패: {e}")
        return ApiResponse.success({**_progress(g.current_user_id), "honeyGained": gained})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("학습 기록을 저장하지 못했어요.")


@training_bp.route("/training/stock-notice", methods=['POST'])
@require_auth
def agree_stock_notice():
    body = request.get_json(silent=True) or {}
    version = body.get('version')
    if isinstance(version, bool) or not isinstance(version, int) or not 1 <= version <= 9999:
        return ApiResponse.error("version 이 올바르지 않습니다.", status=400)

    try:
        socialLoginDaoImpl.save_consent(g.db, g.current_user_id, STOCK_NOTICE, str(version))
        g.db.commit()
        return ApiResponse.success(_progress(g.current_user_id))
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("동의를 저장하지 못했어요.")


# ── 다시 보기(2026-11-24, sql/yangbong/016) ────────────────────────────
_REVIEW_MAX_BYTES = 256 * 1024
_REVIEW_KEY_RE = re.compile(r'^[qt]:.{1,120}$')


@training_bp.route("/training/review", methods=['GET'])
@require_auth
def get_training_review():
    try:
        row = g.db.execute(text("SELECT items, updated_at FROM user_training_review WHERE user_id = :u"),
                           {'u': g.current_user_id}).first()
        if row is None:
            return ApiResponse.success({"items": {}, "updated_at": None})
        try:
            items = json.loads(row[0] or '{}')
        except ValueError:
            items = {}
        return ApiResponse.success({"items": items if isinstance(items, dict) else {},
                                    "updated_at": int(row[1].timestamp() * 1000) if row[1] else None})
    except Exception as e:  # noqa: BLE001 — 표가 없으면 빈 값(화면은 기기 기록으로)
        g.db.rollback()
        logging.warning(f"[training/review] {e}")
        return ApiResponse.success({"items": {}, "updated_at": None})


@training_bp.route("/training/review", methods=['PUT'])
@require_auth
def put_training_review():
    body = request.get_json(silent=True) or {}
    items = body.get('items')
    if not isinstance(items, dict) or not all(isinstance(k, str) and _REVIEW_KEY_RE.match(k) and isinstance(v, dict)
                                              for k, v in items.items()):
        return ApiResponse.error("다시 보기 항목 형식이 올바르지 않습니다.", status=400)
    raw = json.dumps(items, ensure_ascii=False, separators=(',', ':'))
    if len(raw.encode('utf-8')) > _REVIEW_MAX_BYTES:
        return ApiResponse.error("다시 보기 항목이 너무 많아요.", status=400)
    try:
        g.db.execute(text("""
            INSERT INTO user_training_review (user_id, items, updated_at) VALUES (:u, :i, :now)
            ON DUPLICATE KEY UPDATE items = :i, updated_at = :now"""),
            {'u': g.current_user_id, 'i': raw, 'now': datetime.now()})
        g.db.commit()
        return ApiResponse.success({"saved": len(items)})
    except Exception as e:  # noqa: BLE001
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("다시 보기 기록을 저장하지 못했어요.")
