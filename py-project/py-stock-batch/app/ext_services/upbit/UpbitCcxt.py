from datetime import datetime, timedelta

import ccxt, pprint, traceback, copy
import pandas as pd

pd.options.display.float_format = '{:.5f}'.format

class CcxtUpbit:
    def __init__(self, access, secret):
        self.exchange = ccxt.upbit(config = {
            'apiKey': access,
            'secret': secret,
            'enableRateLimit': False
        })
        self.exchange.options['createMarketBuyOrderRequiresPrice'] = False

    def getOHLCV(self, symbol, timeframe):
        since = None

        if timeframe.endswith('h'):
            since = (datetime.today() - timedelta(hours=200 * int(str(timeframe)[:-1]))).strftime("%Y-%m-%dT%H-%M-%S")

        elif timeframe.endswith('m'):
            since = (datetime.today() - timedelta(minutes=200 * int(str(timeframe)[:-1]))).strftime("%Y-%m-%dT%H-%M-%S")

        elif timeframe.endswith('d'):
            since = (datetime.today() - timedelta(days=200 * int(str(timeframe)[:-1]))).strftime("%Y-%m-%dT%H-%M-%S")

        return self.__getOHLCV(symbol, timeframe, since)

    def getOHLCVWithSince(self, symbol, timeframe, since):
        return self.__getOHLCV(symbol, timeframe, since)

    def __getOHLCV(self, symbol, timeframe, since):
        try:
            symbol_str = copy.deepcopy(symbol)
            if len(symbol_str.split('/')) < 2:
                symbol_str = symbol_str + '/KRW'

            data = self.exchange.fetch_ohlcv(symbol_str, timeframe=timeframe, since=since)
            df = pd.DataFrame(data, columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df.columns = [col.lower() for col in df.columns]

            df['datetime'] = (
                pd.to_datetime(df['datetime'], unit='ms')
                .dt.tz_localize('UTC')
                .dt.tz_convert('Asia/Seoul')
                .dt.strftime('%Y-%m-%d %H:%M:%S')
            )

            return df.sort_values('datetime', ignore_index=True)
        except Exception as e:
            traceback.print_exc()
            return None


    def get_current_balance(self, coin=None):
        balance_ticker = self.exchange.fetch_balance()

        if coin is not None:
            return balance_ticker[coin]
        else:
            return balance_ticker

    def get_current_close_value(self, coin):
        balance_ticker = self.exchange.fetch_ticker(f'{coin}/KRW')
        return balance_ticker['close']

    def create_order(self, type, coin, amount):
        # 빠른 대응을 위해 시장가로만 매수 / 매도
        self.exchange.options['createMarketBuyOrderRequiresPrice'] = False
        resp = None
        if type == 'BUY':
            resp = self.exchange.create_market_buy_order(
                symbol=coin,
                amount=(amount * 0.99)
            )
        
        elif type == 'SELL': 
            resp = self.exchange.create_market_sell_order(
                symbol=coin,
                amount=amount
            )
        
        else:
            return None

        return resp