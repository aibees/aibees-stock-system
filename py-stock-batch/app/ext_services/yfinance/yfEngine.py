import pandas as pd
import yfinance as yf

class yfEngine:
    def __init__(self):
        self.__name__ = 'yfEngine'
        pd.set_option('display.max_rows', None)
        pd.set_option('display.precision', 0)

    def getOHLCV(self, symbol: str, start_date: str, end_date: str, interval: str='1d') -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        raw_df = ticker.history(start=start_date, end=end_date, interval=interval, auto_adjust=False)
        raw_df.reset_index(inplace=True)


        df = raw_df[['Date', 'Open', 'High', 'Low', 'Adj Close', 'Volume']]
        df.rename(columns={'Date': 'datetime', 'Adj Close': 'close'}, inplace=True)
        df.columns = [col.lower() for col in df.columns]

        df['datetime'] = (
            pd.to_datetime(df['datetime'], unit='ms')
            .dt.tz_convert('Asia/Seoul')
            .dt.strftime('%Y-%m-%d %H:%M:%S')
        )
        df['open'] = df['open'].astype(int)
        df['high'] = df['high'].astype(int)
        df['low'] = df['low'].astype(int)
        df['close'] = df['close'].astype(int)
        df['volume'] = df['volume'].astype(int)

        return df

