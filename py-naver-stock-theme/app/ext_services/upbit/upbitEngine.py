from datetime import datetime, timedelta

import ccxt
import pandas as pd

pd.options.display.float_format = '{:.5f}'.format


class CcxtUpbit:
    def __init__(self, access, secret):
        self.exchange = ccxt.upbit(config={
            'apiKey': access,
            'secret': secret,
            'enableRateLimit': False
        })
        self.exchange.options['createMarketBuyOrderRequiresPrice'] = False

    def get_current_balance(self, coin=None):
        balance_ticker = self.exchange.fetch_balance()

        if coin is not None:
            return balance_ticker[coin]
        else:
            return balance_ticker
