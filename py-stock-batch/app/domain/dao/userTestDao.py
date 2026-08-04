from app.domain.model.batchBackTestLog import TradeLog
from app.domain.model.userInterestGroups import UserInterestGroups
from app.domain.model.userInterestStocks import UserInterestStocks
from app.domain.model.userWallet import UserWallet

from sqlalchemy import select, update, and_, func, desc, delete, insert


class UserTestDao:
    def __init__(self):
        self.__name__ = 'UserTestDao'

    def select_user_test_wallet(self, session, data):
        stmt = select(
            UserWallet
        ).where(
            UserWallet.user_id == data['user_id']
        )

        result = session.execute(stmt).scalar()

        return result.to_dict()

    def update_user_wallet(self, session, data):
        stmt = update(UserWallet).where(
            UserWallet.user_id == data['user_id']
        ).values(
            user_balance=data['user_balance']
        )

        session.execute(stmt)
        session.commit()

    def update_user_interest_stocks(self, session, data):
        interest_groups = select(UserInterestGroups).where(
            UserInterestGroups.user_id == data['user_id'],
            UserInterestGroups.division == data['division']
        )

        group_result = session.execute(interest_groups).scalar()

        stmt = update(UserInterestStocks).where(
            UserInterestStocks.group_id == group_result.group_id,
            UserInterestStocks.stock_code == data['coin_code']
        ).values(
            status=data['status'],
            curr_balance=data['curr_balance']
        )
        session.execute(stmt)
        session.commit()

    def insert_trade_log(self, session, data):

        def getv(k, default=None):
            if isinstance(data, dict):
                return data.get(k, default)
            return getattr(data, k, default)

        stmt = insert(TradeLog).values(
            user_id=data['user_id'],
            coin_symbol=getv("coin_symbol"),
            action_type=getv("action_type"),
            order_time=getv("order_time"),
            exec_time=getv("exec_time"),

            price=getv("price"),
            quantity=getv("quantity"),
            total_amount=getv("total_amount"),

            remain_qty=getv("remain_qty", 0),
            fee=getv("fee", 0),
            pnl=getv("pnl", 0),
            krw_balance=getv("krw_balance", 0),

            sma_checker=getv("sma_checker", 0),
            rsi_checker=getv("rsi_checker", 0),
            macd_checker=getv("macd_checker", 0),
            stk_checker=getv("stk_checker", 0),
            obv_checker=getv("obv_checker", 0),
            score=getv("score", 0),

            note=getv("note"),
        )

        session.execute(stmt)