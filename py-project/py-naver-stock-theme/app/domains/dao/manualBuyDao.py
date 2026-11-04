"""
수동 매수 DAO — trade_worker_manual_buy (sql/50_manual_buy.sql).

화면 요청을 저장하고 조회만 한다. 실제 주문과 체결 상태 갱신은 worker(py-stock-batch
trade_worker/manual_buy.py)가 맡는다. 트랜잭션은 호출측(요청 종료 시 commit)이 관리한다.

시간 비교는 DB NOW() 로만 한다 — API 서버와 worker 의 시계·시간대가 달라도 만료 판정이 어긋나지 않게.
"""
from sqlalchemy import text

REQUEST_TTL_SEC = 60   # worker 가 이 시간 안에 집어가지 않으면 만료(늦은 주문 방지). manual_buy.py 와 같은 값

_COLUMNS = """id, stock_code, stock_name, order_type, limit_price, qty, state, cancel_requested,
              order_no, session_name, filled_qty, avg_fill_price, reason, created_at, updated_at"""


class ManualBuyDao:
    def __init__(self):
        self.name = 'ManualBuyDao'

    def select_stock(self, session, stock_code: str):
        row = session.execute(
            text("SELECT stock_code, stock_name FROM master_stock WHERE stock_code = :code"),
            {'code': stock_code},
        ).mappings().first()
        return dict(row) if row else None

    def select_by_client_key(self, session, user_id: int, client_key: str):
        row = session.execute(
            text(f"SELECT {_COLUMNS} FROM trade_worker_manual_buy WHERE user_id = :uid AND client_key = :key"),
            {'uid': user_id, 'key': client_key},
        ).mappings().first()
        return dict(row) if row else None

    def select_by_id(self, session, user_id: int, order_id: int):
        row = session.execute(
            text(f"SELECT {_COLUMNS} FROM trade_worker_manual_buy WHERE user_id = :uid AND id = :id"),
            {'uid': user_id, 'id': order_id},
        ).mappings().first()
        return dict(row) if row else None

    def select_list(self, session, user_id: int, limit: int):
        rows = session.execute(
            text(f"""
                SELECT {_COLUMNS} FROM trade_worker_manual_buy
                WHERE  user_id = :uid
                ORDER BY id DESC
                LIMIT :limit
            """),
            {'uid': user_id, 'limit': limit},
        ).mappings().all()
        return [dict(r) for r in rows]

    def insert(self, session, user_id: int, client_key: str, stock_code: str, stock_name: str,
               order_type: str, limit_price, qty: int) -> None:
        session.execute(
            text("""
                INSERT INTO trade_worker_manual_buy
                    (user_id, client_key, stock_code, stock_name, order_type, limit_price, qty, state)
                VALUES
                    (:uid, :key, :code, :name, :type, :price, :qty, 'REQUESTED')
            """),
            {'uid': user_id, 'key': client_key, 'code': stock_code, 'name': stock_name,
             'type': order_type, 'price': limit_price, 'qty': qty},
        )

    def expire_stale(self, session, user_id: int) -> None:
        """worker 가 꺼져 있어 아무도 집어가지 않은 요청을 닫는다."""
        session.execute(
            text("""
                UPDATE trade_worker_manual_buy
                SET    state = 'EXPIRED', reason = '자동매매 서버가 응답하지 않아 주문하지 않았습니다.'
                WHERE  user_id = :uid AND state = 'REQUESTED'
                  AND  created_at < NOW() - INTERVAL :ttl SECOND
            """),
            {'uid': user_id, 'ttl': REQUEST_TTL_SEC},
        )

    def cancel_requested_order(self, session, user_id: int, order_id: int) -> bool:
        """아직 주문 전이면 바로 취소. worker 의 집어가기와 상태 조건으로 경쟁하므로 둘 중 하나만 성공한다."""
        result = session.execute(
            text("""
                UPDATE trade_worker_manual_buy
                SET    state = 'CANCELLED', reason = '주문 전 취소'
                WHERE  user_id = :uid AND id = :id AND state = 'REQUESTED'
            """),
            {'uid': user_id, 'id': order_id},
        )
        return result.rowcount == 1

    def request_open_cancel(self, session, user_id: int, order_id: int) -> bool:
        """접수된 주문 취소 요청. 실제 취소는 worker 가 다음 폴링에 낸다."""
        result = session.execute(
            text("""
                UPDATE trade_worker_manual_buy
                SET    cancel_requested = 'Y'
                WHERE  user_id = :uid AND id = :id AND state = 'OPEN'
            """),
            {'uid': user_id, 'id': order_id},
        )
        return result.rowcount == 1
