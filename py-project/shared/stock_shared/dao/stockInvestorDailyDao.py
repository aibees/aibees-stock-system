"""
stock_investor_daily DAO — 종목별 투자자 순매수(일별).

적재: py-stock-batch StockInvestorJob (07:10, KIS FHKST01010900)
조회: py-naver-stock-theme GET /api/v1/stocks/id/<code> (종목 화면의 '전일 수급')
"""
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.models.stockInvestorDaily import StockInvestorDaily

_COLUMNS = ["ymd", "stock_code", "close_price", "prsn_qty", "frgn_qty", "orgn_qty",
            "prsn_amt", "frgn_amt", "orgn_amt", "updated_at"]
_PK = {"ymd", "stock_code"}


class StockInvestorDailyDao:
    def __init__(self):
        self.__name__ = "StockInvestorDailyDao"

    def upsert_bulk(self, session, rows: list[dict]) -> int:
        """(ymd, stock_code) 기준 일괄 upsert. 반환: 시도한 행 수."""
        if not rows:
            return 0
        now = datetime.now()
        # 누락 키가 있으면 executemany 파라미터 수가 어긋나므로 전 컬럼을 채워 정규화한다.
        norm = [{**{c: r.get(c) for c in _COLUMNS}, "updated_at": now} for r in rows]
        stmt = mysql_insert(StockInvestorDaily)
        stmt = stmt.on_duplicate_key_update(
            **{c: stmt.inserted[c] for c in _COLUMNS if c not in _PK}
        )
        session.execute(stmt, norm)
        return len(norm)

    def delete_older_than(self, session, days: int) -> int:
        """days 일보다 오래된 행 삭제. 반환: 삭제 행 수."""
        floor = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        result = session.execute(delete(StockInvestorDaily).where(StockInvestorDaily.ymd < floor))
        return result.rowcount or 0

    def select_latest(self, session, stock_code: str):
        """종목의 가장 최근 영업일 행(dict) 또는 None."""
        row = session.execute(
            select(StockInvestorDaily)
            .where(StockInvestorDaily.stock_code == stock_code)
            .order_by(StockInvestorDaily.ymd.desc())
            .limit(1)
        ).scalars().first()
        return row.to_dict() if row else None
