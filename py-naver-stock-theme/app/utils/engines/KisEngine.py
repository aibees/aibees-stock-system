import pprint
from datetime import datetime

import pandas as pd
import pykis
from pykis import KisAuth, PyKis, KisStock
from pykis.api.stock.chart import KisChart

import json

from pykis.api.stock.quote import KisQuoteResponse


class KisEngine:
    # virtual 모드별 싱글톤 인스턴스 저장 (True: 모의투자, False: 실투자)
    _instances: dict = {}

    def __new__(cls, key_path: str = "kis.key", virtual: bool = True):
        if virtual not in cls._instances:
            cls._instances[virtual] = super().__new__(cls)
            cls._instances[virtual]._initialized = False
        return cls._instances[virtual]

    def __init__(self, key_path: str = "kis.key", virtual: bool = True):
        # 이미 초기화된 인스턴스는 재초기화하지 않음
        if self._initialized:
            return

        # 1. 파일에서 설정값 읽어오기
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                keys = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"{key_path} 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        except json.JSONDecodeError:
            raise ValueError(f"{key_path} 파일의 JSON 형식이 올바르지 않습니다.")

        # 2. 계정 정보 설정
        self.id = keys.get("id")
        self.account = keys.get("virtual_account") if virtual else keys.get("account")
        self.kis = None

        # 3. PyKis 초기화
        if virtual:
            print("account : " + self.account)
            print(keys)

            self.kis = PyKis(
                id=self.id,
                account=self.account,
                appkey=keys.get("app_key"),
                secretkey=keys.get("sec_key"),
                virtual_id=keys.get("virtual_id"),
                virtual_appkey=keys.get("vir_app_key"),
                virtual_secretkey=keys.get("vir_sec_key"),
                keep_token=True
            )
        else:
            self.kis = PyKis(
                id=self.id,
                account=self.account,
                appkey=keys.get("app_key"),
                secretkey=keys.get("sec_key"),
                keep_token=True
            )

        self._initialized = True

    def getOHLCV(self, code: str, start_date: str, end_date: str):
        try :
            stock: KisStock = self.kis.stock(symbol=code, market="KR")

            # 날짜 변환 및 데이터 조회 (end_date 오타 수정)
            chart: KisChart = stock.chart(
                start=datetime.strptime(start_date, "%Y-%m-%d"),
                end=datetime.strptime(end_date, "%Y-%m-%d")
            )

            raw_df: pd.DataFrame = chart.df()
            df = raw_df.rename(columns={'time': 'datetime'})
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
        except pykis.responses.exceptions.KisNotFoundError as nfe :
            return None

    def get_finance_info(self, code: str):
        quote: KisQuoteResponse = self.kis.stock(symbol=code, market="KR").quote()
        fin_info = quote.indicator

