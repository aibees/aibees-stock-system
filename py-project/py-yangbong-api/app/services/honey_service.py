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
    return {"got": got, "bonus": bonus, "streak": days}


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
