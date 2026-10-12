"""
업종 화면(테마 화면 대체) — KRX 지수업종별 등락·수급 집계.

  업종 : master_stock.idx_bztp_* (07:00 STOCK_CODE_MASTER_JOB, sql/34). 그룹 = 중분류 우선, 없으면 대분류.
         KOSPI 와 KOSDAQ 은 같은 이름(전기·전자 등)이라도 다른 지수라 시장별로 따로 묶는다. 업종 없는 현물은 '미분류'.
  시세 : stock_investor_daily (07:10 STOCK_INVESTOR_JOB) 의 기준일·직전 영업일 종가 → 등락률,
         같은 날 외국인/기관/개인 순매수 대금(백만원). 추가 KIS 호출 없음.
  업종 등락률 = 시가총액 가중(지수와 같은 방식) = Σ(상장주식수 × 종가) ÷ Σ(상장주식수 × 직전 종가) − 1.
         두 날 종가와 상장주식수가 모두 있는 종목만 넣는다.

데이터는 하루 한 번 바뀌므로 기준일별로 CACHE_TTL_SECONDS 동안 기억한다.
"""
import time

from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao

CACHE_TTL_SECONDS = 600
UNCLASSIFIED_CD = "0000"
UNCLASSIFIED_NAME = "미분류"
MARKETS = ("KOSPI", "KOSDAQ")

_cache = {}   # {max_ymd or '': (조회 시각, result)}


class SectorService:
    def __init__(self):
        self.masterStockDaoImpl = MasterStockDao()
        self.investorDaoImpl = StockInvestorDailyDao()

    # ────────────────────────────────────────────────────────────────
    # 공개 API
    # ────────────────────────────────────────────────────────────────
    def get_sectors(self, session, max_ymd: str = None) -> dict:
        """{ymd, prev_ymd, sectors:[업종 요약]} — 업종 상세(stocks)는 빼고 내려준다."""
        data = self._build(session, max_ymd)
        return {
            "ymd": data["ymd"],
            "prev_ymd": data["prev_ymd"],
            "sectors": [{k: v for k, v in s.items() if k != "stocks"} for s in data["sectors"]],
        }

    def get_sector_detail(self, session, market: str, sector_cd: str, max_ymd: str = None) -> dict | None:
        """{ymd, prev_ymd, sector:{요약…, stocks:[종목]}} 또는 업종이 없으면 None."""
        data = self._build(session, max_ymd)
        for s in data["sectors"]:
            if s["market"] == market and s["sector_cd"] == sector_cd:
                return {"ymd": data["ymd"], "prev_ymd": data["prev_ymd"], "sector": s}
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

        ymds = self.investorDaoImpl.select_recent_ymds(session, max_ymd, n=2)
        ymd = ymds[0] if ymds else None
        prev_ymd = ymds[1] if len(ymds) > 1 else None

        by_day = {}
        for r in self.investorDaoImpl.select_by_ymds(session, ymds):
            by_day.setdefault(r["ymd"], {})[r["stock_code"]] = r
        today = by_day.get(ymd, {})
        prev = by_day.get(prev_ymd, {})

        groups = {}
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

            g = groups.setdefault((market, cd), {
                "market": market, "sector_cd": cd, "sector_name": name or cd, "parent_name": parent,
                "stocks": [],
            })
            g["stocks"].append(self._stock_row(st, today.get(st["stock_code"]), prev.get(st["stock_code"])))

        sectors = [self._summarize(g) for g in groups.values()]
        # 시장 → 등락률 높은 순(값 없는 업종·미분류는 뒤)
        sectors.sort(key=lambda s: (
            MARKETS.index(s["market"]),
            s["sector_cd"] == UNCLASSIFIED_CD,
            s["chg_rate"] is None,
            -(s["chg_rate"] or 0),
        ))

        result = {"ymd": ymd, "prev_ymd": prev_ymd, "sectors": sectors}
        _cache[key] = (now, result)
        return result

    @staticmethod
    def _stock_row(st: dict, inv: dict | None, prev_inv: dict | None) -> dict:
        close = inv.get("close_price") if inv else None
        prev_close = prev_inv.get("close_price") if prev_inv else None
        shares = st.get("listed_shares")
        return {
            "stock_code": st["stock_code"],
            "stock_name": st["stock_name"],
            "close": close,
            "prev_close": prev_close,
            "chg_rate": round((close / prev_close - 1) * 100, 2) if close and prev_close else None,
            "market_cap": round(shares * close / 100_000_000) if shares and close else None,   # 억원
            "frgn_amt": inv.get("frgn_amt") if inv else None,    # 백만원
            "orgn_amt": inv.get("orgn_amt") if inv else None,
            "prsn_amt": inv.get("prsn_amt") if inv else None,
            "idx_bztp_src": st.get("idx_bztp_src"),
            "_shares": shares,
        }

    @staticmethod
    def _summarize(g: dict) -> dict:
        cap_now = cap_prev = 0
        up = down = flat = 0
        frgn = orgn = prsn = 0
        cap_sum = 0
        for s in g["stocks"]:
            shares = s.pop("_shares", None)
            if s["chg_rate"] is not None:
                if s["chg_rate"] > 0:
                    up += 1
                elif s["chg_rate"] < 0:
                    down += 1
                else:
                    flat += 1
                if shares:
                    cap_now += shares * s["close"]
                    cap_prev += shares * s["prev_close"]
            frgn += s["frgn_amt"] or 0
            orgn += s["orgn_amt"] or 0
            prsn += s["prsn_amt"] or 0
            cap_sum += s["market_cap"] or 0

        # 종목은 시가총액 큰 순(값 없는 종목은 뒤)
        g["stocks"].sort(key=lambda s: (s["market_cap"] is None, -(s["market_cap"] or 0), s["stock_code"]))
        return {
            **g,
            "stock_count": len(g["stocks"]),
            "chg_rate": round((cap_now / cap_prev - 1) * 100, 2) if cap_prev else None,
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "market_cap": cap_sum or None,   # 억원
            "frgn_amt": frgn,                # 백만원
            "orgn_amt": orgn,
            "prsn_amt": prsn,
            "leaders": [s["stock_name"] for s in g["stocks"][:3]],
        }
