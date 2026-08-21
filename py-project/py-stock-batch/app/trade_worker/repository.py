"""
trade_worker DB 접근 계층 (메인 DAO 와 독립, raw SQL).
※ trade_sell_target_stock 와 완전 분리. worker 매수/매도 포지션은 trade_worker_position 사용.

읽기:
  - get_latest_buy_target_ymd / get_buy_targets(ymd) : trade_buy_target_stock (공용 추천)
  - get_holding_positions / get_holding_one          : trade_worker_position status='HOLDING'
  - get_wallet_balance(user_id)                      : user_wallet
쓰기:
  - open_position / open_position_if_absent / update_position_state / close_position : trade_worker_position
  - set_wallet_balance / set_wallet_snapshot / replace_holdings : user_wallet / user_holdings
  - insert_trade_log / insert_worker_log             : trade_log / trade_worker_log

매도 수기등록(모드 무관, sql/08_manual_sell_order_ddl.sql):
  - get_active_manual_sells / get_manual_sell / upsert_manual_sell /
    cancel_manual_sell / complete_manual_sell         : trade_worker_manual_sell
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
#  구현은 stock_shared.strategy.buy_order 에 있다.
#  worker 와 화면 시뮬레이션(TradeSimulation)이 **같은 순서**로 종목을 골라야
#  "시뮬 결과와 실제 매수가 다른" 상황이 생기지 않는다. 그래서 규칙을 여기
#  복제하지 않고 shared 한 곳에 둔다. 정렬 항목 추가도 그쪽 ORDER_FIELDS 에서 한다.
#
#  아래 이름들은 기존 import 경로 호환을 위해 re-export 한다.
# ──────────────────────────────────────────────────────────────────
from stock_shared.strategy.buy_order import (  # noqa: E402,F401
    ORDER_FIELDS as _ORDER_FIELDS,
    DEFAULT_BUY_ORDER,
    parse_buy_order,
    make_buy_order_key,
    describe_buy_order,
)


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

    # ── 운용모드 (user_trade_mode) ──────────────────────────────────
    def get_trade_mode(self, user_id: int) -> dict:
        """유저의 현재 운용모드 상태.

        반환 키:
          active_mode   현재 모드 코드 (없으면 None)
          pending_mode  예약 모드 — 보유분 청산 후 승계될 모드
          run_state     IDLE / ARMED / HOLDING / SWITCH_PENDING
          enabled_flag  자동매매 ON/OFF (Y/N)

        행이 없으면 전부 None/기본값. worker 는 모드를 못 읽어도 죽지 않고
        호출측이 기본 모드로 떨어지도록 한다(부팅 실패보다 낫다).
        """
        sql = text(
            "SELECT active_mode, pending_mode, run_state, enabled_flag "
            "FROM user_trade_mode WHERE user_id = :uid"
        )
        try:
            with get_session() as s:
                row = s.execute(sql, {"uid": user_id}).mappings().first()
        except Exception as e:  # noqa: BLE001  (테이블 미생성 등)
            log.warning("운용모드 조회 실패 user_id=%s: %s", user_id, e)
            return {"active_mode": None, "pending_mode": None,
                    "run_state": None, "enabled_flag": None}
        if not row:
            return {"active_mode": None, "pending_mode": None,
                    "run_state": None, "enabled_flag": None}
        return dict(row)

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

    def open_position_if_absent(self, user_id: int, stock_code: str, stock_name: str,
                                entry_price: Decimal, qty: Decimal,
                                entry_atr: Decimal = Decimal(0),
                                exclusive_flag: str = "Y") -> bool:
        """이미 HOLDING 포지션이 있으면 아무것도 안 하고 False. 없으면 신규 등록 후 True.

        wallet_sync.reconcile_wallet 이 **계좌 실보유(user_holdings) 중 worker 가
        추적하지 않는 종목**(HTS/MTS 등 타채널 매수분 포함)을 흡수할 때 쓴다
        (2026-08-21, §11.4 대체 구현). 존재 확인 + 삽입을 한 SQL(INSERT ... SELECT
        ... WHERE NOT EXISTS)로 묶어 레이스를 줄이지만, user_id+stock_code+status
        유니크 제약이 없어 완전한 원자성 보장은 아니다 — 편입은 폴링 주기(수십 초)
        당 한 번뿐이라 실질 위험은 낮다. mode_note='EXTERNAL_ABSORBED' 로 worker 가
        직접 산 게 아님을 남긴다.

        exclusive_flag 기본값 'Y': 이 포지션은 BaseBuyExecutor.allow_buy() 의
        "1포지션 원칙" 카운트에서 제외된다(get_holding_positions(exclude_exclusive=True)
        가 걸러냄). 그렇지 않으면(기본값 없이 NULL) 계좌에 있던 종목이 편입되는
        순간 worker 의 자기 자동매수(09:00 cron)가 그 종목이 팔릴 때까지 전부
        멈춘다 — 흡수는 매도 감시 목적이지 매수 정지를 의도한 게 아니므로 기본
        'Y' 로 매수 카운트에서 뺀다. 매도 감시(get_holding_positions 기본 False)는
        exclusive_flag 와 무관하게 항상 전량을 보므로 이 값과 상관없이 그대로 걸린다.
        """
        sql = text(
            """
            INSERT INTO trade_worker_position
                (user_id, stock_code, stock_name, entry_ymd, entry_at, entry_price, entry_atr,
                 qty, bars_held, peak_close, peak_high, bars_since_peak,
                 action_type, status, mode_note, exclusive_flag, created_at, updated_at)
            SELECT :uid, :code, :name, :eymd, :now, :eprice, :eatr,
                   :qty, 0, :eprice, :eprice, 0,
                   'HOLD', 'HOLDING', 'EXTERNAL_ABSORBED', :exclusive, :now, :now
            FROM DUAL
            WHERE NOT EXISTS (
                SELECT 1 FROM trade_worker_position
                WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'
            )
            """
        )
        now = datetime.now()
        with get_session() as s:
            result = s.execute(sql, {
                "uid": user_id, "code": stock_code, "name": stock_name,
                "eymd": now.strftime("%Y%m%d"), "now": now,
                "eprice": str(entry_price), "eatr": str(entry_atr), "qty": str(qty),
                "exclusive": exclusive_flag,
            })
            s.commit()
            return (result.rowcount or 0) > 0

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

    def add_position_qty(self, user_id: int, stock_code: str, delta_qty: Decimal,
                         fill_price: Decimal) -> None:
        """매수 잔량이 뒤늦게 체결 → 보유수량 증분 + 평단가 재계산. HOLDING 만.

        동기 창(wait_fill) 밖에서 도착한 체결통보를 반영하는 경로다.
        평단가는 (기존평가금액 + 이번체결금액) / 총수량 으로 가중평균한다.
        진입가가 바뀌면 손절/익절 라인의 기준도 바뀌므로, 호출측에서 라인 재계산이 필요하다.
        """
        sql = text(
            """
            UPDATE trade_worker_position
            SET entry_price = (entry_price * qty + :px * :dqty) / (qty + :dqty),
                qty = qty + :dqty,
                updated_at = :now
            WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'
              AND qty + :dqty > 0
            """
        )
        with get_session() as s:
            s.execute(sql, {"dqty": str(delta_qty), "px": str(fill_price),
                            "now": datetime.now(), "uid": user_id, "code": stock_code})
            s.commit()

    def reduce_position(self, user_id: int, stock_code: str, exit_price: Decimal,
                        filled_qty: Decimal, reason: str) -> Decimal:
        """부분 매도 → 보유수량 차감. 남은 수량을 반환한다.

        잔량이 0 이 되면 close_position 과 동일하게 SOLD 로 종료한다.
        pnl 은 이번 체결분의 실현손익을 **누적 가산**한다(부분 매도가 여러 번 나뉘어도 합산).
        entry_price 는 건드리지 않는다 — 매도는 평단가를 바꾸지 않는다.

        반환: 차감 후 잔여수량. 포지션이 없으면 Decimal(0).
        """
        with get_session() as s:
            row = s.execute(
                text("SELECT qty FROM trade_worker_position "
                     "WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'"),
                {"uid": user_id, "code": stock_code},
            ).mappings().first()
            if not row:
                return Decimal(0)

            now = datetime.now()
            remain = Decimal(str(row["qty"] or 0)) - Decimal(str(filled_qty))
            if remain <= 0:
                # 전량 소진 → 종료. pnl 은 이번 체결분까지 누적해서 확정.
                # qty 는 건드리지 않는다 — close_position 과 동일하게 두어 M0 동작을 보존한다
                # (SOLD 행의 qty = 마지막 보유수량. 매수 총량은 trade_log 로 추적한다).
                s.execute(
                    text("""
                        UPDATE trade_worker_position
                        SET status = 'SOLD', exit_at = :now, exit_price = :xprice,
                            exit_reason = :reason,
                            pnl = COALESCE(pnl, 0) + (:xprice - entry_price) * :fqty,
                            updated_at = :now
                        WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'
                    """),
                    {"now": now, "xprice": str(exit_price), "reason": (reason or "")[:45],
                     "fqty": str(filled_qty), "uid": user_id, "code": stock_code},
                )
                s.commit()
                return Decimal(0)

            # 잔량 있음 → HOLDING 유지, 실현손익만 누적
            s.execute(
                text("""
                    UPDATE trade_worker_position
                    SET qty = :remain,
                        pnl = COALESCE(pnl, 0) + (:xprice - entry_price) * :fqty,
                        exit_price = :xprice, exit_reason = :reason, updated_at = :now
                    WHERE user_id = :uid AND stock_code = :code AND status = 'HOLDING'
                """),
                {"remain": str(remain), "xprice": str(exit_price), "fqty": str(filled_qty),
                 "reason": (reason or "")[:45], "now": now,
                 "uid": user_id, "code": stock_code},
            )
            s.commit()
            return remain

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

    # ── 매도 수기등록(지정가, 모드 무관) ──────────────────────────────
    #   trade_worker_manual_sell. 등록되면 sell_executor 가 그 종목의 모드
    #   자동 매도 rule(stop/target/trail·일봉 신호)을 보지 않고 sell_price
    #   도달 여부만으로 매도한다(BaseSellExecutor 공통 코드, 모드 무관).
    def get_active_manual_sells(self, user_id: int) -> list[dict]:
        """감시중(ARMED) + 활성(enabled_flag='Y') 수기등록 전체.
        sell_executor 가 주기적으로 재적재해 메모리(dict)로 들고 있는다."""
        sql = text(
            "SELECT user_id, stock_code, stock_name, sell_price, qty_ratio, "
            "       state, enabled_flag, memo "
            "  FROM trade_worker_manual_sell "
            " WHERE user_id = :uid AND state = 'ARMED' AND enabled_flag = 'Y'"
        )
        with get_session() as s:
            return [dict(r) for r in s.execute(sql, {"uid": user_id}).mappings().all()]

    def get_manual_sell(self, user_id: int, stock_code: str) -> dict | None:
        sql = text(
            "SELECT * FROM trade_worker_manual_sell WHERE user_id = :uid AND stock_code = :code"
        )
        with get_session() as s:
            row = s.execute(sql, {"uid": user_id, "code": stock_code}).mappings().first()
        return dict(row) if row else None

    def get_latest_manual_sell(self, user_id: int) -> dict | None:
        """단일 슬롯 화면(LimitOrder.vue) 전용 — 종목코드 없이 "지금 등록된 것" 1건을
        조회한다. get_active_manual_sells 와 달리 enabled_flag='Y' 로 거르지 않는다
        (감시를 꺼둔(enabled_flag='N') 등록도 화면엔 계속 보여야 하므로 — "등록은
        유지되지만 감시하지 않습니다" 문구 참고). state='ARMED' 인 것 중 가장 최근
        갱신 1건. 여러 종목을 동시 등록하는 화면(M2/M3 전용)이 생기면 이 메서드
        대신 get_active_manual_sells 를 그대로 쓰면 된다."""
        sql = text(
            "SELECT * FROM trade_worker_manual_sell "
            " WHERE user_id = :uid AND state = 'ARMED' "
            " ORDER BY updated_at DESC LIMIT 1"
        )
        with get_session() as s:
            row = s.execute(sql, {"uid": user_id}).mappings().first()
        return dict(row) if row else None

    def upsert_manual_sell(self, user_id: int, stock_code: str, stock_name: str,
                           sell_price: Decimal, qty_ratio: Decimal = Decimal("1"),
                           memo: str | None = None, enabled_flag: str = "Y") -> None:
        """등록/재등록. 이미 있으면(같은 유저+종목) 값만 갱신하고 ARMED 로 되돌린다
        (예: DONE/CANCELLED 상태였던 종목을 다시 등록하는 경우).
        enabled_flag='N' 으로 저장하면 등록 자체는 유지되지만 get_active_manual_sells
        (worker 가 읽는 감시 대상)에서 빠진다 — "감시 사용" 토글의 실제 동작."""
        now = datetime.now()
        sql = text(
            """
            INSERT INTO trade_worker_manual_sell
                (user_id, stock_code, stock_name, sell_price, qty_ratio,
                 state, enabled_flag, memo, created_at, updated_at)
            VALUES
                (:uid, :code, :name, :price, :ratio,
                 'ARMED', :flag, :memo, :now, :now)
            ON DUPLICATE KEY UPDATE
                stock_name = :name, sell_price = :price, qty_ratio = :ratio,
                state = 'ARMED', enabled_flag = :flag, memo = :memo,
                filled_price = NULL, filled_qty = NULL, filled_at = NULL,
                updated_at = :now
            """
        )
        with get_session() as s:
            s.execute(sql, {
                "uid": user_id, "code": stock_code, "name": stock_name or "",
                "price": str(sell_price), "ratio": str(qty_ratio), "memo": memo,
                "flag": (enabled_flag or "Y"), "now": now,
            })
            s.commit()

    def cancel_manual_sell(self, user_id: int, stock_code: str) -> None:
        """사용자 취소. 체결 이력을 남기기 위해 삭제 대신 상태만 바꾼다."""
        sql = text(
            "UPDATE trade_worker_manual_sell SET state = 'CANCELLED', updated_at = :now "
            "WHERE user_id = :uid AND stock_code = :code AND state = 'ARMED'"
        )
        with get_session() as s:
            s.execute(sql, {"now": datetime.now(), "uid": user_id, "code": stock_code})
            s.commit()

    def complete_manual_sell(self, user_id: int, stock_code: str,
                             filled_price: Decimal, filled_qty: Decimal) -> None:
        """수기등록 지정가 도달 → worker 가 대신 체결 완료. DONE 으로 종료."""
        sql = text(
            """
            UPDATE trade_worker_manual_sell
            SET state = 'DONE', filled_price = :price, filled_qty = :qty,
                filled_at = :now, updated_at = :now
            WHERE user_id = :uid AND stock_code = :code AND state = 'ARMED'
            """
        )
        with get_session() as s:
            s.execute(sql, {"price": str(filled_price), "qty": str(filled_qty),
                            "now": datetime.now(), "uid": user_id, "code": stock_code})
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
