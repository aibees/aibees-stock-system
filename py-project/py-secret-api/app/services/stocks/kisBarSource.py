"""
비밀상회 시세 출처 — KIS(실시간·장중 봉 포함), KIS 를 끄거나(KIS_ENABLED=false) 키가 없으면 DB 일봉.
web_shared StockService(bar_source=KisBarSource()) 로 넘긴다(2026-11-19, 예전 StockService._period_bars 의 KIS 분기).
"""
import logging

from stock_shared.kis.credentials import KisCredentialError
from web_shared.ext_services.kis.KisEngine import KisEngine
from web_shared.services.stocks.StockService import DbBarSource
from app.utils.service import KIS_ENABLED


class KisBarSource(DbBarSource):

    def __init__(self):
        # KisEngine 은 처음 쓸 때 만든다 — import 시점에 1번 사용자의 KIS 키를 DB 에서 읽지 않게.
        self._kis_engine = None

    @property
    def kis(self) -> KisEngine:
        if self._kis_engine is None:
            self._kis_engine = KisEngine(virtual=False)
        return self._kis_engine

    def recent_bars(self, session, stock_code, count, unit):
        if KIS_ENABLED:
            try:
                return self.kis.get_ohlcv_period_unit(stock_code, count, unit=unit)
            except KisCredentialError as e:
                logging.warning(f"[chart] KIS 키 없음 → DB 일봉 사용: {e}")
        return super().recent_bars(session, stock_code, count, unit)

    def bars_between(self, session, stock_code, date_from, date_to):
        if KIS_ENABLED:
            try:
                return self.kis.getOHLCV(stock_code, date_from, date_to)
            except KisCredentialError as e:
                logging.warning(f"[rec-record] KIS 키 없음 → DB 일봉 사용: {e}")
        return super().bars_between(session, stock_code, date_from, date_to)
