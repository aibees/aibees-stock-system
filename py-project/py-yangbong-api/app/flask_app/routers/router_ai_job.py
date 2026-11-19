"""
AI 분석 생성 작업 — 양봉상회 전용 (url_prefix = /api/v1/anthropic/stock-analysis)
설계: meetings/설계_2026-11-18_AI분석-비동기화.md · sql/yangbong/008

  POST /<overview|theme>/jobs?stock_code=  body {force?}  → 202 {job_id, status, queue_position, joined, …}
       거절: 실적발표월 아님 400 · 쿨다운/하루 한도 429
  GET  /jobs?stock_code=                                   → 이 종목에서 내가 기다리는 작업(섹션별 최근 1건)
  GET  /jobs/<job_id>                                      → 작업 상태(화면 폴링용)

생성 자체는 AI 워커(app.workers.ai_job_worker)가 한다. 이 API 는 요청을 쌓기만 한다.
오류 응답에 KIS·Anthropic 원문을 넣지 않는다(원문은 stock_ai_job.error_detail·서버 로그).
"""
import logging

from flask import Blueprint, Response, g, request

from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse, _dumps
from app.services.anthropic.aiJobService import USER_SECTIONS, AiJobService
from web_shared.services.anthropic.stockAiContentService import (
    AnnouncementMonthRequiredError,
    GenerationQuotaError,
    RefreshCooldownError,
)
from stock_shared.dao.masterStockDao import MasterStockDao

logger = logging.getLogger(__name__)

ai_job_bp = Blueprint("ai_job", __name__)
aiJobServiceImpl = AiJobService()
masterStockDaoImpl = MasterStockDao()

ADMIN_USER_ID = 1


def _accepted(data) -> Response:
    """202 Accepted — 접수됐고 결과는 나중에(작업 폴링·알림)."""
    return Response(_dumps({'success': True, 'data': data}, use_decimal=True),
                    status=202, content_type='application/json; charset=utf-8')


def _stock_code_or_error():
    stock_code = request.args.get("stock_code", "").strip()
    if not stock_code:
        return None, ApiResponse.error("stock_code 파라미터가 필요합니다.")
    if not masterStockDaoImpl.select_master_stock_by_id(g.db, {"stock_code": stock_code}):
        return None, ApiResponse.error("없는 종목코드입니다.", status=400)
    return stock_code, None


def request_job(section: str, stock_code: str):
    """POST /<section>/jobs 와 옛 POST /<section>(양봉 모드) 가 같이 쓴다."""
    body = request.get_json(silent=True) or {}
    is_admin = (g.current_user_id == ADMIN_USER_ID)
    force = is_admin and bool(body.get("force"))
    try:
        return _accepted(aiJobServiceImpl.request(g.db, stock_code, section, g.current_user_id, is_admin, force))
    except AnnouncementMonthRequiredError as e:
        return ApiResponse.error(str(e))
    except (RefreshCooldownError, GenerationQuotaError) as e:
        return ApiResponse.error(str(e), status=429)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ai-job] {stock_code}/{section} 접수 실패: {e}", exc_info=True)
        return ApiResponse.error("AI 분석 요청을 받지 못했어요. 잠시 후 다시 시도해 주세요.", status=500)


@ai_job_bp.route("/<section>/jobs", methods=["POST"])
@require_auth
def create_job(section):
    if section not in USER_SECTIONS:
        return ApiResponse.error("요청할 수 없는 항목입니다.", status=404)
    stock_code, err = _stock_code_or_error()
    if err:
        return err
    return request_job(section, stock_code)


@ai_job_bp.route("/jobs", methods=["GET"])
@require_auth
def my_jobs():
    stock_code = request.args.get("stock_code", "").strip()
    if not stock_code:
        return ApiResponse.error("stock_code 파라미터가 필요합니다.")
    try:
        return ApiResponse.success(aiJobServiceImpl.my_jobs(g.db, g.current_user_id, stock_code))
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ai-job] my_jobs {stock_code}: {e}", exc_info=True)
        return ApiResponse.error("요청 상태를 불러오지 못했어요.", status=500)


@ai_job_bp.route("/jobs/<int:job_id>", methods=["GET"])
@require_auth
def get_job(job_id):
    try:
        job = aiJobServiceImpl.get_job(g.db, job_id)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ai-job] get_job {job_id}: {e}", exc_info=True)
        return ApiResponse.error("요청 상태를 불러오지 못했어요.", status=500)
    if not job:
        return ApiResponse.error("없는 요청입니다.", status=404)
    return ApiResponse.success(job)
