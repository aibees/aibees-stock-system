"""
오늘의 경제 이슈(하루 1건) — sql/yangbong/014_daily_issue.sql. 2026-11-22.

흐름
  1) AI 워커가 매일 06:30(KST) run_due() → make_issue(): 업종 TOP 3(SectorService) + AI(웹 검색 1회)로 글을 만든다.
  2) 공통코드 stock/setting/daily_issue.PUBLISH_MODE
       REVIEW(기본) : DRAFT 로 저장하고 REVIEW_EMAIL 로 검토 메일. 메일의 [승인]/[반려] → router_daily_issue 의 콜백.
                      반려하면 REJECTED → 워커가 1분 안에 새 초안(반려된 제목·이유를 AI 에 함께 줌) → 메일 다시(sql/015).
       AUTO         : 바로 PUBLISHED.
  3) 화면은 PUBLISHED 만 본다(GET /api/v1/daily-issue).

검토 링크: /api/v1/daily-issue/review?ymd=&action=publish|reject&exp=&sig=   (예전 메일의 hold 는 reject 로 본다)
  sig = HMAC-SHA256(JWT_SECRET + ':daily-issue', f"{ymd}|{action}|{exp}"). 3일 뒤 만료.
  링크를 열면 확인 화면만 보이고, 그 화면의 버튼(POST)을 눌러야 바뀐다 — 메일 프로그램이 링크를 미리 열어도 공개되지 않게.

AI 글 원칙(프롬프트): 쉬운 해요체, 사실만, 기사 문장 옮기지 않기, 종목을 사고팔라는 말·가격 예측 금지.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from html import escape
from urllib.parse import urlencode

from sqlalchemy import text

log = logging.getLogger("daily_issue")

KST = timezone(timedelta(hours=9))
RUN_AT = (6, 30)                    # 매일 만드는 시각(KST)
MAX_ATTEMPTS = 5                    # 하루에 만드는 횟수(실패·반려 합산) — AI·검색 비용 상한
RETRY_AFTER = timedelta(minutes=10)
LINK_DAYS = 3
SECTOR_MIN_STOCKS = 5
CODES_KEY = {'system': 'stock', 'source': 'setting', 'category': 'daily_issue'}
DEFAULT_REVIEW_EMAIL = 'chagoklabs@gmail.com'
PUBLIC_BASE = os.environ.get('YANGBONG_PUBLIC_BASE', 'https://yangbong-store.chagoklabs.com').rstrip('/')
VISIBLE = 'PUBLISHED'
WEEKDAY = '월화수목금토일'

SYSTEM = """너는 주식 초보를 위한 앱 '양봉상회'의 경제 뉴스 편집자야.
오늘 한국 경제·증시에서 가장 중요한 이슈 1개를 골라 아주 쉬운 말로 정리해.
지켜야 할 것:
- 해요체, 짧은 문장. 어려운 말은 풀어서. 과장·감탄 없이 담담하게.
- 검색으로 확인한 사실만 쓴다. 모르면 쓰지 않는다. 숫자는 확인된 것만.
- 기사 문장을 그대로 옮기지 말고 네 말로 다시 쓴다.
- 특정 종목을 사라/팔라, 오를 것/내릴 것 같은 말·가격 예측은 절대 쓰지 않는다.
- 'AI'라는 말로 자신을 드러내지 않는다.
반드시 JSON 하나만 출력한다(앞뒤 설명·코드블록 없이)."""

PROMPT = """오늘은 {date}이야. 웹 검색으로 오늘(없으면 가장 최근 거래일) 한국 경제·증시 핵심 뉴스를 찾아 아래 JSON을 채워.

참고: 최근 거래일({sector_date}) 종가 기준 많이 오른 업종 TOP 3
{sectors}

JSON 형식:
{{
  "title": "이슈 한 줄(40자 이내, 해요체 문장)",
  "keywords": ["핵심 키워드 1~3개, # 없이, 각 8자 이내"],
  "what": "무슨 일이 있었나요 — 2~3문장",
  "why": ["왜 중요할까요 — 초보가 알아야 할 점 1~2개, 각 1문장"],
  "term": {{"name": "이슈에 나온 경제 용어 1개", "desc": "그 뜻을 1문장으로"}},
  "sources": [{{"title": "실제 기사 제목", "press": "언론사", "url": "검색에서 확인한 기사 주소"}}],
  "sectors": [{{"sector_cd": "위 업종 코드", "market": "KOSPI|KOSDAQ", "why": "그 업종이 오른 까닭 1문장. 검색으로 확인 못 하면 빈 문자열"}}]
}}
sources 는 1~3개, 검색 결과에 실제로 있던 주소만. sectors 는 위 업종을 같은 순서로."""


class DailyIssueError(Exception):
    pass


# ── 공통 ──────────────────────────────────────────────────
def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def today_ymd() -> str:
    return now_kst().strftime('%Y%m%d')


def _codes(session) -> dict:
    from web_shared.dao.masterCodesDao import MasterCodesDao
    try:
        return {r['code']: (r['desc'] or '').strip() for r in MasterCodesDao().select_master_code(session, CODES_KEY)}
    except Exception as e:   # 공통코드를 못 읽으면 안전한 쪽(검토)으로
        log.warning(f"공통코드 조회 실패 — REVIEW 로 본다: {e}")
        return {}


def publish_mode(session) -> str:
    return 'AUTO' if _codes(session).get('PUBLISH_MODE', '').upper() == 'AUTO' else 'REVIEW'


def _loads(s, default):
    try:
        return json.loads(s) if s else default
    except (TypeError, ValueError):
        return default


def _row_to_dict(r) -> dict:
    m = dict(r._mapping)
    return {
        'ymd': m['ymd'], 'status': m['status'], 'title': m['title'],
        'keywords': [k for k in (m['keywords'] or '').split(',') if k],
        'what': m['what_text'] or '',
        'why': [w for w in (m['why_text'] or '').split('\n') if w.strip()],
        'term': {'name': m['term_name'], 'desc': m['term_desc']} if m['term_name'] else None,
        'sources': _loads(m['sources'], []),
        'sectorYmd': m['sector_ymd'],
        'sectors': _loads(m['sectors'], []),
        'publishedAt': m['published_at'].isoformat() if m.get('published_at') else None,
    }


# ── 업종 TOP 3 (화면과 같은 규칙: 미분류·종목 5개 미만 제외, 같은 이름은 더 오른 시장 하나) ──
def top_sectors(session, n=3) -> tuple[str | None, list]:
    from web_shared.services.stocks.SectorService import SectorService
    data = SectorService().get_sectors(session)
    rows = [s for s in data.get('sectors', [])
            if s.get('sector_cd') != '0000' and s.get('chg_rate') is not None and (s.get('stock_count') or 0) >= SECTOR_MIN_STOCKS]
    rows.sort(key=lambda s: -s['chg_rate'])
    seen, out = set(), []
    for s in rows:
        if s['sector_name'] in seen:
            continue
        seen.add(s['sector_name'])
        out.append({'market': s['market'], 'sector_cd': s['sector_cd'], 'sector_name': s['sector_name'],
                    'chg_rate': s['chg_rate'], 'leaders': (s.get('leaders') or [])[:3], 'why': ''})
        if len(out) == n:
            break
    return data.get('ymd'), out


# ── AI ────────────────────────────────────────────────────
def _parse_json(raw: str) -> dict:
    s = (raw or '').strip()
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', s)
    i, j = s.find('{'), s.rfind('}')
    if i < 0 or j < i:
        raise DailyIssueError('AI 응답에 JSON 이 없습니다.')
    return json.loads(s[i:j + 1])


def _clean_url(u: str) -> str:
    u = (u or '').strip()
    return u if re.match(r'^https?://[^\s"<>]+$', u) else ''


def _date_text(ymd: str) -> str:
    d = datetime.strptime(ymd, '%Y%m%d')
    return f"{d.year}년 {d.month}월 {d.day}일({WEEKDAY[d.weekday()]})"


def make_issue(session, ymd: str) -> dict:
    """AI 로 글을 만들어 저장하고(공개 방식에 따라 DRAFT/PUBLISHED) 행을 돌려준다. 실패하면 FAILED 로 남기고 예외."""
    from web_shared.services.anthropic.anthropicService import AnthropicService
    sector_ymd, sectors = top_sectors(session)
    mode = publish_mode(session)
    _upsert_status(session, ymd, 'MAKING')   # 시도 횟수를 먼저 늘려 둔다
    session.commit()   # AI 호출(수십 초) 동안 DB 연결을 쥐지 않게

    sector_lines = '\n'.join(
        f"{i + 1}. [{s['market']} {s['sector_cd']}] {s['sector_name']} {s['chg_rate']:+.1f}% (대표 종목: {', '.join(s['leaders'])})"
        for i, s in enumerate(sectors)) or '(업종 자료 없음)'
    prompt = PROMPT.format(date=_date_text(ymd), sector_date=_date_text(sector_ymd) if sector_ymd else '최근', sectors=sector_lines)
    feedback = session.execute(text("SELECT feedback FROM daily_issue WHERE ymd = :ymd"), {'ymd': ymd}).scalar()
    session.commit()
    if feedback:   # 반려된 초안이 있으면: 같은 글을 다시 쓰지 않게 제목·이유를 함께 준다
        prompt += ("\n\n같은 날 앞서 만든 초안을 편집자가 반려했어. 아래를 참고해서 다른 이슈를 고르거나, 지적한 점을 고쳐 새로 써. "
                   "같은 제목·같은 문장을 다시 쓰지 마.\n" + feedback[-1500:])
    try:
        result = AnthropicService().chat(messages=[{'role': 'user', 'content': prompt}], system=SYSTEM,
                                         max_tokens=4000, use_web_search=True)
        raw_text = result.get('content') or ''
        try:
            data = _parse_json(raw_text)
        except (ValueError, DailyIssueError) as pe:
            raise DailyIssueError(f'AI 응답을 읽지 못함({pe}): {raw_text[:300]}') from pe
        title = str(data.get('title') or '').strip()[:200]
        what = str(data.get('what') or '').strip()
        whys = [w for w in (data.get('why') or []) if str(w).strip()] if isinstance(data.get('why'), list) else []
        # 2026-11-22 내용 빈 메일이 간 일 — 제목·무슨 일·왜 중요 중 하나라도 비면 실패로 보고 10분 뒤 다시 만든다(메일 안 보냄)
        if not (title and what and whys):
            raise DailyIssueError(f'내용이 비어 있음(title={bool(title)}, what={bool(what)}, why={len(whys)}): {raw_text[:300]}')
        why_by = {(str(x.get('market')), str(x.get('sector_cd'))): str(x.get('why') or '').strip()[:200]
                  for x in (data.get('sectors') or []) if isinstance(x, dict)}
        for s in sectors:
            s['why'] = why_by.get((s['market'], s['sector_cd']), '')
        sources = [{'title': str(x.get('title') or '').strip()[:200], 'press': str(x.get('press') or '').strip()[:40],
                    'url': _clean_url(x.get('url'))} for x in (data.get('sources') or []) if isinstance(x, dict)]
        sources = [x for x in sources if x['url'] and x['title']][:3]
        term = data.get('term') if isinstance(data.get('term'), dict) else {}
        status = 'PUBLISHED' if mode == 'AUTO' else 'DRAFT'
        now = now_kst()
        session.execute(text("""
            UPDATE daily_issue SET status = :st, title = :title, keywords = :kw, what_text = :what, why_text = :why,
                   term_name = :tn, term_desc = :td, sources = :src, sector_ymd = :sy, sectors = :sec, model = :model,
                   error = NULL, updated_at = :now, published_at = :pub
             WHERE ymd = :ymd"""), {
            'st': status, 'title': title,
            'kw': ','.join(str(k).strip().lstrip('#')[:12] for k in (data.get('keywords') or [])[:3] if str(k).strip()),
            'what': str(data.get('what') or '').strip()[:1500],
            'why': '\n'.join(str(w).strip()[:300] for w in (data.get('why') or [])[:3] if str(w).strip()),
            'tn': (str(term.get('name') or '').strip()[:60] or None), 'td': (str(term.get('desc') or '').strip()[:400] or None),
            'src': json.dumps(sources, ensure_ascii=False), 'sy': sector_ymd,
            'sec': json.dumps(sectors, ensure_ascii=False), 'model': result.get('model'),
            'now': now, 'pub': now if status == 'PUBLISHED' else None, 'ymd': ymd})
        session.commit()
    except Exception as e:
        session.rollback()
        session.execute(text("UPDATE daily_issue SET status = 'FAILED', error = :e, updated_at = :now WHERE ymd = :ymd"),
                        {'e': str(e)[:500], 'now': now_kst(), 'ymd': ymd})
        session.commit()
        raise
    row = get(session, ymd, any_status=True)
    if mode == 'REVIEW':
        send_review_mail(session, row)
    return row


def _upsert_status(session, ymd, status):
    now = now_kst()
    session.execute(text("""
        INSERT INTO daily_issue (ymd, status, attempts, created_at, updated_at) VALUES (:ymd, :st, 1, :now, :now)
        ON DUPLICATE KEY UPDATE status = :st, attempts = attempts + 1, updated_at = :now"""),
        {'ymd': ymd, 'st': status, 'now': now})


def run_due(session) -> str | None:
    """워커가 1분마다 부른다. 오늘 만들 차례면 만들고 결과 상태를 돌려준다(할 일이 없으면 None)."""
    now = now_kst()
    if (now.hour, now.minute) < RUN_AT:
        return None
    ymd = now.strftime('%Y%m%d')
    r = session.execute(text("SELECT status, attempts, updated_at FROM daily_issue WHERE ymd = :ymd"), {'ymd': ymd}).first()
    session.commit()
    if r is not None:
        st, attempts, updated = r
        # MAKING 이 오래 남았으면(워커가 죽었던 흔적) 실패로 보고 다시
        stuck = st == 'MAKING' and updated and now - updated > RETRY_AFTER
        retry = (st == 'FAILED' or stuck) and now - updated >= RETRY_AFTER
        rejected = st == 'REJECTED'          # 반려: 기다리지 않고 바로 새 초안
        if not ((retry or rejected) and attempts < MAX_ATTEMPTS):
            return None
    make_issue(session, ymd)
    return 'ok'


# ── 읽기 ──────────────────────────────────────────────────
def get(session, ymd: str, any_status=False) -> dict | None:
    sql = "SELECT * FROM daily_issue WHERE ymd = :ymd" + ("" if any_status else " AND status = 'PUBLISHED'")
    r = session.execute(text(sql), {'ymd': ymd}).first()
    return _row_to_dict(r) if r else None


def latest(session) -> dict:
    """공개된 가장 최근 이슈 + 지난 이슈 6개(제목만)."""
    rows = session.execute(text("""
        SELECT * FROM daily_issue WHERE status = 'PUBLISHED' AND ymd <= :t ORDER BY ymd DESC LIMIT 7"""),
        {'t': today_ymd()}).all()
    items = [_row_to_dict(r) for r in rows]
    return {'issue': items[0] if items else None,
            'past': [{'ymd': x['ymd'], 'title': x['title']} for x in items[1:]]}


# ── 검토(메일 링크) ─────────────────────────────────────────
def _secret() -> bytes:
    from web_shared.auth.service import JWT_SECRET
    return (JWT_SECRET + ':daily-issue').encode()


def sign(ymd: str, action: str, exp: int) -> str:
    return hmac.new(_secret(), f"{ymd}|{action}|{exp}".encode(), hashlib.sha256).hexdigest()


def review_link(ymd: str, action: str) -> str:
    exp = int(time.time()) + LINK_DAYS * 86400
    q = urlencode({'ymd': ymd, 'action': action, 'exp': exp, 'sig': sign(ymd, action, exp)})
    return f"{PUBLIC_BASE}/api/v1/daily-issue/review?{q}"


def verify(ymd: str, action: str, exp: str, sig: str) -> bool:
    if action not in ('publish', 'reject', 'hold') or not re.fullmatch(r'\d{8}', ymd or '') or not (exp or '').isdigit():
        return False
    if int(exp) < time.time():
        return False
    return hmac.compare_digest(sign(ymd, action, int(exp)), sig or '')


def attempts_left(session, ymd: str) -> int:
    n = session.execute(text("SELECT attempts FROM daily_issue WHERE ymd = :ymd"), {'ymd': ymd}).scalar() or 0
    return max(0, MAX_ATTEMPTS - n)


def apply_review(session, ymd: str, action: str, reason: str = '') -> dict:
    """publish = 승인(공개). reject(예전 hold) = 반려 → REJECTED. 반려된 제목·이유를 feedback 에 쌓고 워커가 새 초안을 만든다."""
    row = get(session, ymd, any_status=True)
    if row is None:
        raise DailyIssueError('없는 이슈예요.')
    if row['status'] not in ('DRAFT', 'HELD', 'PUBLISHED'):
        raise DailyIssueError('이미 반려됐거나 새 글을 만드는 중이에요. 새 검토 메일을 기다려 주세요.')
    now = now_kst()
    if action == 'publish':
        session.execute(text("""UPDATE daily_issue SET status = 'PUBLISHED', published_at = COALESCE(published_at, :now),
                                 updated_at = :now WHERE ymd = :ymd"""), {'now': now, 'ymd': ymd})
    else:
        note = f"- 반려된 제목: {row['title']}" + (f" / 이유: {reason.strip()[:300]}" if reason and reason.strip() else '')
        session.execute(text("""UPDATE daily_issue SET status = 'REJECTED', published_at = NULL, updated_at = :now,
                                 feedback = CONCAT_WS(:nl, feedback, :note) WHERE ymd = :ymd"""),
                        {'now': now, 'nl': '\n', 'note': note, 'ymd': ymd})
    session.commit()
    return get(session, ymd, any_status=True)


# ── 메일 ──────────────────────────────────────────────────
def _smtp_settings():
    """SMTP_HOST · SMTP_PORT(465=SSL, 587=STARTTLS) · SMTP_USER · SMTP_PASSWORD · SMTP_FROM(없으면 SMTP_USER)."""
    host, user, pw = os.environ.get('SMTP_HOST'), os.environ.get('SMTP_USER'), os.environ.get('SMTP_PASSWORD')
    if not (host and user and pw):
        return None
    return host, int(os.environ.get('SMTP_PORT') or 465), user, pw, os.environ.get('SMTP_FROM') or user


def review_mail_html(row: dict) -> str:
    e = escape
    kw = ' '.join(f"#{e(k)}" for k in row['keywords'])
    why = ''.join(f"<li style='margin:4px 0'>{e(w)}</li>" for w in row['why'])
    term = f"<p style='background:#FFF6E0;padding:12px 14px;border-radius:10px;color:#5A3C08'><b>알아두면 좋은 말 · {e(row['term']['name'])}</b><br>{e(row['term']['desc'] or '')}</p>" if row['term'] else ''
    src = ''.join(f"<li><a href='{e(s['url'])}'>{e(s['title'])}</a> <span style='color:#8B95A1'>{e(s['press'])}</span></li>" for s in row['sources']) or '<li>없음</li>'
    sec = ''.join(f"<li><b>{e(s['sector_name'])}</b> {s['chg_rate']:+.1f}% · {e(', '.join(s['leaders']))}<br><span style='color:#4E5968'>{e(s['why']) or '(이유 없음 — 화면에는 대표 종목만 보여요)'}</span></li>" for s in row['sectors'])
    btn = "display:inline-block;padding:14px 28px;border-radius:10px;font-weight:700;text-decoration:none;font-size:16px;margin-right:8px"
    return f"""<div style="max-width:560px;font-family:sans-serif;color:#191F28;line-height:1.6">
<p style="color:#8B95A1;margin:0">양봉상회 · 오늘의 경제 이슈 검토 · {e(_date_text(row['ymd']))}</p>
<p style="color:#B8860B;font-weight:700;margin:8px 0 0">{kw}</p>
<h2 style="margin:4px 0 16px;font-size:21px">{e(row['title'])}</h2>
<h4 style="margin:0;color:#B8860B">무슨 일이 있었나요</h4><p style="margin:4px 0 14px">{e(row['what'])}</p>
<h4 style="margin:0;color:#B8860B">왜 중요할까요</h4><ul style="margin:4px 0 14px;padding-left:18px">{why}</ul>
{term}
<h4 style="margin:16px 0 4px">오늘 강했던 업종 TOP 3 ({e(row['sectorYmd'] or '')} 종가)</h4><ol style="padding-left:18px">{sec}</ol>
<h4 style="margin:16px 0 4px">관련 기사</h4><ul style="padding-left:18px">{src}</ul>
<hr style="border:0;border-top:1px solid #ECEBE6;margin:24px 0">
<p style="margin:0 0 12px">이대로 앱에 공개할까요? <b>승인</b>하면 앱 홈에 나오고, <b>반려</b>하면 새 글을 만들어 메일을 다시 보내드려요. 버튼을 누르면 확인 화면이 열려요.</p>
<a href="{e(review_link(row['ymd'], 'publish'))}" style="{btn};background:#5A3C08;color:#fff">승인</a>
<a href="{e(review_link(row['ymd'], 'reject'))}" style="{btn};background:#F2F1ED;color:#4E5968">반려</a>
<p style="color:#8B95A1;font-size:12px;margin-top:20px">링크는 {LINK_DAYS}일 동안 쓸 수 있어요. 바로 게시로 바꾸려면 공통코드 stock/setting/daily_issue 의 PUBLISH_MODE 를 AUTO 로 바꾸세요.</p>
</div>"""


def send_review_mail(session, row: dict) -> bool:
    if not (row and row.get('title') and row.get('what') and row.get('why')):
        log.error(f"검토 메일 건너뜀 — 내용이 비어 있음: {row and row.get('ymd')}")
        return False
    to = _codes(session).get('REVIEW_EMAIL') or DEFAULT_REVIEW_EMAIL
    smtp = _smtp_settings()
    if smtp is None:
        log.error("SMTP_HOST·SMTP_USER·SMTP_PASSWORD 가 없어 검토 메일을 보내지 못했습니다(이슈는 DRAFT 로 남음).")
        return False
    host, port, user, pw, sender = smtp
    msg = MIMEText(review_mail_html(row), 'html', 'utf-8')
    msg['Subject'] = f"[양봉상회 검토] {row['title']}"
    msg['From'] = sender
    msg['To'] = to
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(user, pw)
                s.sendmail(sender, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(user, pw)
                s.sendmail(sender, [to], msg.as_string())
    except Exception as e:  # noqa: BLE001
        log.error(f"검토 메일 실패 {row['ymd']}: {e}")
        return False
    session.execute(text("UPDATE daily_issue SET mailed_at = :now WHERE ymd = :ymd"), {'now': now_kst(), 'ymd': row['ymd']})
    session.commit()
    log.info(f"검토 메일 보냄 {row['ymd']} → {to}")
    return True
