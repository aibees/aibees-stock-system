"""
router_notice.py — 공지사항 조회(읽기 전용, sql/48_notice.sql)

    GET /api/v1/notices?page=&size=  : 목록(최신순, 본문 제외). NoticeList.vue, Home.vue(최근 3건)
    GET /api/v1/notices/<notice_id>  : 상세(본문 포함). NoticeDetail.vue

공개 정보라 업종 조회(/stocks/sectors)처럼 로그인 없이 응답한다.
"""
import logging

from flask import Blueprint, request, g

from app.domains.dao.noticeDao import NoticeDao
from app.flask_app.utils.apiResponse import ApiResponse


noticeDaoImpl = NoticeDao()

notice_bp = Blueprint("notice", __name__)

MAX_PAGE_SIZE = 50


@notice_bp.route("", methods=['GET'])
def select_notice_list():
    """GET /api/v1/notices?page=0&size=20"""
    try:
        page = max(int(request.args.get('page', 0) or 0), 0)
        size = int(request.args.get('size', 20) or 20)
    except (TypeError, ValueError):
        return ApiResponse.error("page / size 파라미터는 숫자여야 합니다.", status=400)
    size = min(size if size > 0 else 20, MAX_PAGE_SIZE)

    try:
        items, total = noticeDaoImpl.select_notice_page(g.db, page, size)
    except Exception as e:
        logging.error(f"[notices] {e}")
        return ApiResponse.error("공지사항을 불러오지 못했습니다.", status=500)

    total_pages = (total + size - 1) // size
    return ApiResponse.success(items, extra={
        'totalPages': total_pages, 'totalElements': total, 'page': page, 'size': size,
    })


@notice_bp.route("/<int:notice_id>", methods=['GET'])
def select_notice_detail(notice_id):
    """GET /api/v1/notices/<notice_id>"""
    try:
        item = noticeDaoImpl.select_notice(g.db, notice_id)
    except Exception as e:
        logging.error(f"[notices] {notice_id}: {e}")
        return ApiResponse.error("공지사항을 불러오지 못했습니다.", status=500)
    if item is None:
        return ApiResponse.error("공지사항을 찾을 수 없습니다.", status=404)
    return ApiResponse.success(item)
