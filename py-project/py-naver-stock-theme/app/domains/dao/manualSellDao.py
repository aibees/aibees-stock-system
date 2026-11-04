"""
매도 수기등록 DAO — trade_worker_manual_sell (sql/08, 09, 27).

화면 요청을 저장하고 조회만 한다. 등록된 행은 worker(py-stock-batch sell_executor)가 재적재(기본 60초)해
조건이 맞으면 판다. 모든 쿼리는 user_id 조건을 건다 — 호출측은 JWT 의 사용자만 넘긴다.
트랜잭션은 호출측(요청 종료 시 commit)이 관리한다.
"""
from decimal import Decimal

from sqlalchemy import text

SELL_NOW_MEMO = '지금 팔기'
# '지금 팔기'는 DOWN(체결가 <= sell_price) 이라 어떤 체결가에서도 첫 틱에 도달한다. DECIMAL(15,2) 범위 안의 값.
# 주문가는 sell_price 가 아니라 실시간 체결가로 나가므로 이 값이 주문에 실리지 않는다.
SELL_NOW_PRICE = Decimal('9999999999999')


class ManualSellDao:
    def __init__(self):
        self.name = 'ManualSellDao'

    def select_holdings(self, session, user_id: int):
        rows = session.execute(text("""
            SELECT stock_code, stock_name, qty, avg_price, cur_price, eval_amount, profit
            FROM   user_holdings
            WHERE  user_id = :uid
            ORDER BY stock_code ASC
        """), {'uid': user_id}).mappings().all()
        return [dict(r) for r in rows]

    def select_holding(self, session, user_id: int, stock_code: str):
        row = session.execute(text("""
            SELECT stock_code, stock_name, qty
            FROM   user_holdings
            WHERE  user_id = :uid AND stock_code = :code
        """), {'uid': user_id, 'code': stock_code}).mappings().first()
        return dict(row) if row else None

    def select_orders(self, session, user_id: int):
        """화면용 전체 목록(모든 상태). 체결·취소 이력과 감시를 꺼둔 등록도 보여야 해서 거르지 않는다."""
        rows = session.execute(text("""
            SELECT * FROM trade_worker_manual_sell
            WHERE  user_id = :uid
            ORDER BY stock_code ASC, sell_price ASC
        """), {'uid': user_id}).mappings().all()
        return [dict(r) for r in rows]

    def select_order_by_memo(self, session, user_id: int, stock_code: str, memo: str):
        """같은 종목·메모의 대기 중(ARMED) 등록 중 가장 최근 행."""
        row = session.execute(text("""
            SELECT * FROM trade_worker_manual_sell
            WHERE  user_id = :uid AND stock_code = :code AND memo = :memo
              AND  state = 'ARMED' AND enabled_flag = 'Y'
            ORDER BY id DESC
            LIMIT 1
        """), {'uid': user_id, 'code': stock_code, 'memo': memo}).mappings().first()
        return dict(row) if row else None

    def select_order(self, session, user_id: int, order_id: int):
        row = session.execute(text("""
            SELECT * FROM trade_worker_manual_sell WHERE user_id = :uid AND id = :id
        """), {'uid': user_id, 'id': order_id}).mappings().first()
        return dict(row) if row else None

    def insert(self, session, user_id: int, stock_code: str, stock_name: str, sell_price,
               trigger_type: str, qty_ratio, base_qty, enabled_flag: str, memo) -> int:
        """항상 새 행을 만든다(종목당 여러 티어 허용). base_qty 로 매도 수량을 등록 시점 기준으로 고정한다."""
        result = session.execute(text("""
            INSERT INTO trade_worker_manual_sell
                (user_id, stock_code, stock_name, sell_price, trigger_type, qty_ratio, base_qty,
                 state, enabled_flag, memo, created_at, updated_at)
            VALUES
                (:uid, :code, :name, :price, :trigger, :ratio, :base_qty,
                 'ARMED', :flag, :memo, NOW(), NOW())
        """), {'uid': user_id, 'code': stock_code, 'name': stock_name or '', 'price': str(sell_price),
               'trigger': trigger_type, 'ratio': str(qty_ratio), 'base_qty': str(base_qty),
               'flag': enabled_flag, 'memo': memo})
        return result.lastrowid

    def cancel(self, session, user_id: int, order_id: int) -> bool:
        """이 티어만 취소한다. 같은 종목의 다른 티어는 그대로 둔다."""
        result = session.execute(text("""
            UPDATE trade_worker_manual_sell
            SET    state = 'CANCELLED', updated_at = NOW()
            WHERE  user_id = :uid AND id = :id AND state = 'ARMED'
        """), {'uid': user_id, 'id': order_id})
        return result.rowcount == 1
