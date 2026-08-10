import logging

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.tradeBuyTargetStockTest import TradeBuyTargetStockTest

logging.basicConfig(level=logging.ERROR)

# upsert 시 PK(ymd, stock_code) 를 제외하고 갱신하는 컬럼
_UPSERT_COLS = (
    "stock_name",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rate",
    "action_type",
    "macd_cross",
    "obv_cross",
    "is_vol_limit",
    "is_under_bb_upper",
    "is_over_on_mid",
    "is_vol_surge",
    "is_bb_mid_breakout",
    "eps",
    "pbr",
    "per",
    "roe",
    "peg",
    "score",
    "rank_no",
)


class TradeBuyTargetStockTestDao(BaseDao):
    """trade_buy_target_stock_test 전용 DAO.

    TradeBuyTargetStockDao 와 동일한 upsert 스키마를 쓰되, 운영 테이블
    (trade_buy_target_stock)이 아닌 테스트 테이블에만 쓴다. 알고리즘
    오프라인 재현 테스트(app/test/run_test_buy_check.py)에서 사용.
    """
    model = TradeBuyTargetStockTest

    def __init__(self):
        self.__name__ = "TradeBuyTargetStockTestDao"

    def select_recent_codes(self, session, from_ymd: str, to_ymd: str) -> set:
        """[from_ymd, to_ymd](양쪽 포함) 구간에 테스트 매수추천에 등장한 종목코드 집합.
        운영 DAO의 동명 메서드와 동일한 용도(재추천 페널티 랭킹)."""
        stmt = (
            select(TradeBuyTargetStockTest.stock_code)
            .where(TradeBuyTargetStockTest.ymd >= from_ymd, TradeBuyTargetStockTest.ymd <= to_ymd)
            .distinct()
        )
        return {r[0] for r in session.execute(stmt).all()}

    def delete_by_ymd(self, session, ymd: str) -> int:
        """해당 일자 전체 삭제(재실행 시 중복 방지)."""
        return (
            session.query(TradeBuyTargetStockTest)
            .filter(TradeBuyTargetStockTest.ymd == ymd)
            .delete()
        )

    def upsert_trade_buy_target_stock(self, session, data_list: list[dict]) -> None:
        """
        ymd + stock_code 기준 Upsert. 입력 dict 구조는 운영 DAO와 동일:
          d['todayStock'] : open/high/low/close/volume/rate
          d['indicator']  : macd_cross/obv_cross/is_* 플래그
          d['fin']        : eps/pbr/per/roe/peg
          d['score'], d['rank_no'] : 랭킹 산정 후에만 채워짐
        """
        if not data_list:
            logging.info("Upsert할 데이터가 없습니다.")
            return

        for d in data_list:
            row = {
                "ymd": d["ymd"],
                "stock_code": d["stock_code"],
                "stock_name": d["stock_name"],
                "action_type": d["action_type"],
                "open": d["todayStock"]["open"],
                "high": d["todayStock"]["high"],
                "low": d["todayStock"]["low"],
                "close": d["todayStock"]["close"],
                "volume": d["todayStock"]["volume"],
                "rate": d["todayStock"]["rate"],
                "macd_cross": d["indicator"]["macd_cross"],
                "obv_cross": d["indicator"]["obv_cross"],
                "is_vol_limit": d["indicator"]["is_vol_limit"],
                "is_under_bb_upper": d["indicator"]["is_under_bb_upper"],
                "is_over_on_mid": d["indicator"]["is_over_on_mid"],
                "is_vol_surge": d["indicator"]["is_vol_surge"],
                "is_bb_mid_breakout": d["indicator"]["is_bb_mid_breakout"],
                "eps": d["fin"]["eps"],
                "pbr": d["fin"]["pbr"],
                "per": d["fin"]["per"],
                "roe": d["fin"]["roe"],
                "peg": d["fin"]["peg"],
                "score": d.get("score"),
                "rank_no": d.get("rank_no"),
            }

            stmt = insert(TradeBuyTargetStockTest).values(row)
            upsert_stmt = stmt.on_duplicate_key_update(
                **{c: stmt.inserted[c] for c in _UPSERT_COLS}
            )
            session.execute(upsert_stmt)
