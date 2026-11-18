"""
최우선타겟(매수추천 카드 select) — 유저당 1건, 날짜 무관. **비밀상회 전용**(매매 워커가 읽는다).
worker(RecoBuyExecutor)가 다음 영업일 정규장 라운드에서 읽어 소비(1회성 null화)한다.
2026-11-19 StockService 에서 분리(web_shared StockService 는 양봉상회도 쓰므로).
"""
from stock_shared.dao.tradeBuyTargetPriorityDao import TradeBuyTargetPriorityDao
from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao


class PriorityTargetService:

    def __init__(self):
        self.buyTargetStockDaoImpl = TradeBuyTargetStockDao()
        self.buyTargetPriorityDaoImpl = TradeBuyTargetPriorityDao()

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
