"""
오늘의 경제 이슈 — sql/yangbong/014 · app/services/daily_issue_service.py. 2026-11-22.

  GET  /api/v1/daily-issue              공개된 최근 이슈 + 지난 이슈 제목(비로그인 허용)
  GET  /api/v1/daily-issue/<ymd>        공개된 그날 이슈
  GET  /api/v1/daily-issue/review       검토 메일의 [확인]/[보류] 링크 → 확인 화면(HTML, 아직 바꾸지 않음)
  POST /api/v1/daily-issue/review       확인 화면의 버튼 → 공개/보류 적용(HTML)
  검토 링크는 서명(sig)·만료(exp)로 지킨다. 로그인은 필요 없다.
"""
import logging
import re
from html import escape

from flask import Blueprint, Response, g, request

from web_shared.http.response import ApiResponse
from app.services import daily_issue_service as svc

daily_issue_bp = Blueprint('daily_issue', __name__)

_ACTION_LABEL = {'publish': '공개', 'hold': '보류'}


@daily_issue_bp.route('/daily-issue', methods=['GET'])
def latest_issue():
    try:
        return ApiResponse.success(svc.latest(g.db))
    except Exception as e:  # noqa: BLE001 — 표가 없을 때도 화면은 카드를 숨기면 된다
        logging.error(f"[daily-issue] {e}")
        return ApiResponse.error("오늘의 경제 이슈를 불러오지 못했어요.", 500)


@daily_issue_bp.route('/daily-issue/<ymd>', methods=['GET'])
def issue_of(ymd):
    if not re.fullmatch(r'\d{8}', ymd):
        return ApiResponse.error("날짜 형식이 아니에요.", 400)
    row = svc.get(g.db, ymd)
    return ApiResponse.success(row) if row else ApiResponse.error("공개된 이슈가 없어요.", 404)


def _page(title: str, body: str, status=200) -> Response:
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{escape(title)}</title></head>
<body style="margin:0;background:#F4F3EF;font-family:sans-serif;color:#191F28">
<main style="max-width:480px;margin:40px auto;padding:28px 24px;background:#fff;border-radius:16px;line-height:1.6">
<p style="margin:0;color:#8B95A1;font-size:13px">양봉상회 · 오늘의 경제 이슈 검토</p>{body}</main></body></html>"""
    return Response(html, status=status, mimetype='text/html')


def _args():
    src = request.form if request.method == 'POST' else request.args
    return (src.get('ymd', ''), src.get('action', ''), src.get('exp', ''), src.get('sig', ''))


@daily_issue_bp.route('/daily-issue/review', methods=['GET', 'POST'])
def review():
    ymd, action, exp, sig = _args()
    if not svc.verify(ymd, action, exp, sig):
        return _page('링크 오류', "<h2>링크가 맞지 않거나 기간이 지났어요</h2><p>다음 검토 메일의 버튼을 눌러 주세요.</p>", 403)
    row = svc.get(g.db, ymd, any_status=True)
    if row is None:
        return _page('없음', "<h2>없는 이슈예요</h2>", 404)
    label = _ACTION_LABEL[action]
    e = escape
    if request.method == 'GET':
        # 메일 프로그램이 링크를 미리 열어도 바뀌지 않게, 여기서는 확인만 묻는다.
        color = '#5A3C08' if action == 'publish' else '#4E5968'
        return _page(f'{label} 확인', f"""
<h2 style="margin:8px 0 4px;font-size:20px">{e(row['title'])}</h2>
<p style="margin:0 0 20px;color:#4E5968">지금 상태: <b>{e(_status_text(row['status']))}</b></p>
<form method="post" style="margin:0">
  <input type="hidden" name="ymd" value="{e(ymd)}"><input type="hidden" name="action" value="{e(action)}">
  <input type="hidden" name="exp" value="{e(exp)}"><input type="hidden" name="sig" value="{e(sig)}">
  <button type="submit" style="width:100%;height:52px;border:0;border-radius:12px;background:{color};color:#fff;font-size:16px;font-weight:700">
    {'앱에 공개하기' if action == 'publish' else '보류하기 (앱에 안 보여요)'}</button>
</form>""")
    try:
        row = svc.apply_review(g.db, ymd, action)
    except svc.DailyIssueError as ex:
        return _page('처리 불가', f"<h2>{e(str(ex))}</h2>", 409)
    except Exception as ex:  # noqa: BLE001
        g.db.rollback()
        logging.error(f"[daily-issue/review] {ymd} {action}: {ex}")
        return _page('오류', "<h2>처리하지 못했어요. 잠시 후 다시 눌러 주세요.</h2>", 500)
    done = '공개했어요. 앱 홈에 바로 보여요.' if action == 'publish' else '보류했어요. 앱에는 보이지 않아요. 마음이 바뀌면 메일의 [확인]을 눌러 주세요.'
    return _page(f'{label} 완료', f"<h2 style='margin:8px 0 4px;font-size:20px'>{e(row['title'])}</h2><p>{done}</p>")


def _status_text(st: str) -> str:
    return {'DRAFT': '검토 전', 'PUBLISHED': '공개 중', 'HELD': '보류', 'FAILED': '만들기 실패', 'MAKING': '만드는 중'}.get(st, st)
