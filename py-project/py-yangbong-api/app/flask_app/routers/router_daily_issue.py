"""
오늘의 경제 이슈 — sql/yangbong/014·015 · app/services/daily_issue_service.py. 2026-11-22.

  GET  /api/v1/daily-issue              공개된 최근 이슈 + 지난 이슈 제목(비로그인 허용)
  GET  /api/v1/daily-issue/<ymd>        공개된 그날 이슈
  GET  /api/v1/daily-issue/review       검토 메일의 [승인]/[반려] 링크 → 확인 화면(HTML, 아직 바꾸지 않음)
  POST /api/v1/daily-issue/review       확인 화면의 버튼 → 승인(공개) / 반려(이유는 선택 → 새 초안을 만들어 메일 다시)
  검토 링크는 서명(sig)·만료(exp)로 지킨다. 로그인은 필요 없다. 예전 메일의 [보류](hold)는 반려로 본다.
"""
import logging
import re
from html import escape

from flask import Blueprint, Response, g, request

from web_shared.http.response import ApiResponse
from app.services import daily_issue_service as svc

daily_issue_bp = Blueprint('daily_issue', __name__)

_ACTION_LABEL = {'publish': '승인', 'reject': '반려'}


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


def _reason_box(left: int) -> str:
    """반려 확인 화면: 이유(선택) 입력 + 남은 횟수 안내."""
    note = (f"반려하면 1분 안에 새 글을 만들어 메일을 다시 보내드려요. 오늘 {left}번 더 만들 수 있어요." if left
            else "오늘은 더 만들 수 없어요(하루 한도). 반려하면 오늘 이슈는 비어요.")
    return (
        '<label for="reason" style="display:block;font-size:14px;font-weight:700;color:#4E5968">반려 이유 '
        '<span style="font-weight:400;color:#8B95A1">(선택 · 새 글에 반영돼요)</span></label>'
        '<textarea id="reason" name="reason" maxlength="300" rows="3" placeholder="예) 너무 어려워요 / 다른 이슈로 / 숫자를 더 쉽게" '
        'style="box-sizing:border-box;width:100%;margin:6px 0 4px;padding:10px 12px;border:1.5px solid #ECEBE6;'
        'border-radius:10px;font:inherit;font-size:15px"></textarea>'
        f'<p style="margin:0 0 16px;font-size:13px;color:#8B95A1">{note}</p>')


@daily_issue_bp.route('/daily-issue/review', methods=['GET', 'POST'])
def review():
    ymd, sig_action, exp, sig = _args()
    if not svc.verify(ymd, sig_action, exp, sig):
        return _page('링크 오류', "<h2>링크가 맞지 않거나 기간이 지났어요</h2><p>다음 검토 메일의 버튼을 눌러 주세요.</p>", 403)
    action = 'reject' if sig_action == 'hold' else sig_action   # 서명은 메일에 적힌 이름 그대로 확인하고, 동작은 새 이름으로
    row = svc.get(g.db, ymd, any_status=True)
    if row is None:
        return _page('없음', "<h2>없는 이슈예요</h2>", 404)
    label = _ACTION_LABEL[action]
    e = escape
    if request.method == 'GET':
        # 메일 프로그램이 링크를 미리 열어도 바뀌지 않게, 여기서는 확인만 묻는다.
        color = '#5A3C08' if action == 'publish' else '#4E5968'
        extra = '' if action == 'publish' else _reason_box(svc.attempts_left(g.db, ymd))
        button = '승인하고 앱에 공개하기' if action == 'publish' else '반려하고 새 글 받기'
        return _page(f'{label} 확인', f"""
<h2 style="margin:8px 0 4px;font-size:20px">{e(row['title'])}</h2>
<p style="margin:0 0 20px;color:#4E5968">지금 상태: <b>{e(_status_text(row['status']))}</b></p>
<form method="post" style="margin:0">
  <input type="hidden" name="ymd" value="{e(ymd)}"><input type="hidden" name="action" value="{e(sig_action)}">
  <input type="hidden" name="exp" value="{e(exp)}"><input type="hidden" name="sig" value="{e(sig)}">
  {extra}
  <button type="submit" style="width:100%;height:52px;border:0;border-radius:12px;background:{color};color:#fff;font-size:16px;font-weight:700">{button}</button>
</form>""")
    try:
        row = svc.apply_review(g.db, ymd, action, request.form.get('reason', ''))
    except svc.DailyIssueError as ex:
        return _page('처리 불가', f"<h2>{e(str(ex))}</h2>", 409)
    except Exception as ex:  # noqa: BLE001
        g.db.rollback()
        logging.error(f"[daily-issue/review] {ymd} {action}: {ex}")
        return _page('오류', "<h2>처리하지 못했어요. 잠시 후 다시 눌러 주세요.</h2>", 500)
    if action == 'publish':
        done = '승인했어요. 앱 홈에 바로 보여요.'
    elif svc.attempts_left(g.db, ymd):
        done = '반려했어요. 앱에는 보이지 않아요. 1분 안에 새 글을 만들어 메일로 다시 보내드릴게요.'
    else:
        done = '반려했어요. 오늘은 더 만들 수 없어서(하루 한도) 오늘 이슈는 비어요.'
    return _page(f'{label} 완료', f"<h2 style='margin:8px 0 4px;font-size:20px'>{e(row['title'])}</h2><p>{done}</p>")


def _status_text(st: str) -> str:
    return {'DRAFT': '검토 전', 'PUBLISHED': '공개 중', 'HELD': '보류', 'REJECTED': '반려(새 글 만드는 중)',
            'FAILED': '만들기 실패', 'MAKING': '만드는 중'}.get(st, st)
