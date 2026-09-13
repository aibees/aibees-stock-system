import json
import logging

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.models.tradeBuyTargetChart import TradeBuyTargetChart

logging.basicConfig(level=logging.ERROR)


class TradeBuyTargetChartDao:
    def __init__(self):
        self.__name__ = "TradeBuyTargetChartDao"

    # ------------------------------------------------------------------
    # select
    # ------------------------------------------------------------------
    def select_by_ymd(self, session, ymd: str) -> dict:
        """해당 일자 전 종목의 차트데이터를 한 번에 조회.

        반환: {stock_code: [{date, open, high, low, close, volume, ma20, ma60}, ...]}
        (읽는 쪽은 항상 그 날짜의 buy-target 리스트 전체에 붙여야 하므로 종목별 N번
        조회 대신 ymd 하나로 일괄 조회한다.)
        """
        stmt = select(TradeBuyTargetChart).where(TradeBuyTargetChart.ymd == ymd)
        rows = session.execute(stmt).scalars().all()
        result = {}
        for row in rows:
            try:
                result[row.stock_code] = json.loads(row.chart_data)
            except (TypeError, ValueError):
                result[row.stock_code] = []
        return result

    # ------------------------------------------------------------------
    # insert / delete
    # ------------------------------------------------------------------
    def delete_by_ymd(self, session, ymd: str) -> int:
        """해당 일자 전체 삭제(배치 재실행 시 clean_buy_target_stock_by_ymd 와 짝으로 호출)."""
        return (
            session.query(TradeBuyTargetChart)
            .filter(TradeBuyTargetChart.ymd == ymd)
            .delete()
        )

    def upsert_bulk(self, session, data_list: list[dict]):
        """ymd + stock_code 기준 Upsert.

        data_list: [{'ymd':.., 'stock_code':.., 'chart_data': [...]}, ...]
        chart_data 는 파이썬 list(JSON 직렬화는 여기서 처리).
        """
        if not data_list:
            logging.info("Upsert할 차트 데이터가 없습니다.")
            return

        for d in data_list:
            row = {
                "ymd": d["ymd"],
                "stock_code": d["stock_code"],
                "chart_data": json.dumps(d["chart_data"], ensure_ascii=False),
            }
            stmt = insert(TradeBuyTargetChart).values(row)
            upsert_stmt = stmt.on_duplicate_key_update(chart_data=stmt.inserted.chart_data)
            session.execute(upsert_stmt)
