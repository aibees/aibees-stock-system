"""
router_account.py — 계정 삭제(회원 탈퇴). **양봉상회 전용**. 앱스토어 심사 필수 항목(앱 안에서 계정 삭제).

    DELETE /api/oauth/account   (Authorization 필요) — 로그인한 본인 계정과 연결 데이터를 지운다.

- user_id 는 JWT 에서만 읽는다(require_auth → g.current_user_id).
- 관리자(user_id=1)는 지울 수 없다(403).
- 자식 테이블부터 지우고 user_master 는 마지막. user_id 열이 실제로 있는 테이블만 지운다.
- 접속 기록(user_login_log, user_menu_access_log)과 AI 생성 횟수(stock_ai_gen_log)는 개인 식별 정보가 없고
  법정 보관·남용 방지 목적이라 남긴다(개인정보 처리방침의 '관계 법령 보존' 범위).
- AI 작업(stock_ai_job.created_by)은 다른 사람도 구독하는 공용 결과라 지우지 않는다.
"""
import logging

from flask import Blueprint, g
from sqlalchemy import text

from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse

account_bp = Blueprint("account", __name__)

_ACCOUNT_DELETE_TABLES = (
    'user_notification', 'stock_ai_job_subscriber',
    'device_push_token', 'user_refresh_token', 'user_interest_stocks', 'user_interest_groups',
    'user_persona', 'user_options', 'user_option_reco', 'user_consent', 'user_role', 'user_auth',
    'user_login_type', 'user_detail', 'user_master',
)


@account_bp.route("/account", methods=['DELETE'])
@require_auth
def delete_account():
    user_id = g.current_user_id
    if user_id == 1:
        return ApiResponse.error("관리자 계정은 삭제할 수 없습니다.", status=403)

    try:
        rows = g.db.execute(text(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND column_name = 'user_id'"
        )).fetchall()
        present = {str(r[0]).lower() for r in rows}
        deleted = {}
        for table in _ACCOUNT_DELETE_TABLES:
            if table in present:
                result = g.db.execute(text(f"DELETE FROM `{table}` WHERE user_id = :uid"), {"uid": user_id})
                deleted[table] = result.rowcount
        g.db.commit()
        logging.warning(f"[account] 계정 삭제 user_id={user_id} rows={deleted}")
        return ApiResponse.success(None)
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error("계정 삭제에 실패했습니다. 잠시 후 다시 시도해 주세요.")
