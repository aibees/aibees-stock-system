"""
stock_ohlcv_daily(+_state) DAO — 백테스트용 일봉 원천.

쓰기는 StockOhlcvDailyJob 하나뿐이다. 종목 단위로 호출하고 커밋도 호출부가 종목 단위로 한다.
  - replace_bars : 종목 전체 교체(백필·수정주가 재수집). DELETE 후 INSERT.
  - upsert_bars  : 증분. PK(stock_code, trade_date) 기준 UPSERT.
"""
import logging
from datetime import datetime

from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.stockOhlcvDaily import StockOhlcvDaily, StockOhlcvDailyState

logging.basicConfig(level=logging.ERROR)

_BAR_COLS = ("open_price", "high_price", "low_price", "close_price", "volume", "amount")


class StockOhlcvDailyDao(BaseDao):
    model = StockOhlcvDaily

    def __init__(self):
        self.__name__ = "StockOhlcvDailyDao"

    # ------------------------------------------------------------------
    # select
    # ------------------------------------------------------------------
    def select_states(self, session) -> dict:
        """{stock_code: state dict}. 대상 분류(백필/증분)용."""
        rows = session.execute(select(StockOhlcvDailyState)).scalars().all()
        return {r.stock_code: r.to_dict() for r in rows}

    def select_closes_since(self, session, stock_code: str, from_date) -> dict:
        """{trade_date: close_price}. 증분 시 겹치는 구간 비교용."""
        stmt = select(StockOhlcvDaily.trade_date, StockOhlcvDaily.close_price).where(and_(
            StockOhlcvDaily.stock_code == stock_code,
            StockOhlcvDaily.trade_date >= from_date,
        ))
        return {d: int(c) for d, c in session.execute(stmt).all()}

    def select_bounds(self, session, stock_code: str) -> dict:
        """적재 구간과 봉 수. 상태 테이블 갱신용."""
        stmt = select(
            func.min(StockOhlcvDaily.trade_date),
            func.max(StockOhlcvDaily.trade_date),
            func.count(),
        ).where(StockOhlcvDaily.stock_code == stock_code)
        first, last, cnt = session.execute(stmt).one()
        return {"first_date": first, "last_date": last, "bar_cnt": int(cnt or 0)}

    def select_bars(self, session, stock_code: str, from_date=None, to_date=None) -> list:
        """일봉 오름차순. 백테스트 로더용."""
        conds = [StockOhlcvDaily.stock_code == stock_code]
        if from_date:
            conds.append(StockOhlcvDaily.trade_date >= from_date)
        if to_date:
            conds.append(StockOhlcvDaily.trade_date <= to_date)
        stmt = select(StockOhlcvDaily).where(and_(*conds)).order_by(StockOhlcvDaily.trade_date.asc())
        return [r.to_dict() for r in session.execute(stmt).scalars().all()]

    # ------------------------------------------------------------------
    # write
    # ------------------------------------------------------------------
    def replace_bars(self, session, stock_code: str, bars: list, chunk_size: int = 500) -> int:
        """종목 일봉 전체 교체. 수정주가가 바뀌면 과거 전 구간이 달라지므로 부분 갱신으로는 맞출 수 없다.

        처음 받는 종목은 DELETE 를 건너뛴다. REPEATABLE READ 에서 없는 범위를 DELETE 하면
        갭 락이 걸리고, 병렬 스레드가 인접 종목을 INSERT 하다 서로 막혀 데드락(1213)이 난다.
        """
        if self.select_bounds(session, stock_code)["bar_cnt"]:
            session.execute(delete(StockOhlcvDaily).where(StockOhlcvDaily.stock_code == stock_code))
        return self._insert(session, stock_code, bars, chunk_size, upsert=False)

    def upsert_bars(self, session, stock_code: str, bars: list, chunk_size: int = 500) -> int:
        """증분 UPSERT. 당일 봉이 장 마감 후 확정값으로 바뀌어도 덮인다."""
        return self._insert(session, stock_code, bars, chunk_size, upsert=True)

    def _insert(self, session, stock_code: str, bars: list, chunk_size: int, upsert: bool) -> int:
        rows = [{"stock_code": stock_code, "trade_date": b["trade_date"],
                 **{c: b[c] for c in _BAR_COLS}} for b in bars]
        for i in range(0, len(rows), chunk_size):
            stmt = mysql_insert(StockOhlcvDaily).values(rows[i:i + chunk_size])
            if upsert:
                stmt = stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in _BAR_COLS})
            session.execute(stmt)
        return len(rows)

    def upsert_state(self, session, stock_code: str, **fields) -> None:
        """상태 행 UPSERT. 넘긴 필드만 갱신하고 updated_at 은 항상 지금으로 맞춘다."""
        row = {"stock_code": stock_code, "updated_at": datetime.now(), **fields}
        stmt = mysql_insert(StockOhlcvDailyState).values(row)
        stmt = stmt.on_duplicate_key_update(**{k: stmt.inserted[k] for k in row if k != "stock_code"})
        session.execute(stmt)
