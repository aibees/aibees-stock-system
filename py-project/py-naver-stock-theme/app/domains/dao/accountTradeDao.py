"""
accountTradeDao.py — 계좌 현황 / 거래 내역 READ-ONLY DAO

명세: "계좌 현황 · 거래 내역 — BE(Flask) 협조요청 명세서"
프론트: MyWallet.vue(계좌 현황), TradeLog.vue(거래 내역)

핵심 규칙:
    1. read-only. write(INSERT/UPDATE/DELETE) 없음. 적재는 trade_worker 전담.
    2. 모든 쿼리는 WHERE user_id = :uid 로 스코프 강제 (멀티테넌시).
    3. DECIMAL / datetime 은 원본 그대로(native) 반환한다.
       → 문자열 직렬화(str/ISO8601)는 라우터의 _row() 가 전담.
       (기존 model.to_dict() 는 float 캐스팅을 하므로 명세 위반 → 사용하지 않음)

데이터 출처:
    ① user_wallet              : 계좌 요약
    ② v_user_portfolio (VIEW)  : 보유 종목 + 합계(TOTAL 행)
    ③④ trade_worker_position   : worker 포지션 / 매매 이력
    ⑤ trade_log                : 체결 로그 (coin_symbol 컬럼에 주식코드 저장)
    ⑥ trade_worker_log         : 운영 로그

주의: v_user_portfolio / trade_worker_position / trade_worker_log 는
      trade_worker 가 생성·적재하는 자원이다. DDL 은
      docs/account_trade_worker_tables.sql 참조.
"""

from datetime import datetime, timedelta

from sqlalchemy import text

import logging
logging.basicConfig(level=logging.ERROR)


class AccountTradeDao:
    """계좌/거래 조회 전용 DAO. 모든 메서드는 read-only."""

    def __init__(self):
        self.__name__ = 'AccountTradeDao'

    # ------------------------------------------------------------------
    # 내부 헬퍼 — 기간 파라미터 보정
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_from(value):
        """'YYYY-MM-DD' 또는 ISO8601 → datetime. 'YYYY-MM-DD' 는 00:00:00 으로 보정."""
        if value is None or value == '':
            return None
        v = str(value).strip()
        if len(v) == 10:  # YYYY-MM-DD
            return datetime.strptime(v, "%Y-%m-%d")
        return datetime.fromisoformat(v)

    @staticmethod
    def _parse_to(value):
        """'to' 상한. 'YYYY-MM-DD' 로 오면 다음날 00:00:00 으로 보정(exclusive <)."""
        if value is None or value == '':
            return None
        v = str(value).strip()
        if len(v) == 10:  # YYYY-MM-DD → 다음날 00:00:00
            return datetime.strptime(v, "%Y-%m-%d") + timedelta(days=1)
        return datetime.fromisoformat(v)

    # ==================================================================
    # ① 계좌 요약 — user_wallet 단건
    # ==================================================================
    def get_wallet(self, session, user_id: int):
        stmt = text("""
            SELECT user_id, user_balance, stock_amount, total_asset, updated_at
            FROM   user_wallet
            WHERE  user_id = :uid
        """)
        row = session.execute(stmt, {"uid": user_id}).mappings().first()
        return dict(row) if row else None

    # ==================================================================
    # ② 보유 포트폴리오 — v_user_portfolio (STOCK 행 + TOTAL 행)
    # ==================================================================
    def get_portfolio(self, session, user_id: int):
        stmt = text("""
            SELECT *
            FROM   v_user_portfolio
            WHERE  user_id = :uid
            ORDER BY row_type, stock_code
        """)
        rows = session.execute(stmt, {"uid": user_id}).mappings().all()
        return [dict(r) for r in rows]

    # ==================================================================
    # ③④ worker 포지션 / 매매 이력 — trade_worker_position
    #     status 필터(None|HOLDING|SOLD) + 페이지네이션 + total
    # ==================================================================
    def get_positions(self, session, user_id: int, status, limit: int, offset: int):
        where = "WHERE user_id = :uid AND (:status IS NULL OR status = :status)"
        params = {"uid": user_id, "status": status}

        total = session.execute(
            text(f"SELECT COUNT(*) FROM trade_worker_position {where}"), params
        ).scalar() or 0

        rows = session.execute(
            text(f"""
                SELECT *
                FROM   trade_worker_position
                {where}
                ORDER BY entry_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], total

    # ==================================================================
    # ⑤ 거래(체결) 로그 — trade_log
    #    필터: action / stock_code(=coin_symbol) / exec_time 범위
    # ==================================================================
    def get_trade_logs(self, session, user_id: int,
                       action=None, code=None, dt_from=None, dt_to=None,
                       limit: int = 20, offset: int = 0):
        where = """
            WHERE user_id = :uid
              AND (:dt_from IS NULL OR exec_time >= :dt_from)
              AND (:dt_to   IS NULL OR exec_time <  :dt_to)
              AND (:code    IS NULL OR coin_symbol = :code)
              AND (:action  IS NULL OR action_type = :action)
        """
        params = {
            "uid": user_id,
            "action": action or None,
            "code": code or None,
            "dt_from": self._parse_from(dt_from),
            "dt_to": self._parse_to(dt_to),
        }

        total = session.execute(
            text(f"SELECT COUNT(*) FROM trade_log {where}"), params
        ).scalar() or 0

        rows = session.execute(
            text(f"""
                SELECT trade_id, user_id, coin_symbol, action_type,
                       order_time, exec_time, price, quantity, total_amount,
                       remain_qty, fee, pnl, krw_balance, note
                FROM   trade_log
                {where}
                ORDER BY exec_time DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset},
        ).mappings().all()

        # coin_symbol → stock_code 로 키 변환 (프론트에 coin_ 접두어 노출 금지)
        out = []
        for r in rows:
            d = dict(r)
            d["stock_code"] = d.pop("coin_symbol", None)
            out.append(d)
        return out, total

    # ==================================================================
    # ⑥ 운영 로그 — trade_worker_log
    #    필터: source(buy|sell) / level(INFO|WARN) / created_at >=
    # ==================================================================
    def get_worker_logs(self, session, user_id: int,
                        source=None, level=None, dt_from=None,
                        limit: int = 20, offset: int = 0):
        where = """
            WHERE user_id = :uid
              AND (:source IS NULL OR source = :source)
              AND (:level  IS NULL OR level  = :level)
              AND (:dt_from IS NULL OR created_at >= :dt_from)
        """
        params = {
            "uid": user_id,
            "source": source or None,
            "level": level or None,
            "dt_from": self._parse_from(dt_from),
        }

        total = session.execute(
            text(f"SELECT COUNT(*) FROM trade_worker_log {where}"), params
        ).scalar() or 0

        rows = session.execute(
            text(f"""
                SELECT log_id, user_id, source, level, message, created_at
                FROM   trade_worker_log
                {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {**params, "limit": limit, "offset": offset},
        ).mappings().all()

        return [dict(r) for r in rows], total
