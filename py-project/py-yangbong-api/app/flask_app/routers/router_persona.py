"""
router_persona.py — 성향 테스트 결과(계정 저장). **양봉상회 전용**(2026-11-19 router_user_options 에서 분리).

    GET /api/v1/user-options/persona   {persona_type, updated_at(epoch ms)} 또는 null(저장한 적 없음)
    PUT /api/v1/user-options/persona   body {persona_type} — 모든 로그인 사용자

표 user_persona 는 `yangbong` 스키마에만 있다(sql/yangbong/002_service_tables.sql).
"""
import logging
import re

from flask import Blueprint, g, request

from stock_shared.dao.userPersonaDao import UserPersonaDao
from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse

persona_bp = Blueprint("persona", __name__)
userPersonaDaoImpl = UserPersonaDao()


# ===============================================================================
# 3. 성향 테스트 결과 (계정 저장) — 양봉상회 전용(sql/yangbong/002_service_tables.sql)
#    GET /api/v1/user-options/persona · PUT /api/v1/user-options/persona
#    화면(persona-store.js)이 로그인할 때 기기 값과 비교해 더 최근 쪽으로 맞춘다.
# ===============================================================================
# 유형 key 목록은 데이터(personaConfig.json / 공통코드 PERSONA_CONFIG)라 여기서는 형식만 본다.
_PERSONA_TYPE_RE = re.compile(r'^[a-z][a-z0-9_]{0,29}$')


@persona_bp.route("/user-options/persona", methods=['GET'])
@require_auth
def get_user_persona():
    try:
        return ApiResponse.success(userPersonaDaoImpl.select_by_user_id(g.db, g.current_user_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e)[:255])


@persona_bp.route("/user-options/persona", methods=['PUT'])
@require_auth
def put_user_persona():
    body = request.get_json(silent=True) or {}

    fields = {}
    if 'persona_type' in body:
        pt = body.get('persona_type')
        if not isinstance(pt, str) or not _PERSONA_TYPE_RE.match(pt):
            return ApiResponse.error("persona_type 형식이 올바르지 않습니다.", status=400)
        fields['persona_type'] = pt
    if not fields:
        return ApiResponse.error("변경할 항목이 없습니다.", status=400)

    try:
        userPersonaDaoImpl.upsert(g.db, g.current_user_id, fields)
        g.db.commit()
        return ApiResponse.success(userPersonaDaoImpl.select_by_user_id(g.db, g.current_user_id))
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e)[:255])
