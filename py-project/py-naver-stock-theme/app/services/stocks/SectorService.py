"""
업종 화면(테마 화면 대체) — KRX 지수업종별 등락·수급 집계 + 최근 5영업일 추이.

  업종 : master_stock.idx_bztp_* (07:00 STOCK_CODE_MASTER_JOB, sql/34). 그룹 = 중분류 우선, 없으면 대분류.
         KOSPI 와 KOSDAQ 은 같은 이름(전기·전자 등)이라도 다른 지수라 시장별로 따로 묶는다. 업종 없는 현물은 '미분류'.
  시세 : stock_investor_daily (07:10 STOCK_INVESTOR_JOB, 90일 보관) 의 최근 TREND_DAYS+1 영업일 종가 → 등락률,
         같은 날 외국인/기관/개인 순매수 대금(백만원). 추가 KIS 호출 없음.
  업종 등락률(하루) = 시가총액 가중(지수와 같은 방식) = Σ(상장주식수 × 종가) ÷ Σ(상장주식수 × 직전 종가) − 1.
         두 날 종가와 상장주식수가 모두 있는 종목만 넣는다. 상장주식수는 현재값으로 고정(과거 증자 등은 무시).
  누적 등락률 = 하루 등락률을 차례로 곱한 값(지수를 이어 붙인 것과 같음). 시장 전체도 같은 방식으로 계산해 비교선으로 준다.

데이터는 하루 한 번 바뀌므로 기준일별로 CACHE_TTL_SECONDS 동안 기억한다.
"""
import time

from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao

CACHE_TTL_SECONDS = 600
TREND_DAYS = 5
UNCLASSIFIED_CD = "0000"
UNCLASSIFIED_NAME = "미분류"
MARKETS = ("KOSPI", "KOSDAQ")
_FLOWS = ("frgn_amt", "orgn_amt", "prsn_amt")

_cache = {}   # {max_ymd or '': (조회 시각, result)}


class SectorService:
    def __init__(self):
        self.masterStockDaoImpl = MasterStockDao()
        self.investorDaoImpl = StockInvestorDailyDao()

    # ────────────────────────────────────────────────────────────────
    # 공개 API
    # ────────────────────────────────────────────────────────────────
    def get_sectors(self, session, max_ymd: str = None) -> dict:
        """{ymd, prev_ymd, days, markets:{시장: {trend}}, sectors:[업종 요약]} — 업종 상세(stocks)는 빼고 내려준다."""
        data = self._build(session, max_ymd)
        return {
            **{k: v for k, v in data.items() if k != "sectors"},
            "sectors": [{k: v for k, v in s.items() if k != "stocks"} for s in data["sectors"]],
        }

    def get_sector_detail(self, session, market: str, sector_cd: str, max_ymd: str = None) -> dict | None:
        """{ymd, prev_ymd, days, market_trend, sector:{요약…, stocks:[종목]}} 또는 업종이 없으면 None."""
        data = self._build(session, max_ymd)
        for s in data["sectors"]:
            if s["market"] == market and s["sector_cd"] == sector_cd:
                return {"ymd": data["ymd"], "prev_ymd": data["prev_ymd"],
                        "base_ymd": data["base_ymd"], "days": data["days"],
                        "market_trend": data["markets"][market]["trend"], "sector": s}
        return None

    # ────────────────────────────────────────────────────────────────
    # 집계
    # ────────────────────────────────────────────────────────────────
    def _build(self, session, max_ymd: str = None) -> dict:
        key = max_ymd or ""
        now = time.time()
        cached = _cache.get(key)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]

        # 오래된 → 최신. days[0] 은 첫날 등락률의 기준(직전 종가)으로만 쓴다.
        days = sorted(self.investorDaoImpl.select_recent_ymds(session, max_ymd, n=TREND_DAYS + 1))
        inv = {}   # {stock_code: {ymd: row}}
        for r in self.investorDaoImpl.select_by_ymds(session, days):
            inv.setdefault(r["stock_code"], {})[r["ymd"]] = r

        groups, market_members = {}, {m: [] for m in MARKETS}
        for st in self.masterStockDaoImpl.select_sector_stocks(session):
            market = st["stock_type"]
            if market not in MARKETS:
                continue
            if st["idx_bztp_mcls_cd"]:
                cd, name, parent = st["idx_bztp_mcls_cd"], st["idx_bztp_mcls_name"], st["idx_bztp_lcls_name"]
            elif st["idx_bztp_lcls_cd"]:
                cd, name, parent = st["idx_bztp_lcls_cd"], st["idx_bztp_lcls_name"], None
            else:
                cd, name, parent = UNCLASSIFIED_CD, UNCLASSIFIED_NAME, None

            member = (st, inv.get(st["stock_code"], {}))
            market_members[market].append(member)
            g = groups.setdefault((market, cd), {
                "market": market, "sector_cd": cd, "sector_name": name or cd, "parent_name": parent,
                "members": [],
            })
            g["members"].append(member)

        sectors = [self._summarize(g, days) for g in groups.values()]
        # 시장 → 등락률 높은 순(값 없는 업종·미분류는 뒤)
        sectors.sort(key=lambda s: (
            MARKETS.index(s["market"]),
            s["sector_cd"] == UNCLASSIFIED_CD,
            s["chg_rate"] is None,
            -(s["chg_rate"] or 0),
        ))

        result = {
            "ymd": days[-1] if days else None,
            "prev_ymd": days[-2] if len(days) > 1 else None,
            "base_ymd": days[0] if days else None,   # 누적 등락률 0% 기준일(첫 추이 점의 직전 영업일)
            "days": days[1:],
            "markets": {m: {"trend": self._trend(market_members[m], days)} for m in MARKETS},
            "sectors": sectors,
        }
        _cache[key] = (now, result)
        return result

    @staticmethod
    def _close(rows: dict, ymd: str):
        r = rows.get(ymd)
        return r.get("close_price") if r else None

    @classmethod
    def _rate(cls, rows: dict, a: str, b: str):
        """a → b 등락률(%) 또는 None."""
        ca, cb = cls._close(rows, a), cls._close(rows, b)
        return round((cb / ca - 1) * 100, 2) if ca and cb else None

    @classmethod
    def _trend(cls, members: list, days: list) -> list:
        """[{ymd, chg_rate, cum_rate, frgn_amt, orgn_amt, prsn_amt}] — days[1:] 각 날짜. 값이 없으면 None."""
        out, cum = [], 1.0
        for prev, cur in zip(days, days[1:]):
            cap_now = cap_prev = 0
            flows = dict.fromkeys(_FLOWS, 0)
            for st, rows in members:
                shares = st.get("listed_shares")
                c0, c1 = cls._close(rows, prev), cls._close(rows, cur)
                if shares and c0 and c1:
                    cap_now += shares * c1
                    cap_prev += shares * c0
                r = rows.get(cur)
                if r:
                    for k in _FLOWS:
                        flows[k] += r.get(k) or 0
            rate = (cap_now / cap_prev - 1) if cap_prev else None
            if rate is not None:
                cum *= 1 + rate
            out.append({
                "ymd": cur,
                "chg_rate": round(rate * 100, 2) if rate is not None else None,
                "cum_rate": round((cum - 1) * 100, 2) if rate is not None else None,
                **flows,
            })
        return out

    @classmethod
    def _summarize(cls, g: dict, days: list) -> dict:
        members = g.pop("members")
        ymd = days[-1] if days else None
        prev = days[-2] if len(days) > 1 else None

        stocks = []
        up = down = flat = 0
        up5 = down5 = flat5 = 0
        for st, rows in members:
            last = rows.get(ymd) or {}
            close = last.get("close_price")
            shares = st.get("listed_shares")
            chg = cls._rate(rows, prev, ymd) if prev else None
            if chg is not None:
                up, down, flat = up + (chg > 0), down + (chg < 0), flat + (chg == 0)
            chg5 = cls._rate(rows, days[0], ymd) if len(days) > 1 else None
            if chg5 is not None:
                up5, down5, flat5 = up5 + (chg5 > 0), down5 + (chg5 < 0), flat5 + (chg5 == 0)
            stocks.append({
                "stock_code": st["stock_code"],
                "stock_name": st["stock_name"],
                "close": close,
                "prev_close": cls._close(rows, prev) if prev else None,
                "chg_rate": chg,
                "chg_rate_5d": chg5,
                "market_cap": round(shares * close / 100_000_000) if shares and close else None,   # 억원
                **{k: last.get(k) for k in _FLOWS},                                                   # 백만원
                "idx_bztp_src": st.get("idx_bztp_src"),
            })
        # 종목은 시가총액 큰 순(값 없는 종목은 뒤)
        stocks.sort(key=lambda s: (s["market_cap"] is None, -(s["market_cap"] or 0), s["stock_code"]))

        trend = cls._trend(members, days)
        today = trend[-1] if trend else {}
        return {
            **g,
            "stock_count": len(stocks),
            "chg_rate": today.get("chg_rate"),
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "market_cap": sum(s["market_cap"] or 0 for s in stocks) or None,   # 억원
            **{k: today.get(k, 0) for k in _FLOWS},                               # 기준일 순매수(백만원)
            "chg_rate_5d": trend[-1]["cum_rate"] if trend else None,
            "up_count_5d": up5,
            "down_count_5d": down5,
            "flat_count_5d": flat5,
            **{f"{k}_5d": sum(t[k] for t in trend) for k in _FLOWS},              # 기간 합계
            "trend": trend,
            "leaders": [s["stock_name"] for s in stocks[:3]],
            "stocks": stocks,
        }
