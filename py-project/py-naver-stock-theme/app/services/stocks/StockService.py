import pandas as pd

from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from app.ext_services.kis.KisEngine import KisEngine
from app.services.stocks.StockModService import StockModService
from app.utils.constants.Literal import Literal
from datetime import datetime, timedelta


class StockService:

    def __init__(self):
        self.buyTargetStockDaoImpl = TradeBuyTargetStockDao()
        self.modService = StockModService()
        self.kis = KisEngine(virtual=False)

    def get_buy_target_stock_list(self, session, ymd):
        return self.buyTargetStockDaoImpl.select_trade_buy_target_daily(session, ymd)

    def get_target_rec_record(self, session, params):
        stock_code = params.get(Literal.STOCK_CODE, None)
        rec_recent_record = self.buyTargetStockDaoImpl.select_trade_recent_record(session, params)

        today = datetime.today()

        if rec_recent_record is None:
            # 3개월 데이터
            date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")

            ohlcv = self.kis.getOHLCV(stock_code, date_from, date_to)
            if ohlcv is None:
                raise Exception("DF is NONE")

            last_row = ohlcv.iloc[0]
            max_row = ohlcv.loc[ohlcv[Literal.CLOSE].idxmax(), [Literal.YMD, Literal.CLOSE]]
            today_row = ohlcv.iloc[-1]

            return {
                'rec_record': {
                    Literal.YMD: last_row[Literal.YMD][:10],
                    Literal.CLOSE: int(last_row[Literal.CLOSE]),
                    'rate': 0.0
                },
                'max_record': {
                    Literal.YMD: max_row[Literal.YMD][:10],
                    Literal.CLOSE: int(max_row[Literal.CLOSE]),
                    'rate': round((int(max_row[Literal.CLOSE]) - int(last_row[Literal.CLOSE])) / int(last_row[Literal.CLOSE]) * 100, 2)
                },
                'now_record': {
                    Literal.YMD: today_row[Literal.YMD][:10],
                    Literal.CLOSE: int(today_row[Literal.CLOSE]),
                    'rate': round((int(today_row[Literal.CLOSE]) - int(last_row[Literal.CLOSE])) / int(last_row[Literal.CLOSE]) * 100, 2)
                }
            }

        else:
            # 추천당시 종가
            rec_close = rec_recent_record.get(Literal.CLOSE)
            date_from_form = datetime.strptime(rec_recent_record.get(Literal.YMD), '%Y%m%d')
            date_from = date_from_form.strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d")

            ohlcv:pd.DataFrame = self.kis.getOHLCV(stock_code, date_from, date_to)
            max_row = ohlcv.loc[ohlcv['close'].idxmax(), ['ymd', 'close']]
            today_row = ohlcv.iloc[-1]

            return {
                'rec_record': {
                    Literal.YMD: date_from,
                    Literal.CLOSE: int(rec_close),
                    'rate': 0.0
                },
                'max_record': {
                    Literal.YMD: max_row[Literal.YMD][:10],
                    Literal.CLOSE: int(max_row[Literal.CLOSE]),
                    'rate': round((int(max_row[Literal.CLOSE]) - int(rec_close)) / int(max_row[Literal.CLOSE]) * 100, 2)
                },
                'now_record': {
                    Literal.YMD: today_row[Literal.YMD][:10],
                    Literal.CLOSE: int(today_row[Literal.CLOSE]),
                    'rate': round((int(today_row[Literal.CLOSE]) - int(rec_close)) / int(max_row[Literal.CLOSE]) * 100, 2)
                }
            }


    def get_stock_chart_data(self, session, params):
        from datetime import datetime, timedelta
        stock_code = params.get(Literal.STOCK_CODE, None)
        # start_date = params.get('start_date', None)
        end_date = params.get('end_date', None)
        period = params.get('period', None)

        # if start_date:
        #     start_date = (datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=120)).strftime('%Y-%m-%d')

        ohlcv:pd.DataFrame = self.kis.get_ohlcv_period(stock_code, period)

        if ohlcv is None:
            raise Exception("DF is NONE")

        # OPEN, HIGH, CLOSE, LOW, VOLUME, SMA(5, 20, 60, 120), BB(UPPER, MID, LOWER) 들어있는 dataframe
        created:pd.DataFrame = self.modService.createAddChannel(ohlcv).tail(200)

        # datetime('%Y-%m-%d %H:%M:%S') → ymd('%Y-%m-%d')
        created[Literal.YMD] = created[Literal.YMD].str[:10]

        def to_xy(col):
            return [
                {
                    'x': str(row[Literal.YMD]),
                    'y': round(row[col], 2) if pd.notna(row[col]) else None}
                for _, row in created.iterrows()
            ]

        ohcl = [
            {
                'x': str(row[Literal.YMD]),
                'o': float(row[Literal.OPEN]),
                'h': float(row[Literal.HIGH]),
                'c': float(row[Literal.CLOSE]),
                'l': float(row[Literal.LOW]),
            }
            for _, row in created.iterrows()
        ]

        vol = [
            {
                'x': str(row[Literal.YMD]),
                'y': float(row[Literal.VOLUME]),
            } for _, row in created.iterrows()
        ]

        rate = [
            {
                'x': str(row[Literal.YMD]),
                'y': str(row['RATE'])
            } for _, row in created.iterrows()
        ]

        return {
            'ohcl':     ohcl,
            'volume':   vol,
            'rate':     rate,
            'ma5':      to_xy(Literal.SMA_5),
            'ma20':     to_xy(Literal.SMA_20),
            'ma60':     to_xy(Literal.SMA_60),
            'ma120':    to_xy(Literal.SMA_120),
            'bb_upper': to_xy(Literal.BB_UPPER),
            'bb_mid':   to_xy(Literal.BB_MID),
            'bb_lower': to_xy(Literal.BB_LOWER),
        }
