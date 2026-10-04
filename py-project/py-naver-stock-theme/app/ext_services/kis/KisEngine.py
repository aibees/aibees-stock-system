import pprint
from datetime import datetime, timedelta

import pandas as pd
import pykis
from pykis import KisStock
from pykis.api.stock.chart import KisChart

from pykis.api.stock.quote import KisQuoteResponse

from app.utils.constants.Literal import Literal
from stock_shared.kis.client import create_pykis
from stock_shared.kis.credentials import load_creds_from_db, load_creds_from_file

# 실투자 KIS 인증정보를 조회할 기본 user_detail.user_id.
# user_id 를 명시하지 않은 기존 호출부(KisEngine(virtual=False)) 는 계속 이 계정을 쓴다.
_KIS_USER_ID = 1


class KisEngine:
    # 싱글톤 인스턴스 저장. 키는 (virtual, user_id) 다.
    #   PyKis 생성은 토큰 준비를 수반하고 발급은 KIS 가 1분 1회로 제한(EGW00133)하므로
    #   같은 계정으로는 프로세스당 1개만 두어야 한다.
    #   예전엔 키가 virtual(bool) 하나였는데, 그러면 실투자 인스턴스가 **계정 1개**로
    #   굳어 유저별 조회(매매손익 화면 등)를 할 수 없다. 그래서 user_id 를 키에 넣는다.
    #   모의투자(virtual=True)는 kis.key 파일 기반이라 user_id 가 의미 없으므로 None 으로 정규화한다.
    _instances: dict = {}

    @staticmethod
    def _cache_key(virtual: bool, user_id):
        return (virtual, None if virtual else int(user_id or _KIS_USER_ID))

    def __new__(cls, key_path: str = "kis.key", virtual: bool = True, user_id=None):
        key = cls._cache_key(virtual, user_id)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
            cls._instances[key]._initialized = False
        return cls._instances[key]

    def __init__(self, key_path: str = "kis.key", virtual: bool = True, user_id=None):
        # 이미 초기화된 인스턴스는 재초기화하지 않음
        if self._initialized:
            return

        # 이 인스턴스가 어느 계정인지 남겨둔다(로그/디버깅용). 모의투자는 None.
        self.user_id = None if virtual else int(user_id or _KIS_USER_ID)

        self.kis = None

        if virtual:
            # 모의투자: 기존 파일(kis.key) 방식 유지
            keys = load_creds_from_file(key_path)
            self.id = keys.get("id")
            self.account = keys.get("virtual_account")
            self.kis = create_pykis(
                id=self.id,
                account=self.account,
                app_key=keys.get("app_key"),
                sec_key=keys.get("sec_key"),
                virtual_id=keys.get("virtual_id"),
                virtual_app_key=keys.get("vir_app_key"),
                virtual_sec_key=keys.get("vir_sec_key"),
            )
        else:
            # 실투자: DB(user_detail) 에서 이 인스턴스 계정의 인증정보 조회
            # strict=True + 파일 폴백 없음 — 키가 없는 유저가 다른 계좌를 보게 되는 경로가
            # 애초에 없어야 하는 앱이다(router_profit 이 이 예외를 400 으로 바꾼다).
            # legacy_fallback: 사용자 설정 화면이 아직 kis_access_key/kis_secret_key 에 쓰므로
            # 화면에서 등록한 키를 계속 읽는다(credentials 모듈 docstring 참고). 임시 옵션이다.
            keys = load_creds_from_db(self.user_id, strict=True, legacy_fallback=True)
            self.id = keys.get("id")
            self.account = keys.get("account")
            self.kis = create_pykis(
                id=self.id,
                account=self.account,
                app_key=keys.get("app_key"),
                sec_key=keys.get("sec_key"),
            )

        self._initialized = True

    # ── 헬퍼 ─────────────────────────────────────────────────
    @staticmethod
    def _resolve_market(code: str) -> str:
        """6자리 숫자 → 'KR', 그 외(영문 등) → 'US'"""
        return "KR" if (len(code) == 6 and code.isdigit()) else "US"

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

    # 종합 시황/공시(제목) [국내주식-141] — 전체 시황 피드를 주므로 stock_code(iscd1)로
    # 클라이언트 필터링한다. 매칭 결과가 없으면 종목명으로 제목 검색(FID_TITL_CNTT)을
    # 한 번 더 시도해 적중률을 보완한다.
    def get_news_title(self, code: str, stock_name: str = None, count: int = 8) -> list:
        matched = self.__fetch_news_title(fid_input_iscd=code)
        matched = [row for row in matched if row.get('iscd1') == code]

        if not matched and stock_name:
            matched = self.__fetch_news_title(fid_titl_cntt=stock_name)

        return [
            {
                'title': row.get('hts_pbnt_titl_cntt', ''),
                'source': row.get('dorg', ''),
                'date': row.get('data_dt', ''),
                'time': row.get('data_tm', ''),
            }
            for row in matched[:count]
        ]

    def __fetch_news_title(self, fid_input_iscd: str = '', fid_titl_cntt: str = '') -> list:
        now = datetime.now()
        resp = self.kis.fetch(
            '/uapi/domestic-stock/v1/quotations/news-title',
            api='FHKST01011800',
            params={
                'FID_NEWS_OFER_ENTP_CODE': '',
                'FID_COND_MRKT_CLS_CODE': '',
                'FID_INPUT_ISCD': fid_input_iscd,
                'FID_TITL_CNTT': fid_titl_cntt,
                'FID_INPUT_DATE_1': now.strftime('%Y%m%d'),
                'FID_INPUT_HOUR_1': now.strftime('%H%M%S'),
                'FID_RANK_SORT_CLS_CODE': '',
                'FID_INPUT_SRNO': '',
            },
        )
        return resp.__response__.json().get('output', [])

    # ──────────────────────────────────────────────────────────────────
    # 기간별매매손익현황조회 (inquire-period-trade-profit / TTTC8715R)
    #   HTS [0856] 기간별 매매손익 > "종목별" 과 같은 데이터. 실현손익(매도 확정분)
    #   이라 보유 중 평가손익(MyWallet 의 user_holdings)과는 성격이 다르다.
    #
    #   pykis 에도 domestic_order_profits() 래퍼가 있지만 쓰지 않는다 —
    #   KisDomesticOrderProfit 이 매핑하는 필드가 pdno/prdt_name/pchs_unpr/
    #   sll_pric/sll_amt/sll_qty 뿐이고, profit 을 sell_amount - buy_amount 로
    #   **직접 계산**한다. 그 값은 수수료·제세금이 빠지지 않은 총액이라 KIS 가
    #   내려주는 rlzt_pfls(실현손익)와 다르다. 손익조회 화면이 보여줘야 하는 건
    #   세후 실현손익이므로 fee/tl_tax/rlzt_pfls/pfls_rt 와 output2 합계
    #   (tot_rlzt_pfls/tot_pftrt 등)를 그대로 받으려면 직접 호출해야 한다.
    #   (broker.py 의 orderable() 이 pykis 래퍼를 쓰지 않는 것과 같은 이유)
    #
    #   모의투자 미지원 API 다. 이 엔진 자체가 실전 전용이라 추가 분기는 두지 않는다.
    # ──────────────────────────────────────────────────────────────────
    _PROFIT_PATH = "/uapi/domestic-stock/v1/trading/inquire-period-trade-profit"
    _PROFIT_TR_ID = "TTTC8715R"
    # 연속조회 안전장치. 1페이지 ≈ 20~30행이라 정상 조회면 한참 전에 끝난다.
    # tr_cont 가 끝없이 M 로 오는 이상 응답에 매달려 워커 스레드를 붙잡지 않도록
    # 상한을 둔다(상한에 걸리면 truncated=True 로 알린다).
    _PROFIT_MAX_PAGES = 50

    def get_period_trade_profit(self, start_ymd: str, end_ymd: str,
                                symbol: str | None = None,
                                sort_dvsn: str = "00") -> dict | None:
        """기간별 실현손익. 성공 시 {'rows': [...], 'summary': {...},
        'truncated': bool}, 실패 시 None.

        start_ymd / end_ymd 는 'YYYYMMDD'. symbol 이 None/빈값이면 전체 종목.
        sort_dvsn: '00' 최근순 / '01' 과거순.
        """
        account = self.kis.primary   # KisAccountNumber (CANO / ACNT_PRDT_CD)
        rows: list[dict] = []
        summary: dict = {}
        ctx_fk = ""
        ctx_nk = ""
        tr_cont = ""
        truncated = False

        for page in range(self._PROFIT_MAX_PAGES):
            try:
                resp = self.kis.request(
                    self._PROFIT_PATH,
                    method="GET",
                    params={
                        "CANO": account.number,
                        "ACNT_PRDT_CD": account.code,
                        "PDNO": symbol or "",       # 공란 = 전체 종목
                        "INQR_STRT_DT": start_ymd,
                        "INQR_END_DT": end_ymd,
                        "SORT_DVSN": sort_dvsn,
                        "CBLC_DVSN": "00",          # 00 = 전체
                        "CTX_AREA_FK100": ctx_fk,
                        "CTX_AREA_NK100": ctx_nk,
                    },
                    # tr_cont 는 1페이지에선 공백, 2페이지부터 'N'(다음 데이터 조회).
                    headers={"tr_id": self._PROFIT_TR_ID, "custtype": "P",
                             "tr_cont": tr_cont},
                    appkey_location="header", auth=True,
                )
                j = resp.json()
            except Exception as e:  # noqa: BLE001
                print(f"[get_period_trade_profit] 요청 실패(page={page}): {e}", flush=True)
                return None if page == 0 else {"rows": rows, "summary": summary,
                                               "truncated": True}

            if j.get("rt_cd") != "0":
                print(f"[get_period_trade_profit] rt_cd={j.get('rt_cd')} "
                      f"msg={j.get('msg1')}", flush=True)
                # 1페이지부터 실패면 조회 자체 실패. 중간이면 받은 만큼은 살린다.
                return None if page == 0 else {"rows": rows, "summary": summary,
                                               "truncated": True}

            rows.extend(j.get("output1") or [])
            # output2(합계)는 매 페이지에 같은 전체 합계가 실려 온다 — 마지막 값으로 덮어쓴다.
            if j.get("output2"):
                summary = j["output2"]

            # 응답 헤더 tr_cont: F/M = 다음 데이터 있음, D/E = 마지막.
            # 공백/누락이면 더 받을 게 없는 것으로 본다.
            resp_cont = (resp.headers.get("tr_cont") or "").strip().upper()
            if resp_cont not in ("F", "M"):
                break

            ctx_fk = (j.get("ctx_area_fk100") or "").strip()
            ctx_nk = (j.get("ctx_area_nk100") or "").strip()
            tr_cont = "N"
            if not ctx_nk:
                # 다음 데이터가 있다는데 연속조회키가 없으면 같은 페이지를 무한 반복하게 된다.
                break
        else:
            truncated = True
            print(f"[get_period_trade_profit] 연속조회 {self._PROFIT_MAX_PAGES}페이지 "
                  f"상한 도달 → 이후 데이터 생략", flush=True)

        return {"rows": rows, "summary": summary, "truncated": truncated}
