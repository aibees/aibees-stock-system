import pandas as pd

from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from stock_shared.dao.tradeBuyTargetChartDao import TradeBuyTargetChartDao
from stock_shared.dao.tradeBuyTargetPriorityDao import TradeBuyTargetPriorityDao
from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao
from app.ext_services.kis.KisEngine import KisEngine
from app.services.stocks.StockModService import StockModService
from app.utils.constants.Literal import Literal
from datetime import datetime, timedelta


class StockService:

    def __init__(self):
        self.buyTargetStockDaoImpl = TradeBuyTargetStockDao()
        self.buyTargetChartDaoImpl = TradeBuyTargetChartDao()
        self.buyTargetPriorityDaoImpl = TradeBuyTargetPriorityDao()
        self.masterStockDaoImpl = MasterStockDao()
        self.investorDaoImpl = StockInvestorDailyDao()
        self.modService = StockModService()
        self.kis = KisEngine(virtual=False)

    def get_buy_target_stock_list(self, session, ymd):
        results = self.buyTargetStockDaoImpl.select_trade_buy_target_daily(session, ymd)
        if not results:
            return results

        # 전 종목이 같은 날짜(ymd 미지정 시 DAO가 자동 resolve한 최신 영업일)이므로
        # 첫 행의 ymd로 차트 데이터를 한 번에 조회해 붙인다(종목별 N회 조회 대신).
        resolved_ymd = results[0]["ymd"]
        chart_map = self.buyTargetChartDaoImpl.select_by_ymd(session, resolved_ymd)
        for item in results:
            item["chart_data"] = chart_map.get(item["stock_code"], [])

        # 시가총액·투자자 수급 — 추천일 이하 가장 최근 영업일 기준(20:00 추천 → 다음 날 07:10 그날 수급 적재).
        # 부가 정보라 실패해도 추천 목록은 그대로 내려준다.
        try:
            self.attach_market_info(session, results, resolved_ymd)
        except Exception as e:
            print(f"[buy-target] 시가총액·수급 조회 실패: {e}", flush=True)
        return results

    def attach_market_info(self, session, items: list, max_ymd: str = None) -> None:
        """
        items(각 dict 에 stock_code) 에 시가총액·투자자 순매수를 붙인다(제자리 수정).
          investor_ymd                 : 수급·종가 기준 영업일 (YYYYMMDD)
          frgn_amt / orgn_amt / prsn_amt : 외국인 / 기관계 / 개인 순매수 대금(백만원)
          frgn_qty / orgn_qty / prsn_qty : 순매수 수량(주)
          market_cap                   : 시가총액(억원) = 상장주식수 × investor_ymd 종가
        데이터가 없으면 None. 매수추천 목록(/buy-target)·종목 단건(/id/<code>) 공용.
        """
        codes = [it["stock_code"] for it in items if it.get("stock_code")]
        inv_map = self.investorDaoImpl.select_latest_by_codes(session, codes, max_ymd)
        shares_map = self.masterStockDaoImpl.select_listed_shares(session, codes)
        for it in items:
            inv = inv_map.get(it.get("stock_code"))
            shares = shares_map.get(it.get("stock_code"))
            it["investor_ymd"] = inv["ymd"] if inv else None
            for k in ("frgn_amt", "orgn_amt", "prsn_amt", "frgn_qty", "orgn_qty", "prsn_qty"):
                it[k] = inv.get(k) if inv else None
            # 종가는 수급과 같은 날 값 우선. 수급이 아직 없으면(배치 전·신규 종목) 행 자신의 종가(매수추천 close)로.
            close = (inv.get("close_price") if inv else None) or self._to_number(it.get("close"))
            it["market_cap"] = round(shares * close / 100_000_000) if shares and close else None

    @staticmethod
    def _to_number(v):
        try:
            n = float(v)
            return n if n > 0 else None
        except (TypeError, ValueError):
            return None

    # ────────────────────────────────────────────────────────────────
    # 최우선타겟 (Home.vue 매수추천 카드 select) — 유저당 1건, 날짜 무관.
    # worker(BuyExecutor1)가 다음 영업일 정규장 라운드에서 읽어 소비(1회성 null화)한다.
    # ────────────────────────────────────────────────────────────────
    def get_priority_target(self, session, user_id: int):
        return self.buyTargetPriorityDaoImpl.select_by_user_id(session, user_id)

    def set_priority_target(self, session, user_id: int, ymd: str, stock_code: str):
        """지정 전, 그 ymd 매수타겟 목록에 실제 존재하는 종목인지 검증한다
        (프론트가 sortedData 밖의 값을 보낼 리 없지만 방어적으로 한 번 더 막는다).
        검증 실패 시 ValueError를 던진다 — 라우터가 400 으로 변환."""
        found = self.buyTargetStockDaoImpl.exists_stock_on_ymd(session, ymd, stock_code)
        if not found:
            raise ValueError(f"{ymd} 매수타겟 목록에 없는 종목입니다: {stock_code}")
        self.buyTargetPriorityDaoImpl.upsert(
            session, user_id, stock_code, found["stock_name"], ymd
        )
        return {"stock_code": stock_code, "stock_name": found["stock_name"], "set_ymd": ymd}

    def clear_priority_target(self, session, user_id: int):
        self.buyTargetPriorityDaoImpl.clear(session, user_id)

    def get_target_rec_record(self, session, params):
        stock_code = params.get(Literal.STOCK_CODE, None)
        rec_recent_record = self.buyTargetStockDaoImpl.select_trade_recent_record(session, params)

        today = datetime.today()

        if rec_recent_record is None:
            # 3개월 데이터
            date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")

            ohlcv = self.kis.getOHLCV(stock_code, date_from, date_to)
            if ohlcv is None or ohlcv.empty:
                # 거래정지(master_stock.market_stop) 등으로 시세가 없으면 400 대신 '데이터 없음'.
                # (예전엔 예외 → 400 → 화면이 빈 객체로 렌더돼 TypeError)
                return None

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
            if ohlcv is None or ohlcv.empty or not rec_close:
                return None
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
                    'rate': round((int(max_row[Literal.CLOSE]) - int(rec_close)) / int(rec_close) * 100, 2)
                },
                'now_record': {
                    Literal.YMD: today_row[Literal.YMD][:10],
                    Literal.CLOSE: int(today_row[Literal.CLOSE]),
                    'rate': round((int(today_row[Literal.CLOSE]) - int(rec_close)) / int(rec_close) * 100, 2)
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

        ohlcv:pd.DataFrame = self.kis.get_ohlcv_period_unit(stock_code, 200, unit=period or "day")

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
