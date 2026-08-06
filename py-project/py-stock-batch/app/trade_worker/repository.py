"""
trade_worker DB 접근 계층 (메인 DAO 와 독립, raw SQL).
※ trade_sell_target_stock 와 완전 분리. worker 매수/매도 포지션은 trade_worker_position 사용.

읽기:
  - get_latest_buy_target_ymd / get_buy_targets(ymd) : trade_buy_target_stock (공용 추천)
  - get_holding_positions / get_holding_one          : trade_worker_position status='HOLDING'
  - get_wallet_balance(user_id)                      : user_wallet
쓰기:
  - open_position / update_position_state / close_position : trade_worker_position
  - set_wallet_balance / set_wallet_snapshot / replace_holdings : user_wallet / user_holdings
  - insert_trade_log / insert_worker_log             : trade_log / trade_worker_log
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from pytz import timezone
from sqlalchemy import text

from app.config.contextManager import get_session

log = logging.getLogger("trade_worker.repo")
_KST = timezone("Asia/Seoul")


# ──────────────────────────────────────────────────────────────────
#  매수타겟 정렬 — 유저별 개인화 (user_options.s1_buy_order)
#
#  스펙 문자열: "필드[:방향],필드[:방향],..."
#      예) "score:desc,volume:desc,rank_no:asc"
#          "volume,rate"          ← 방향 생략 시 필드별 기본방향 사용
#  앞의 키가 동률일 때만 다음 키로 tie-break 한다.
#
#  ★ 정렬 항목 추가 방법 = _ORDER_FIELDS 에 한 줄 추가. 그게 전부다.
#    (파서·키생성·검증이 전부 이 dict 를 참조한다)
#
#  SQL ORDER BY 를 쓰지 않는 이유:
#    · score/rank_no/volume 이 nullable 인데 DB 별 NULL 정렬 위치가 갈린다.
#      NULL 은 asc/desc 어느 쪽이든 **항상 후순위** 여야 한다.
#    · rate 는 '12.5%' 형태 varchar 라 애초에 SQL 정렬이 불가능하다.
# ──────────────────────────────────────────────────────────────────
def _num(v):
    """숫자형 추출. 변환 불가/None 이면 None(→ 항상 후순위)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v):
    """'12.5%' · '-3.2%' · 12.5 → float. 변환 불가면 None."""
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    s = str(v).strip().replace("%", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# 필드명 → (값 추출기, 기본 정렬방향)
#   기본방향: "그 필드로 정렬하라"고 했을 때 사람이 기대하는 쪽.
#   score/volume/rate 는 클수록 상위(desc), rank_no 는 작을수록 상위(asc).
_ORDER_FIELDS = {
    "score":   (lambda r: _num(r.get("score")),   "desc"),
    "volume":  (lambda r: _num(r.get("volume")),  "desc"),
    "rate":    (lambda r: _pct(r.get("rate")),    "desc"),
    "rank_no": (lambda r: _num(r.get("rank_no")), "asc"),
    "close":   (lambda r: _num(r.get("close")),   "desc"),
    # ── 추가 예시(컬럼만 SELECT 에 넣으면 즉시 동작) ──
    # "per":   (lambda r: _num(r.get("per")),     "asc"),
    # "roe":   (lambda r: _num(r.get("roe")),     "desc"),
}

# 스펙 미설정(NULL) 시 기본 = 기존 동작 그대로
DEFAULT_BUY_ORDER = "score:desc,rank_no:asc"


def parse_buy_order(spec: str | None) -> list[tuple[str, bool]]:
    """스펙 문자열 → [(필드명, is_desc), ...]. 모르는 필드는 버린다.

    유효한 항목이 하나도 안 남으면 DEFAULT_BUY_ORDER 로 되돌린다.
    (유저가 오타를 내도 매수가 멈추면 안 되므로 예외를 던지지 않는다)
    """
    steps: list[tuple[str, bool]] = []
    for token in (spec or "").split(","):
        token = token.strip()
        if not token:
            continue
        field, _, direction = token.partition(":")
        field = field.strip().lower()
        entry = _ORDER_FIELDS.get(field)
        if entry is None:
            log.warning("[매수정렬] 알 수 없는 필드 무시: %r (허용: %s)",
                        field, ", ".join(_ORDER_FIELDS))
            continue
        direction = (direction.strip().lower() or entry[1])
        steps.append((field, direction == "desc"))

    if not steps:
        if spec:
            log.warning("[매수정렬] 유효 항목 없음(%r) → 기본값 사용", spec)
        return parse_buy_order(DEFAULT_BUY_ORDER) if spec else \
            [(f, d == "desc") for f, d in
             ((t.partition(":")[0], t.partition(":")[2])
              for t in DEFAULT_BUY_ORDER.split(","))]
    return steps


def make_buy_order_key(spec: str | None):
    """스펙에 맞는 sort key 함수를 만들어 반환.

    각 키는 (is_null, value) 2-튜플이다.
      · is_null 0/1 → NULL 행은 정렬 **방향과 무관하게** 항상 뒤로 간다.
        (구현 초기의 float('inf') 방식은 desc 로 뒤집으면 NULL 이 맨 앞으로
         올라오는 함정이 있어 이 방식으로 바꿨다)
      · desc 는 값의 부호를 뒤집어 오름차순 sort 하나로 처리한다.
    마지막에 stock_code 를 넣어 전 키 동률일 때도 순서가 흔들리지 않게 한다
    (DB 가 행 순서를 보장하지 않으므로 없으면 실행마다 1순위가 바뀔 수 있다).
    """
    steps = parse_buy_order(spec)

    def key(row):
        out = []
        for field, is_desc in steps:
            v = _ORDER_FIELDS[field][0](row)
            out.append((1, 0.0) if v is None else (0, -v if is_desc else v))
        return (tuple(out), str(row.get("stock_code") or ""))

    return key


def describe_buy_order(spec: str | None) -> str:
    """로그용 요약 — 실제 적용된 정렬을 남긴다(설정과 다를 수 있으므로)."""
    return ",".join(f"{f}:{'desc' if d else 'asc'}" for f, d in parse_buy_order(spec))


class Repository:
    # ── 읽기 ────────────────────────────────────────────────────────
    def get_latest_buy_target_ymd(self, min_ymd: str | None = None) -> str | None:
        """조회 창 하한(min_ymd) 안에서 가장 최신 매수타겟 ymd.
        오래된(직전 영업일 이전) 추천을 잡지 않도록 하한을 둔다.
        min_ymd 지정: 그 값을 하한으로 사용(보통 broker.prev_trading_day 직전영업일).
        미지정: KST 요일 heuristic fallback(월요일 today-4 / 그 외 today-2).
        (ymd 는 YYYYMMDD 문자열)."""
        if not min_ymd:
            now = datetime.now(_KST)
            lookback = 4 if now.weekday() == 0 else 2   # 0=월
            min_ymd = (now - timedelta(days=lookback)).strftime("%Y%m%d")
        sql = text(
            "SELECT MAX(ymd) AS ymd FROM trade_buy_target_stock WHERE ymd >= :min_ymd"
        )
        with get_session() as s:
            row = s.execute(sql, {"min_ymd": min_ymd}).mappings().first()
        return row["ymd"] if row and row["ymd"] else None

    def get_buy_targets(self, ymd: str, order_spec: str | None = None) -> list[dict]:
        """해당 ymd 추천 전체를 order_spec 순서로 정렬해 반환.

        order_spec: user_options.s1_buy_order (예 "score:desc,volume:desc").
                    None/빈값이면 DEFAULT_BUY_ORDER(= score:desc,rank_no:asc).
                    문법·필드 상세는 파일 상단 _ORDER_FIELDS 주석 참고.

        ※ 정렬 결과의 **1순위가 곧 매수 종목**이다(BuyExecutor 는 위에서부터
          체결 가능한 첫 종목을 산다. 프리마켓 라운드는 아예 targets[0] 만 본다).
          그래서 적용된 정렬을 로그로 남긴다.

        nxt_flag(master_stock): 'Y'=NXT 대상(통합 라우팅), 그 외=KRX 전용.
        """
        sql = text(
            "SELECT t.ymd, t.stock_code, t.stock_name, t.rate, t.close, "
            "       t.volume, t.score, t.rank_no, ms.nxt_flag "
            "FROM trade_buy_target_stock t "
            "LEFT JOIN master_stock ms ON ms.stock_code = t.stock_code "
            "WHERE t.ymd = :ymd"
        )
        with get_session() as s:
            rows = [dict(r) for r in s.execute(sql, {"ymd": ymd}).mappings().all()]
        rows.sort(key=make_buy_order_key(order_spec))
        return rows

    # ── worker 전용 포지션 테이블(trade_worker_position) ─────────────
    #   trade_sell_target_stock 와 무관. worker 가 직접 매수한 HOLDING 만 다룬다.
    def get_holding_positions(self, user_id: int, exclude_exclusive: bool = False) -> list[dict]:
        """HOLDING 포지션 목록.

        exclude_exclusive=True 는 **매수 1포지션 카운트 전용**이다.
        exclusive_flag='Y' 는 "이 종목은 보유 중이어도 신규 매수를 막지 않는다"는 뜻일 뿐,
        손절/익절 감시 대상에서 빼겠다는 뜻이 아니다.
        매도 감시(sell_executor)와 부팅 대조(_reconcile_positions)는 반드시 기본값(False)으로
        전량을 봐야 한다. 여기서 걸러버리면 그 종목은 실시간 라인 감시가 꺼져
        손절선 없이 방치되고, 부팅 시 수량 보정·외부청산 정리도 되지 않는다.
        """
        sql = text(
            "SELECT p.position_id, "
            "       p.user_id, "
            "       p.stock_code, "
            "       p.stock_name, "
            "       p.entry_ymd, "
            "       p.entry_price, "
            "       p.entry_atr, "
            "       p.qty AS hold_qty, "
            "       p.bars_held, "
            "       p.peak_close, "
            "       p.peak_high, "
            "       p.bars_since_peak,     "
            "       p.last_check_ymd, "
            "       p.stop_price, "
            "       p.target_price, "
            "       p.trail_line, "
            "       p.action_type,        "
            "       ms.nxt_flag           "
            "  FROM trade_worker_position p"
            "  LEFT JOIN master_stock ms ON ms.stock_code = p.stock_code"
            " WHERE p.user_id = :uid      "
            "   AND p.status = 'HOLDING'  "
            + ("   AND COALESCE(p.exclusive_flag, 'N') != 'Y'" if exclude_exclusive else "")
        )
        with get_session() as s:
            return [dict(r) for r in s.execute(sql, {"uid": user_id}).mappings().all()]

    def get_holding_one(self, user_id: int, stock_code: str) -> dict | None:
        sql = text(
            "SELECT position_id FROM trade_worker_position "
            "WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING' LIMIT 1"
        )
        with get_session() as s:
            row = s.execute(sql, {"uid": user_id, "code": stock_code}).mappings().first()
        return dict(row) if row else None

    def get_user_notify(self, user_id: int) -> dict:
        """유저 알림 설정: email(user_master) + tele_bot_id/tele_chat_id(user_detail)."""
        sql = text(
            "SELECT m.email, d.tele_bot_id, d.tele_chat_id "
            "FROM user_master m LEFT JOIN user_detail d ON m.user_id = d.user_id "
            "WHERE m.user_id = :uid"
        )
        with get_session() as s:
            row = s.execute(sql, {"uid": user_id}).mappings().first()
        return dict(row) if row else {}

    def get_wallet_balance(self, user_id: int) -> Decimal:
        sql = text("SELECT user_balance FROM user_wallet WHERE user_id = :uid")
        with get_session() as s:
            row = s.execute(sql, {"uid": user_id}).mappings().first()
        return Decimal(row["user_balance"]) if row and row["user_balance"] is not None else Decimal(0)

    # ── 쓰기 ────────────────────────────────────────────────────────
    def set_wallet_balance(self, user_id: int, balance: Decimal) -> None:
        sql = text("UPDATE user_wallet SET user_balance = :bal, updated_at = :now WHERE user_id = :uid")
        with get_session() as s:
            s.execute(sql, {"bal": str(balance), "now": datetime.now(), "uid": user_id})
            s.commit()

    def set_wallet_snapshot(self, user_id: int, cash=None, stock_amount=None, total_asset=None) -> None:
        """user_wallet 스냅샷 갱신(예수금/보유주식평가/총자산). None 인 항목은 건드리지 않음."""
        sets = ["updated_at = :now"]
        params = {"uid": user_id, "now": datetime.now()}
        if cash is not None:
            sets.append("user_balance = :cash")
            params["cash"] = str(cash)
        if stock_amount is not None:
            sets.append("stock_amount = :st")
            params["st"] = str(stock_amount)
        if total_asset is not None:
            sets.append("total_asset = :tot")
            params["tot"] = str(total_asset)
        sql = text(f"UPDATE user_wallet SET {', '.join(sets)} WHERE user_id = :uid")
        with get_session() as s:
            s.execute(sql, params)
            s.commit()

    def replace_holdings(self, user_id: int, holdings: list) -> None:
        """user_holdings 를 실제 보유종목으로 전량 교체(snapshot). 부팅/체결 시 호출."""
        del_sql = text("DELETE FROM user_holdings WHERE user_id = :uid")
        ins_sql = text(
            "INSERT INTO user_holdings "
            "(user_id, stock_code, stock_name, qty, avg_price, cur_price, eval_amount, profit, updated_at) "
            "VALUES (:uid, :code, :name, :qty, :avg, :cur, :eval, :profit, :now)"
        )
        now = datetime.now()
        with get_session() as s:
            s.execute(del_sql, {"uid": user_id})
            for h in (holdings or []):
                s.execute(ins_sql, {
                    "uid": user_id,
                    "code": h["symbol"],
                    "name": h.get("name") or "",
                    "qty": str(h["qty"]),
                    "avg": str(h["avg_price"]),
                    "cur": str(h["cur_price"]),
                    "eval": str(h["eval_amount"]),
                    "profit": str(h["profit"]),
                    "now": now,
                })
            s.commit()

    def open_position(self, user_id: int, stock_code: str, stock_name: str,
                      entry_price: Decimal, qty: Decimal, entry_atr: Decimal = Decimal(0)) -> None:
        """worker 매수 체결 → trade_worker_position 에 HOLDING 신규 등록.
        entry_ymd/entry_at = 실제 매수 체결일. peak 는 진입가로 초기화, bars_held=0."""
        sql = text(
            """
            INSERT INTO trade_worker_position
                (user_id, stock_code, stock_name, entry_ymd, entry_at, entry_price, entry_atr,
                 qty, bars_held, peak_close, peak_high, bars_since_peak,
                 action_type, status, created_at, updated_at)
            VALUES
                (:uid, :code, :name, :eymd, :now, :eprice, :eatr,
                 :qty, 0, :eprice, :eprice, 0,
                 'HOLD', 'HOLDING', :now, :now)
            """
        )
        now = datetime.now()
        with get_session() as s:
            s.execute(sql, {
                "uid": user_id, "code": stock_code, "name": stock_name,
                "eymd": now.strftime("%Y%m%d"), "now": now,
                "eprice": str(entry_price), "eatr": str(entry_atr), "qty": str(qty),
            })
            s.commit()

    def update_position_state(self, user_id: int, stock_code: str, state: dict) -> None:
        """일별 갱신: 추적값(peak/bars) + 매도라인(stop/target/trail) + action 갱신. HOLDING 만."""
        cols = {
            "bars_held": "bars_held", "peak_close": "peak_close", "peak_high": "peak_high",
            "bars_since_peak": "bars_since_peak", "last_check_ymd": "last_check_ymd",
            "stop_price": "stop_price", "target_price": "target_price", "trail_line": "trail_line",
            "action_type": "action_type", "profit_pct": "profit_pct", "sell_reason": "sell_reason",
            "entry_atr": "entry_atr",
        }
        sets, params = ["updated_at = :now"], {"now": datetime.now(), "uid": user_id, "code": stock_code}
        for key, col in cols.items():
            if key in state and state[key] is not None:
                sets.append(f"{col} = :{key}")
                params[key] = str(state[key]) if not isinstance(state[key], (int, str)) else state[key]
        sql = text(
            f"UPDATE trade_worker_position SET {', '.join(sets)} "
            f"WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'"
        )
        with get_session() as s:
            s.execute(sql, params)
            s.commit()

    def update_position_qty(self, user_id: int, stock_code: str, qty: Decimal) -> None:
        """보유수량 갱신(부팅 대사 등 실제 수량과 맞출 때). HOLDING 만."""
        sql = text(
            "UPDATE trade_worker_position SET qty = :qty, updated_at = :now "
            "WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'"
        )
        with get_session() as s:
            s.execute(sql, {"qty": str(qty), "now": datetime.now(), "uid": user_id, "code": stock_code})
            s.commit()

    def close_position(self, user_id: int, stock_code: str, exit_price: Decimal,
                       filled_qty: Decimal, reason: str) -> None:
        """매도 체결 → status=SOLD + 청산정보/실현손익 기록(이력으로 남김)."""
        sql = text(
            """
            UPDATE trade_worker_position
            SET status = 'SOLD', exit_at = :now, exit_price = :xprice, exit_reason = :reason,
                pnl = (:xprice - entry_price) * :fqty, updated_at = :now
            WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'
            """
        )
        with get_session() as s:
            s.execute(sql, {
                "now": datetime.now(), "xprice": str(exit_price), "reason": (reason or "")[:45],
                "fqty": str(filled_qty), "uid": user_id, "code": stock_code,
            })
            s.commit()

    def insert_worker_log(self, user_id: int, source: str, level: str, message: str) -> None:
        """worker 로그 1건 적재(시간순). trade_worker_log 테이블."""
        sql = text(
            "INSERT INTO trade_worker_log (user_id, source, level, message, created_at) "
            "VALUES (:uid, :src, :lvl, :msg, :now)"
        )
        with get_session() as s:
            s.execute(sql, {
                "uid": user_id, "src": (source or "")[:10], "lvl": (level or "")[:10],
                "msg": (message or "")[:500], "now": datetime.now(),
            })
            s.commit()

    def insert_trade_log(self, user_id: int, stock_code: str, action: str,
                         price: Decimal, qty: Decimal, krw_balance: Decimal,
                         note: str = "") -> None:
        sql = text(
            """
            INSERT INTO trade_log
                (user_id, coin_symbol, action_type, order_time, exec_time,
                 price, quantity, total_amount, remain_qty, fee, pnl, krw_balance, note)
            VALUES
                (:uid, :code, :action, :now, :now,
                 :price, :qty, :total, 0, 0, 0, :krw, :note)
            """
        )
        now = datetime.now()
        total = Decimal(price) * Decimal(qty)
        with get_session() as s:
            s.execute(sql, {
                "uid": user_id, "code": stock_code, "action": action, "now": now,
                "price": str(price), "qty": str(qty), "total": str(total),
                "krw": str(krw_balance), "note": note[:255],
            })
            s.commit()
