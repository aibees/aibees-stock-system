
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
from datetime import datetime, timedelta
import logging

from app.domains.models.tradeBuyTargetStock import TradeBuyTargetStock
from app.utils.constants.Literal import Literal

logging.basicConfig(level=logging.ERROR)


class TradeBuyTargetStockDao:
    def __init__(self):
        self.__name__ = 'TradeBuyTargetStockDao'

    def select_trade_buy_target_daily(self, session, data: dict):
        ymd = data.get(Literal.YMD, datetime.today().strftime(Literal.ISO_DATE_FORMAT))

        stmt = select(
            TradeBuyTargetStock
        ).where(
            TradeBuyTargetStock.ymd == ymd
        ).order_by(
            TradeBuyTargetStock.rank_no
        )

        results = session.execute(stmt).scalars().all()
        return [item.to_dict() for item in results]


    def select_trade_recent_record(self, session, data: dict) -> dict:
        stock_code = data.get(Literal.STOCK_CODE, None)
        today = datetime.today()
        date_from = (today - timedelta(days=30)).strftime("%Y%m%d")
        date_to   = (today - timedelta(days=1)).strftime("%Y%m%d")

        if not stock_code:
            raise Exception("no stock code")

        stmt = select(
            TradeBuyTargetStock
        ).where(
            TradeBuyTargetStock.stock_code == stock_code,
            TradeBuyTargetStock.ymd.between(date_from, date_to)
        ).order_by(
            TradeBuyTargetStock.ymd.desc()
        ).limit(1)

        results = session.execute(stmt).scalars().first()
        return results.to_dict() if results else None

