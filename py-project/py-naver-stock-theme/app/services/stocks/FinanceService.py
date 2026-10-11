"""
개별종목 '재무' 탭 — 진입할 때 KIS 에서 그때그때 조회한다(추천 목록에 없는 종목도).

  PER·PBR·EPS·BPS : 현재가 시세(현재가 ÷ 직전 연간 결산 EPS/BPS)
  ROE·증가율·부채비율·PEG : 재무비율(연간 확정 결산)
계산 규칙은 stock_shared.kis.finance (배치와 공용). KIS 키는 운영자(user 1) 실계좌 키 — 조회만 한다.
같은 종목은 CACHE_TTL_SECONDS 동안 다시 부르지 않는다(탭을 열 때마다 KIS 호출하지 않게).
"""
import time

from app.ext_services.kis.KisEngine import KisEngine

CACHE_TTL_SECONDS = 600
_cache = {}   # {stock_code: (조회 시각, result)}


class FinanceService:

    def get_fundamentals(self, stock_code: str) -> dict:
        now = time.time()
        cached = _cache.get(stock_code)
        if cached and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1]
        result = KisEngine(virtual=False).get_fundamentals(stock_code)
        _cache[stock_code] = (now, result)
        return result
