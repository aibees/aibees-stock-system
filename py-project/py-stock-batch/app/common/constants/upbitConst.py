class UpbitConstant:
    def __init__(self):
        self.upbit_balance_column = [
            { 'code': 'currency', 
              'name': '코인' },
            { 'code': 'balance', 
              'name': '보유량' },
            { 'code': 'avg_buy_price', 
              'name': '평균 매수가' },
            { 'code': 'avg_buy_price_modified', 
              'name': '평단가 조정여부' },
            { 'code': 'unit_currency', 
              'name': '매수 기준통화' }
        ]

        self.upbit_ohlcv = [
            { 'code': 'Datetime',
              'name': '시간' },
            { 'code': 'Open',
              'name': '시가' },
            { 'code': 'High',
              'name': '고가' },
            { 'code': 'Low',
              'name': '저가' },
            { 'code': 'Close',
              'name': '종가' },
            { 'code': 'Volume',
              'name': '거래량' },
        ]

        self.upbit_coin_indicator = [
            { 'code': 'BB_Upper',
              'name': '볼린져 상한선' },
            { 'code': 'BB_Middle',
              'name': '볼린져 중앙' },
            { 'code': 'BB_Lower',
              'name': '볼린져 하한선' },
            { 'code': '',
              'name': '' },
        ]


upbitConstant = UpbitConstant()