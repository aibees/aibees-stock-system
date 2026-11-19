"""
운용모드 관리 DAO — master_trade_mode / user_trade_mode / trade_mode_change_log / trade_worker_position(조회).

worker(py-stock-batch trade_worker)는 user_trade_mode.active_mode 만 읽는다(설정 폴링으로 장중 전환 반영).
pending_mode(보유분 청산 후 승계)는 worker 에 승계 로직이 없어 쓰지 않는다 — 전환은 항상 즉시 적용.
트랜잭션은 호출측(요청 종료 시 commit)이 관리한다.
"""
from sqlalchemy import text


class TradeModeDao:
    def __init__(self):
        self.name = 'TradeModeDao'

    def select_modes(self, session):
        rows = session.execute(text("""
            SELECT mode_code, mode_name, mode_desc, sort_order
            FROM   master_trade_mode
            WHERE  enabled_flag = 'Y'
            ORDER BY sort_order, mode_code
        """)).mappings().all()
        return [dict(r) for r in rows]

    def select_state(self, session, user_id: int):
        row = session.execute(text("""
            SELECT active_mode, active_from, enabled_flag, run_state,
                   pending_mode, last_tick_at, last_message, updated_at
            FROM   user_trade_mode
            WHERE  user_id = :uid
        """), {"uid": user_id}).mappings().first()
        return dict(row) if row else None

    def select_holding_positions(self, session, user_id: int):
        rows = session.execute(text("""
            SELECT stock_code, stock_name, trade_mode, entry_at, entry_price, qty,
                   stop_price, target_price, trail_line, bars_held, profit_pct, sell_reason
            FROM   trade_worker_position
            WHERE  user_id = :uid AND status = 'HOLDING'
            ORDER BY entry_at DESC
        """), {"uid": user_id}).mappings().all()
        return [dict(r) for r in rows]

    def apply_mode(self, session, user_id: int, mode_code: str, enabled_flag: str):
        """모드 즉시 적용. 행이 없으면 만든다. 예약(pending)은 비운다."""
        session.execute(text("""
            INSERT INTO user_trade_mode
                (user_id, enabled_flag, run_state, active_mode, active_config, active_from,
                 pending_mode, pending_config, pending_at, created_at, updated_at)
            VALUES
                (:uid, :flag, 'IDLE', :mode, JSON_OBJECT(), NOW(), NULL, NULL, NULL, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                enabled_flag   = VALUES(enabled_flag),
                active_mode    = VALUES(active_mode),
                active_config  = VALUES(active_config),
                active_from    = NOW(),
                pending_mode   = NULL,
                pending_config = NULL,
                pending_at     = NULL,
                updated_at     = NOW()
        """), {"uid": user_id, "mode": mode_code, "flag": enabled_flag})

    def insert_change_log(self, session, user_id: int, action_type: str,
                          from_mode, to_mode, reason: str, actor: str = 'USER'):
        session.execute(text("""
            INSERT INTO trade_mode_change_log
                (user_id, action_type, from_mode, to_mode, reason, actor, created_at)
            VALUES (:uid, :action, :from_mode, :to_mode, :reason, :actor, NOW())
        """), {"uid": user_id, "action": action_type, "from_mode": from_mode,
               "to_mode": to_mode, "reason": reason, "actor": actor})

    def select_change_logs(self, session, user_id: int, limit: int):
        rows = session.execute(text("""
            SELECT log_id, action_type, from_mode, to_mode, reason, actor, created_at
            FROM   trade_mode_change_log
            WHERE  user_id = :uid
            ORDER BY log_id DESC
            LIMIT :limit
        """), {"uid": user_id, "limit": limit}).mappings().all()
        return [dict(r) for r in rows]
