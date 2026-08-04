import pprint
from datetime import datetime, timedelta

import pandas as pd
import pykis
from pykis import KisAuth, PyKis, KisStock
from pykis.api.stock.chart import KisChart

import json

from pykis.api.stock.quote import KisQuoteResponse

from app.config.db.database import dbConn
from app.domains.dao.userDetailDao import UserDetailDao
from app.utils.constants.Literal import Literal

# 실투자 KIS 인증정보를 조회할 user_detail 의 user_id (단일계정 고정)
_KIS_USER_ID = 1


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

        self.kis = None

        if virtual:
            # 모의투자: 기존 파일(kis.key) 방식 유지
            keys = self._load_keys_from_file(key_path)
            self.id = keys.get("id")
            self.account = keys.get("virtual_account")
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
            # 실투자: DB(user_detail) 에서 인증정보 조회
            keys = self._load_keys_from_db(_KIS_USER_ID)
            self.id = keys.get("id")
            self.account = keys.get("account")
            self.kis = PyKis(
                id=self.id,
                account=self.account,
                appkey=keys.get("app_key"),
                secretkey=keys.get("sec_key"),
                keep_token=True
            )

        self._initialized = True

    # ── 헬퍼 ─────────────────────────────────────────────────
    @staticmethod
    def _resolve_market(code: str) -> str:
        """6자리 숫자 → 'KR', 그 외(영문 등) → 'US'"""
        return "KR" if (len(code) == 6 and code.isdigit()) else "US"

    # ── 인증정보 로더 ────────────────────────────────────────
    @staticmethod
    def _load_keys_from_file(key_path: str) -> dict:
        """모의투자용 kis.key 파일에서 설정값을 읽어옵니다."""
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"{key_path} 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        except json.JSONDecodeError:
            raise ValueError(f"{key_path} 파일의 JSON 형식이 올바르지 않습니다.")

    @staticmethod
    def _load_keys_from_db(user_id: int) -> dict:
        """실투자용 인증정보를 user_detail 에서 조회합니다."""
        session = dbConn.get_session()
        try:
            keys = UserDetailDao().select_kis_credentials(session, user_id)
        finally:
            session.remove()

        if keys is None:
            raise ValueError(f"user_detail(user_id={user_id}) 레코드를 찾을 수 없습니다.")
        if not keys.get("app_key") or not keys.get("sec_key"):
            raise ValueError(f"user_detail(user_id={user_id})에 KIS 인증키가 설정되지 않았습니다.")
        if not keys.get("id") or not keys.get("account"):
            raise ValueError(f"user_detail(user_id={user_id})에 kis_id/kis_account가 설정되지 않았습니다.")
        return keys

    # 봉 단위별 '캔들 1개당 대략 캘린더 일수' 배수.
    # period(원하는 캔들 개수)에 곱해 조회 윈도우(timedelta)를 산출한다.
    #  - day: 주말/공휴일 보정 위해 1.6배
    #  - week/month/year: 캔들당 캘린더 일수에 약간의 버퍼
    _UNIT_DAY_FACTOR = {
        "day": 1.6,
        "week": 7.5,
        "month": 31,
        "year": 366,
    }

    def get_ohlcv_period(self, code: str, period: int = 200) -> pd.DataFrame:
        """일봉 OHLCV 조회 (기본). 내부적으로 unit='day'로 위임."""
        return self.get_ohlcv_period_unit(code, period, unit="day")

    def get_ohlcv_period_unit(
        self, code: str, period: int = 200, unit: str = "day"
    ) -> pd.DataFrame:
        """
        일/주/월/년 단위 OHLCV 캔들을 조회한다.

        period: 가져올 캔들 개수(근사). unit: 'day' | 'week' | 'month' | 'year'.
        pykis는 period(int)를 '당일 분봉 간격'으로 해석하므로, 기간 차트는
        start(timedelta) + period(단위 문자열) 조합으로 요청한다.
        """
        unit = (unit or "day").lower()
        if unit not in self._UNIT_DAY_FACTOR:
            raise ValueError(
                f"지원하지 않는 unit='{unit}'. (day|week|month|year 중 하나)"
            )

        try:
            stock: KisStock = self.kis.stock(symbol=code, market=self._resolve_market(code))

            window_days = int(float(period) * self._UNIT_DAY_FACTOR[unit])
            chart: KisChart = stock.chart(
                start=timedelta(days=window_days),
                period=unit,
            )
            return self.__produce_data(chart)

        except pykis.responses.exceptions.KisNotFoundError as nfe :
            return None



    def getOHLCV(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        try :
            stock: KisStock = self.kis.stock(symbol=code, market=self._resolve_market(code))

            # 날짜 변환 및 데이터 조회 (end_date 오타 수정)
            chart: KisChart = stock.chart(
                start=datetime.strptime(start_date, "%Y-%m-%d"),
                end=datetime.strptime(end_date, "%Y-%m-%d")
            )
            return self.__produce_data(chart)

        except pykis.responses.exceptions.KisNotFoundError as nfe :
            return None


    def __produce_data(self, chart: KisChart) -> pd.DataFrame:
        raw_df: pd.DataFrame = chart.df().tail(350)

        df = raw_df.rename(columns={'time': 'datetime'})
        df[Literal.YMD] = (
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

    def get_finance_info(self, code: str):
        quote: KisQuoteResponse = self.kis.stock(symbol=code, market=self._resolve_market(code)).quote()
        fin_info = quote.indicator

        result = {
            'eps': str(fin_info.eps),
            'per': str(fin_info.per),
            'pbr': str(fin_info.pbr),
            'roe': str(round(fin_info.pbr / fin_info.per, 2)),
            'peg': str(round(fin_info.per / fin_info.eps, 2))
        }

        return result
