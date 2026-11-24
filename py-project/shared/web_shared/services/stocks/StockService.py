import logging
import pandas as pd

from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from stock_shared.dao.tradeBuyTargetBasicDao import TradeBuyTargetBasicDao
from stock_shared.reco_algo import merge_reco_sources
from stock_shared.dao.tradeBuyTargetChartDao import TradeBuyTargetChartDao
from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao
from web_shared.services.stocks import dailyBarSource
from web_shared.services.stocks.StockModService import StockModService
from stock_shared import chart_analysis
from web_shared.dao.masterCodesDao import MasterCodesDao
from web_shared.constants.Literal import Literal
from datetime import datetime, timedelta


class DbBarSource:
    """시세 출처 — DB 일봉(stock_ohlcv_daily, 전 거래일까지). 양봉상회 기본. 배치(StockOhlcvDailyJob)가 매일 적재한다."""

    def recent_bars(self, session, stock_code, count, unit):
        return dailyBarSource.recent_bars(session, stock_code, count, unit)

    def bars_between(self, session, stock_code, date_from, date_to):
        return dailyBarSource.bars_between(session, stock_code, date_from, date_to)


class StockService:
    """종목·매수추천·차트 공용 서비스(양봉상회·비밀상회 웹서버 공용, 2026-11-19 web_shared 로 옮김).

    bar_source : 차트·추천 기록의 시세 출처. recent_bars(session, code, count, unit)·bars_between(session, code, from, to)
                 를 가진 객체. 없으면 DB 일봉(DbBarSource). 비밀상회는 KIS(장중 봉 포함) 출처를 넘긴다.
    최우선타겟 지정(매매 워커용)은 비밀상회 전용이라 여기 없다(py-secret-api PriorityTargetService).
    """

    def __init__(self, bar_source=None):
        self.buyTargetStockDaoImpl = TradeBuyTargetStockDao()
        self.buyTargetBasicDaoImpl = TradeBuyTargetBasicDao()
        self.buyTargetChartDaoImpl = TradeBuyTargetChartDao()
        self.masterStockDaoImpl = MasterStockDao()
        self.investorDaoImpl = StockInvestorDailyDao()
        self.modService = StockModService()
        self.bar_source = bar_source or DbBarSource()

    def _period_bars(self, session, stock_code, count, unit):
        return self.bar_source.recent_bars(session, stock_code, count, unit)

    def _bars_between(self, session, stock_code, date_from, date_to):
        return self.bar_source.bars_between(session, stock_code, date_from, date_to)

    def get_buy_target_stock_list(self, session, ymd, lite: bool = False, source: str | None = None):
        """매수추천 목록. 두 테이블을 종목당 한 줄로 합치고 행마다 algos(걸린 알고리즘)를 붙인다.

          · trade_buy_target_stock : 2파 종합순위(PREMIUM). 워커가 읽는 테이블.
                                     rank_no 가 남아 있는 옛 행(기본 알고리즘이 같은 테이블에 저장되던 시절)은 BASIC 도 겸한다.
          · trade_buy_target_basic : 옛 기계식 알고리즘(BASIC).
        단계 판정·권한별 가공은 RecoLevel.apply_levels 가 한다.

        chart_data 는 응답용으로 줄인다(compact_bars, 2026-11-18). 봉 개수(120)는 그대로다 —
        화면이 120일선·MACD(EMA)를 이 봉으로 다시 계산하므로 봉을 자르면 추천 판정이 달라진다.
        lite=True(홈)면 이동평균(ma20·ma60·ma120)도 뺀다. 홈은 미니 차트를 그리지 않는다.

        source 로 한 테이블만 읽을 수 있다(비밀상회 매수추천 화면의 베이직·프리미엄 탭, 2026-11-25).
          'basic'   → trade_buy_target_basic 만 / 'premium' → trade_buy_target_stock 만 / None → 둘 다 합침(기존)
        ymd 미지정이면 그 테이블의 가장 최근 영업일을 쓴다.
        """
        if source not in (None, 'basic', 'premium'):
            raise ValueError(f"source 는 basic·premium 중 하나여야 합니다: {source}")
        use_main = source in (None, 'premium')
        use_basic = source in (None, 'basic')
        # ymd 미지정이면 두 테이블 중 더 최근 영업일을 쓴다(한쪽만 비는 날에도 다른 쪽이 나오게).
        if not ymd.get(Literal.YMD):
            latest = [y for y in ((self.buyTargetStockDaoImpl.select_latest_ymd(session) if use_main else None),
                                  (self.buyTargetBasicDaoImpl.select_latest_ymd(session) if use_basic else None)) if y]
            ymd = {**ymd, Literal.YMD: max(latest) if latest else None}

        main_rows = self.buyTargetStockDaoImpl.select_trade_buy_target_daily(session, ymd) if use_main else []
        basic_rows = self.buyTargetBasicDaoImpl.select_daily(session, ymd.get(Literal.YMD)) if use_basic else []
        results = merge_reco_sources(main_rows, basic_rows)
        if not results:
            return results

        # 전 종목이 같은 날짜이므로 첫 행의 ymd로 차트 데이터를 한 번에 조회해 붙인다(종목별 N회 조회 대신).
        resolved_ymd = results[0]["ymd"]
        chart_map = self.buyTargetChartDaoImpl.select_by_ymd(session, resolved_ymd)
        for item in results:
            item["chart_data"] = self.compact_bars(chart_map.get(item["stock_code"], []), with_ma=not lite)

        # 시가총액·투자자 수급 — 추천일 이하 가장 최근 영업일 기준(20:00 추천 → 다음 날 07:10 그날 수급 적재).
        # 부가 정보라 실패해도 추천 목록은 그대로 내려준다.
        try:
            self.attach_market_info(session, results, resolved_ymd)
        except Exception as e:
            print(f"[buy-target] 시가총액·수급 조회 실패: {e}", flush=True)

        # 업종명(홈 추천 목록·매수추천 종목명 옆) — master_stock.idx_bztp_* (sql/34). 없으면 None.
        try:
            sector_map = self.masterStockDaoImpl.select_sector_names(
                session, [it["stock_code"] for it in results if it.get("stock_code")])
        except Exception as e:
            print(f"[buy-target] 업종 조회 실패: {e}", flush=True)
            sector_map = {}
        for item in results:
            item["sector_name"] = sector_map.get(item.get("stock_code"))
        return results

    _MA_KEYS = ("ma20", "ma60", "ma120")

    @classmethod
    def compact_bars(cls, bars: list, with_ma: bool = True) -> list:
        """매수추천 chart_data 를 응답용으로 줄인다. 값의 의미는 바꾸지 않는다.
          · date   'YYYY-MM-DD 00:00:00' → 'YYYY-MM-DD' (화면은 모두 앞 10자리만 쓴다)
          · 가격    정수면 정수로(2335.0 → 2335), 아니면 소수 2자리
          · volume 정수로
          · ma*    소수 2자리(미니 차트 선 그리기용). with_ma=False 면 뺀다
        그 밖의 키는 그대로 둔다."""
        out = []
        for b in bars or []:
            if not isinstance(b, dict):
                continue
            row = {}
            for k, v in b.items():
                if k in cls._MA_KEYS:
                    if with_ma:
                        row[k] = round(v, 2) if isinstance(v, float) else v
                elif k == "date":
                    row[k] = str(v)[:10] if v is not None else v
                elif k == "volume":
                    row[k] = int(v) if isinstance(v, (int, float)) else v
                elif k in ("open", "high", "low", "close") and isinstance(v, float):
                    row[k] = int(v) if v.is_integer() else round(v, 2)
                else:
                    row[k] = v
            out.append(row)
        return out

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

    def get_target_rec_record(self, session, params):
        stock_code = params.get(Literal.STOCK_CODE, None)
        rec_recent_record = self.buyTargetStockDaoImpl.select_trade_recent_record(session, params)

        today = datetime.today()

        if rec_recent_record is None:
            # 3개월 데이터
            date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")

            ohlcv = self._bars_between(session, stock_code, date_from, date_to)
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

            ohlcv:pd.DataFrame = self._bars_between(session, stock_code, date_from, date_to)
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

        # 일봉만 분석(스윙·피보·패턴 등)을 붙인다. 분석을 켜면 지표 워밍업용으로 봉을 더 받는다(화면은 그대로 200봉)
        modules = self._chart_analysis_modules(session) if (period or "day") == "day" else []
        ohlcv:pd.DataFrame = self._period_bars(session, stock_code, 350 if modules else 200, period or "day")

        if ohlcv is None or ohlcv.empty:
            raise Exception("DF is NONE")

        # OPEN, HIGH, CLOSE, LOW, VOLUME, SMA(5, 20, 60, 120), BB(UPPER, MID, LOWER) 들어있는 dataframe
        created:pd.DataFrame = self.modService.createAddChannel(ohlcv).tail(200)

        # datetime('%Y-%m-%d %H:%M:%S') → ymd('%Y-%m-%d')
        created[Literal.YMD] = created[Literal.YMD].str[:10]

        # iterrows 는 행마다 Series 를 만들어 느리다(200봉 × 10회). 열을 파이썬 리스트로 한 번에 꺼내 묶는다.
        #   값·모양은 예전 iterrows 판과 같다: x 는 'YYYY-MM-DD', y 는 소수 2자리(NaN 이면 None), 가격·거래량은 float, rate 는 문자열.
        xs = [str(v) for v in created[Literal.YMD].tolist()]

        def to_xy(col):
            return [{'x': x, 'y': (round(y, 2) if pd.notna(y) else None)}
                    for x, y in zip(xs, created[col].astype(float).tolist())]

        o_, h_, c_, l_ = (created[k].astype(float).tolist()
                          for k in (Literal.OPEN, Literal.HIGH, Literal.CLOSE, Literal.LOW))
        ohcl = [{'x': x, 'o': o, 'h': h, 'c': c, 'l': l} for x, o, h, c, l in zip(xs, o_, h_, c_, l_)]
        vol = [{'x': x, 'y': y} for x, y in zip(xs, created[Literal.VOLUME].astype(float).tolist())]
        rate = [{'x': x, 'y': str(y)} for x, y in zip(xs, created['RATE'].tolist())]

        result = {
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
        if modules:
            full = ohlcv[[Literal.YMD, Literal.OPEN, Literal.HIGH, Literal.LOW, Literal.CLOSE]].copy()
            full[Literal.YMD] = full[Literal.YMD].str[:10]
            result['analysis'] = chart_analysis.analyze(full, len(created), modules)
        return result

    @staticmethod
    def _chart_analysis_modules(session) -> list:
        """공통코드 stock/setting/screen/CHART_ANALYSIS → 켤 분석 모듈. 행이 없으면 전부, 'N' 이면 끔."""
        try:
            rows = MasterCodesDao().select_master_code(
                session, {'system': 'stock', 'source': 'setting', 'category': 'screen'})
            setting = next((row['desc'] for row in rows if row['code'] == 'CHART_ANALYSIS'), None)
        except Exception as e:
            logging.warning(f"[chart] CHART_ANALYSIS 설정 조회 실패 — 전부 켬: {e}")
            setting = None
        return chart_analysis.parse_modules(setting)
