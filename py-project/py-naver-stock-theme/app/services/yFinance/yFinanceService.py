import yfinance as yf
import pandas as pd
import json

from app.domains.dao.masterStockDao import MasterStockDao

class YFinanceService:
    def __init__(self):
        self.__name__ = 'YFinanceService'
        self.masterStockDao = MasterStockDao()
        
    def getStockChartData(self, session, param):
        stock_info = self.masterStockDao.select_master_stock_by_id(session, param)
        
        yf_code = stock_info['stock_code'] + '.' + stock_info['stock_type_yf']
        ticker = yf.Ticker(yf_code)
        df = ticker.history(period="241d")
        
        df = df.reset_index()
        df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(lambda col: col.astype(int))
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        df2 = df[['Date', 'Open', 'High', 'Low', 'Close']].copy()
        df2.rename(columns={'Date': 'x', 'Open': 'o', 'High': 'h', 'Low': 'l', 'Close': 'c'}, inplace = True)
        df2 = df2.to_dict(orient='records')

        df['ma5']  = df['Close'].rolling(window=5).mean().fillna(0).apply(int)
        df['ma20'] = df['Close'].rolling(window=20).mean().fillna(0).apply(int)
        df['ma60'] = df['Close'].rolling(window=60).mean().fillna(0).apply(int)
        df['ma120'] = df['Close'].rolling(window=120).mean().fillna(0).apply(int)
        
        ma005 = [{'x': row['Date'], 'y': row['ma5']} for index, row in df.iterrows()]
        
        ma020 = [{'x': row['Date'], 'y': row['ma20']} for index, row in df.iterrows()]
        
        ma060 = [{'x': row['Date'], 'y': row['ma60']} for index, row in df.iterrows()]
        
        ma120 = [{'x': row['Date'], 'y': row['ma120']} for index, row in df.iterrows()]
        
        volume = [{'x': row['Date'], 'y': row['Volume']} for index, row in df.iterrows()]
        
        df_date = df[['Date']].to_dict(orient='list')
        
        return {
            'ohcl': df2,
            'volume': volume,
            'ma5': ma005,
            'ma20': ma020,
            'ma60': ma060,
            'ma120': ma120,
            'date': df_date
        }
        