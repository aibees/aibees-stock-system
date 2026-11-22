"""
꿀(포인트) 1단계 — 규칙과 지급·사용. **양봉상회 전용**(2026-11-22). 기획: yangbong-store-vue/docs/points-plan.md

원칙: 활동으로만 모으고 돈으로 팔지 않는다. 모은 꿀은 1년 뒤 사라진다. 지급은 서버만 한다.
표: yangbong.honey_ledger · honey_pass (sql/yangbong/012). 표가 없으면 호출부가 오류로 처리한다.

같은 보상을 두 번 주지 않는 장치는 honey_ledger 의 UNIQUE(user_id, kind, ref) 다(INSERT IGNORE).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

KST = timezone(timedelta(hours=9))

# ── 규칙(수치는 운영하며 바꾼다. 화면 honey-store.js 의 표시 문구와 함께 바꾼다) ──
ATTEND = 10                    # 하루 첫 방문
STREAK_DAYS = 7
STREAK_BONUS = 50              # 7일 연속 출석한 날
START = 100                    # 처음 시작하기(질문 3개 → 종목 담기) 1번
LESSON = 20                    # 트레이닝 단계 1개(단계당 1번)
QUIZ = 10                      # 오늘의 한 문제 정답(하루 1번)
CHART_QUIZ = 5                 # 차트 퀴즈에서 같은 방향을 봤을 때(문제당 1번, 처음 풀 때만)
CHART_QUIZ_DAILY_MAX = 3       # 하루에 차트 퀴즈 꿀을 받는 횟수(구독자가 문제를 끝없이 풀어 꿀을 찍어 내지 못하게)
AD_REWARDS = (20, 30, 40)      # 광고 1·2·3번째, 그 뒤로는 AD_AFTER
AD_AFTER = 30
AD_DAILY_MAX = 10
DAY_PASS_COST = 1000           # 프리미엄 하루 이용권(24시간)
DAY_PASS_HOURS = 24
EXPIRE_DAYS = 365
DAILY_TARGET = 360             # 화면의 '오늘 N / 360꿀' 분모(광고 300 + 출석·문제·수업 하나쯤)

# 트레이닝 단계 key(yangbong-store-vue src/scripts/data/trainingToc.json). 목차를 바꾸면 여기도 고친다.
# 목록에 없는 key 로는 꿀을 주지 않는다(임의 key 로 꿀을 찍어 내지 못하게).
LESSON_KEYS = frozenset([
    'chart-basic/candle', 'chart-basic/bull-bear', 'chart-basic/volume', 'chart-basic/ma', 'chart-basic/sr', 'chart-basic/check',
    'chart-advanced/trendline', 'chart-advanced/price-volume', 'chart-advanced/bb', 'chart-advanced/atr',
    'chart-advanced/macd-obv', 'chart-advanced/pullback', 'chart-advanced/check',
    'chart-deep/wave', 'chart-deep/box', 'chart-deep/multi-tf', 'chart-deep/wrong', 'chart-deep/backtest', 'chart-deep/check',
    'company-analysis/business', 'company-analysis/income', 'company-analysis/debt', 'company-analysis/valuation',
    'company-analysis/disclosure', 'company-analysis/check',
    'supply-demand/basics', 'supply-demand/players', 'supply-demand/net-buying', 'supply-demand/with-price',
    'supply-demand/trap', 'supply-demand/check',
    'risk-management/why-loss', 'risk-management/position-size', 'risk-management/exit-price',
    'risk-management/split-buy', 'risk-management/journal', 'risk-management/check',
])

DAY_PASS_FEATURE = 'RECO_ADVANCED'   # 하루 이용권이 여는 기능(프리미엄 단계, RecoLevel.ADVANCED_FEATURE)


class HoneyError(Exception):
    """화면에 그대로 보여 줄 수 있는 이유(잔액 부족 등)."""


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None, microsecond=0)


def ymd_of(dt: datetime) -> str:
    return dt.strftime('%Y%m%d')


def ad_reward(count_before: int) -> int:
    """오늘 이미 본 광고 수 → 이번 광고 보상."""
    return AD_REWARDS[count_before] if count_before < len(AD_REWARDS) else AD_AFTER


# ── 쓰기 ──────────────────────────────────────────────
def credit(session, user_id: int, kind: str, ref: str, amount: int) -> int:
    """꿀을 넣는다. 이미 같은 (kind, ref) 로 받았으면 0 을 돌려준다. 커밋은 호출부가 한다."""
    now = now_kst()
    result = session.execute(text(
        "INSERT IGNORE INTO honey_ledger (user_id, amount, kind, ref, ymd, remaining, expires_at, created_at) "
        "VALUES (:uid, :amt, :kind, :ref, :ymd, :amt, :exp, :now)"
    ), {"uid": user_id, "amt": amount, "kind": kind, "ref": str(ref)[:80], "ymd": ymd_of(now),
        "exp": now + timedelta(days=EXPIRE_DAYS), "now": now})
    return amount if result.rowcount == 1 else 0


def balance(session, user_id: int) -> int:
    row = session.execute(text(
        "SELECT COALESCE(SUM(remaining), 0) FROM honey_ledger "
        "WHERE user_id = :uid AND amount > 0 AND remaining > 0 AND expires_at > :now"
    ), {"uid": user_id, "now": now_kst()}).first()
    return int(row[0] or 0)


def spend(session, user_id: int, kind: str, amount: int) -> None:
    """꿀을 쓴다. 만료가 빠른 꿀부터 줄인다. 모자라면 HoneyError. 커밋은 호출부가 한다."""
    now = now_kst()
    rows = session.execute(text(
        "SELECT id, remaining FROM honey_ledger "
        "WHERE user_id = :uid AND amount > 0 AND remaining > 0 AND expires_at > :now "
        "ORDER BY expires_at, id FOR UPDATE"
    ), {"uid": user_id, "now": now}).fetchall()
    if sum(int(r[1]) for r in rows) < amount:
        raise HoneyError("꿀이 부족해요.")
    left = amount
    for rid, remaining in rows:
        if left <= 0:
            break
        take = min(int(remaining), left)
        session.execute(text("UPDATE honey_ledger SET remaining = remaining - :t WHERE id = :id"), {"t": take, "id": rid})
        left -= take
    session.execute(text(
        "INSERT INTO honey_ledger (user_id, amount, kind, ref, ymd, remaining, expires_at, created_at) "
        "VALUES (:uid, :amt, :kind, :ref, :ymd, 0, NULL, :now)"
    ), {"uid": user_id, "amt": -amount, "kind": kind, "ref": str(int(now.timestamp() * 1000)), "ymd": ymd_of(now), "now": now})


def attend(session, user_id: int) -> dict:
    """오늘 출석. 7일 연속이 되는 날엔 보너스도 함께. {got, streak, bonus}"""
    today = ymd_of(now_kst())
    got = credit(session, user_id, 'ATTEND', today, ATTEND)
    days = streak_days(session, user_id)
    bonus = 0
    if got and days > 0 and days % STREAK_DAYS == 0:
        bonus = credit(session, user_id, 'STREAK', today, STREAK_BONUS)
    invite_gain = 0
    if got:
        try:
            r = check_invite(session, user_id)   # 초대받은 사람이면 3일 출석 확인(표가 없으면 넘어간다)
            invite_gain = (r or {}).get("gained", 0)
        except Exception:
            invite_gain = 0
    return {"got": got, "bonus": bonus + invite_gain, "streak": days}


def watch_ad(session, user_id: int, transaction_id: str) -> int:
    """광고 시청 완료(AdMob 서버 측 확인을 통과한 뒤에만 부른다). 하루 한도를 넘으면 0."""
    count = ad_count_today(session, user_id)
    if count >= AD_DAILY_MAX:
        return 0
    return credit(session, user_id, 'AD', transaction_id, ad_reward(count))


def buy_day_pass(session, user_id: int) -> datetime:
    """프리미엄 하루 이용권. 이미 쓰는 중이면 남은 시간 뒤로 24시간을 더한다."""
    spend(session, user_id, 'SPEND_DAY_PASS', DAY_PASS_COST)
    now = now_kst()
    current = active_pass_until(session, user_id)
    until = (current if current and current > now else now) + timedelta(hours=DAY_PASS_HOURS)
    session.execute(text(
        "INSERT INTO honey_pass (user_id, kind, expires_at, created_at) VALUES (:uid, 'DAY', :until, :now) "
        "ON DUPLICATE KEY UPDATE expires_at = VALUES(expires_at)"
    ), {"uid": user_id, "until": until, "now": now})
    return until


# ── 읽기 ──────────────────────────────────────────────
def chart_quiz_credit(session, user_id: int, question_id: int) -> int:
    """차트 퀴즈 일치 꿀. 같은 문제는 1번, 하루 CHART_QUIZ_DAILY_MAX 번까지. 받은 양(0 이면 못 받음). 커밋은 호출부."""
    n = session.execute(text(
        "SELECT COUNT(*) FROM honey_ledger WHERE user_id = :uid AND kind = 'CHART_QUIZ' AND ymd = :ymd"
    ), {"uid": user_id, "ymd": ymd_of(now_kst())}).first()[0]
    if int(n or 0) >= CHART_QUIZ_DAILY_MAX:
        return 0
    return credit(session, user_id, 'CHART_QUIZ', str(int(question_id)), CHART_QUIZ)


def ad_count_today(session, user_id: int) -> int:
    row = session.execute(text(
        "SELECT COUNT(*) FROM honey_ledger WHERE user_id = :uid AND kind = 'AD' AND ymd = :ymd"
    ), {"uid": user_id, "ymd": ymd_of(now_kst())}).first()
    return int(row[0] or 0)


def streak_days(session, user_id: int) -> int:
    """오늘(또는 어제)까지 이어진 연속 출석 일수. 오늘 아직 안 왔으면 어제까지를 센다."""
    rows = session.execute(text(
        "SELECT ref FROM honey_ledger WHERE user_id = :uid AND kind = 'ATTEND' ORDER BY ref DESC LIMIT 400"
    ), {"uid": user_id}).fetchall()
    days = {r[0] for r in rows}
    cur = now_kst().date()
    if cur.strftime('%Y%m%d') not in days:
        cur -= timedelta(days=1)
    n = 0
    while cur.strftime('%Y%m%d') in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def active_pass_until(session, user_id: int):
    row = session.execute(text(
        "SELECT expires_at FROM honey_pass WHERE user_id = :uid AND kind = 'DAY' AND expires_at > :now"
    ), {"uid": user_id, "now": now_kst()}).first()
    return row[0] if row else None


def summary(session, user_id: int) -> dict:
    """꿀 화면이 쓰는 요약: 잔액, 오늘 모은 양, 할 일 상태, 연속 출석, 이용권."""
    now = now_kst()
    today = ymd_of(now)
    rows = session.execute(text(
        "SELECT kind, ref, amount FROM honey_ledger WHERE user_id = :uid AND ymd = :ymd"
    ), {"uid": user_id, "ymd": today}).fetchall()
    earned = sum(int(r[2]) for r in rows if int(r[2]) > 0)
    kinds = {r[0] for r in rows}
    ad_count = sum(1 for r in rows if r[0] == 'AD')
    start_done = session.execute(text(
        "SELECT 1 FROM honey_ledger WHERE user_id = :uid AND kind = 'START' LIMIT 1"), {"uid": user_id}).first() is not None
    lessons_done = session.execute(text(
        "SELECT COUNT(*) FROM honey_ledger WHERE user_id = :uid AND kind = 'LESSON'"), {"uid": user_id}).first()[0]
    expiring = session.execute(text(
        "SELECT COALESCE(SUM(remaining), 0) FROM honey_ledger WHERE user_id = :uid AND amount > 0 AND remaining > 0 "
        "AND expires_at > :now AND expires_at <= :soon"), {"uid": user_id, "now": now, "soon": now + timedelta(days=30)}).first()[0]
    until = active_pass_until(session, user_id)
    streak = streak_days(session, user_id)
    return {
        "balance": balance(session, user_id),
        "expiringSoon": int(expiring or 0),
        "today": {"earned": earned, "target": DAILY_TARGET},
        "attend": {"done": 'ATTEND' in kinds, "amount": ATTEND},
        "streak": {"days": streak, "goal": STREAK_DAYS, "bonus": STREAK_BONUS},
        "quiz": {"done": 'QUIZ' in kinds, "amount": QUIZ},
        "ad": {"count": ad_count, "max": AD_DAILY_MAX,
               "next": ad_reward(ad_count) if ad_count < AD_DAILY_MAX else 0},
        "lesson": {"done": int(lessons_done or 0), "total": len(LESSON_KEYS), "amount": LESSON},
        "start": {"done": start_done, "amount": START},
        "dayPass": {"cost": DAY_PASS_COST, "until": int(until.replace(tzinfo=KST).timestamp() * 1000) if until else None},
    }


def ledger(session, user_id: int, limit: int = 50, before_id: int = None) -> list:
    params = {"uid": user_id, "lim": max(1, min(limit, 100))}
    cond = ""
    if before_id:
        cond = "AND id < :bid"
        params["bid"] = before_id
    rows = session.execute(text(
        f"SELECT id, amount, kind, ref, created_at FROM honey_ledger WHERE user_id = :uid {cond} ORDER BY id DESC LIMIT :lim"
    ), params).fetchall()
    return [{"id": r[0], "amount": int(r[1]), "kind": r[2], "ref": r[3],
             "at": int(r[4].replace(tzinfo=KST).timestamp() * 1000)} for r in rows]


def extra_features(session, user_id) -> list:
    """프리미엄 하루 이용권을 쓰는 중이면 RECO_ADVANCED 를 더한다(web_shared.auth.features 에 등록)."""
    if user_id is None:
        return []
    try:
        return [DAY_PASS_FEATURE] if active_pass_until(session, user_id) else []
    except Exception:
        return []   # 표가 아직 없을 때(sql/012 적용 전)


# ══════════════ 2단계: 친구 초대 (sql/yangbong/013) ══════════════
import secrets

INVITER_REWARD = 300
INVITEE_REWARD = 100
INVITE_DAYS = 3            # 코드를 넣은 뒤 서로 다른 날 출석 수
INVITER_MONTHLY_MAX = 10   # 초대한 사람이 한 달에 꿀을 받는 인원
INVITE_SIGNUP_DAYS = 14    # 가입하고 이 기간 안에만 코드를 넣을 수 있다
_CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # 헷갈리는 0·O·1·I 제외


def invite_code(session, user_id: int) -> str:
    """내 초대 코드. 없으면 만든다(커밋은 호출부)."""
    row = session.execute(text("SELECT code FROM honey_invite_code WHERE user_id = :uid"), {"uid": user_id}).first()
    if row:
        return row[0]
    for _ in range(8):
        code = ''.join(secrets.choice(_CODE_CHARS) for _ in range(8))
        result = session.execute(text(
            "INSERT IGNORE INTO honey_invite_code (user_id, code, created_at) VALUES (:uid, :code, :now)"
        ), {"uid": user_id, "code": code, "now": now_kst()})
        if result.rowcount == 1:
            return code
        row = session.execute(text("SELECT code FROM honey_invite_code WHERE user_id = :uid"), {"uid": user_id}).first()
        if row:
            return row[0]
    raise HoneyError("초대 코드를 만들지 못했어요. 잠시 후 다시 해 주세요.")


def _signup_at(session, user_id: int):
    """가입 시각 — 가입 때 만들어지는 권한 행(user_auth)의 가장 이른 생성일. 모르면 None."""
    try:
        row = session.execute(text("SELECT MIN(created_date) FROM user_auth WHERE user_id = :uid"), {"uid": user_id}).first()
        return row[0] if row else None
    except Exception:
        return None


def _invite_days(session, invitee_id: int, since) -> int:
    row = session.execute(text(
        "SELECT COUNT(DISTINCT ref) FROM honey_ledger WHERE user_id = :uid AND kind = 'ATTEND' AND created_at >= :since"
    ), {"uid": invitee_id, "since": since.replace(hour=0, minute=0, second=0)}).first()
    return int(row[0] or 0)


def redeem_invite(session, invitee_id: int, code: str, device_id: str = None) -> dict:
    """친구 코드 넣기. 조건이 맞지 않으면 HoneyError(화면에 그대로 보인다). 커밋은 호출부."""
    code = (code or '').strip().upper()
    if not code or len(code) > 12:
        raise HoneyError("초대 코드를 확인해 주세요.")
    if session.execute(text("SELECT 1 FROM honey_invite WHERE invitee_id = :uid"), {"uid": invitee_id}).first():
        raise HoneyError("이미 초대 코드를 등록했어요.")
    owner = session.execute(text("SELECT user_id FROM honey_invite_code WHERE code = :c"), {"c": code}).first()
    if not owner:
        raise HoneyError("없는 초대 코드예요.")
    inviter_id = int(owner[0])
    if inviter_id == invitee_id:
        raise HoneyError("내 초대 코드는 넣을 수 없어요.")
    signup = _signup_at(session, invitee_id)
    if signup and now_kst() - signup > timedelta(days=INVITE_SIGNUP_DAYS):
        raise HoneyError(f"초대 코드는 가입하고 {INVITE_SIGNUP_DAYS}일 안에만 넣을 수 있어요.")
    device = (device_id or '')[:64] or None
    if device and session.execute(text("SELECT 1 FROM honey_invite WHERE device_id = :d"), {"d": device}).first():
        raise HoneyError("이 기기에서는 이미 초대 코드를 등록했어요.")
    now = now_kst()
    session.execute(text(
        "INSERT INTO honey_invite (invitee_id, user_id, inviter_id, code, device_id, redeemed_at) "
        "VALUES (:uid, :uid, :inv, :code, :dev, :now)"
    ), {"uid": invitee_id, "inv": inviter_id, "code": code, "dev": device, "now": now})
    return check_invite(session, invitee_id)


def check_invite(session, invitee_id: int) -> dict:
    """초대받은 사람이 3일 출석을 채웠으면 양쪽에 꿀을 준다(출석할 때마다 부른다). {days, goal, completed, gained}"""
    row = session.execute(text(
        "SELECT inviter_id, redeemed_at, completed_at FROM honey_invite WHERE invitee_id = :uid FOR UPDATE"
    ), {"uid": invitee_id}).first()
    if not row:
        return None
    inviter_id, redeemed_at, completed_at = int(row[0]), row[1], row[2]
    days = _invite_days(session, invitee_id, redeemed_at)
    if completed_at or days < INVITE_DAYS:
        return {"days": min(days, INVITE_DAYS), "goal": INVITE_DAYS, "completed": bool(completed_at), "gained": 0}
    now = now_kst()
    session.execute(text("UPDATE honey_invite SET completed_at = :now WHERE invitee_id = :uid"), {"now": now, "uid": invitee_id})
    gained = credit(session, invitee_id, 'INVITED', 'invited', INVITEE_REWARD)
    # 초대한 사람: 이번 달 완료 인원이 한도 안이면 꿀
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    done = session.execute(text(
        "SELECT COUNT(*) FROM honey_ledger WHERE user_id = :inv AND kind = 'INVITE' AND created_at >= :ms"
    ), {"inv": inviter_id, "ms": month_start}).first()[0]
    if int(done or 0) < INVITER_MONTHLY_MAX:
        credit(session, inviter_id, 'INVITE', str(invitee_id), INVITER_REWARD)
    return {"days": INVITE_DAYS, "goal": INVITE_DAYS, "completed": True, "gained": gained}


def invite_summary(session, user_id: int) -> dict:
    code = invite_code(session, user_id)
    now = now_kst()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    completed = session.execute(text(
        "SELECT COUNT(*) FROM honey_invite WHERE inviter_id = :uid AND completed_at IS NOT NULL"), {"uid": user_id}).first()[0]
    pending = session.execute(text(
        "SELECT COUNT(*) FROM honey_invite WHERE inviter_id = :uid AND completed_at IS NULL"), {"uid": user_id}).first()[0]
    month = session.execute(text(
        "SELECT COUNT(*) FROM honey_ledger WHERE user_id = :uid AND kind = 'INVITE' AND created_at >= :ms"
    ), {"uid": user_id, "ms": month_start}).first()[0]
    mine = None
    row = session.execute(text("SELECT code, redeemed_at, completed_at FROM honey_invite WHERE invitee_id = :uid"), {"uid": user_id}).first()
    if row:
        mine = {"code": row[0], "days": min(_invite_days(session, user_id, row[1]), INVITE_DAYS), "goal": INVITE_DAYS,
                "completed": row[2] is not None}
    signup = _signup_at(session, user_id)
    can_redeem = mine is None and (not signup or now - signup <= timedelta(days=INVITE_SIGNUP_DAYS))
    return {
        "code": code,
        "reward": {"inviter": INVITER_REWARD, "invitee": INVITEE_REWARD, "days": INVITE_DAYS},
        "completed": int(completed or 0), "pending": int(pending or 0),
        "monthLeft": max(0, INVITER_MONTHLY_MAX - int(month or 0)), "monthMax": INVITER_MONTHLY_MAX,
        "mine": mine, "canRedeem": can_redeem,
    }
