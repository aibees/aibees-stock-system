"""
trade_buy_target_basic DAO — 기본 단계(옛 기계식 알고리즘) 추천 종목.

저장: py-stock-batch StockBuyCheckJob (watch 게이트 통과 종목 + 점수·순위)
조회: py-naver-stock-theme GET /api/v1/stocks/buy-target (기본 단계 목록)
워커는 이 테이블을 읽지 않는다(trade_buy_target_stock 만 본다).
"""
from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.tradeBuyTargetBasic import TradeBuyTargetBasic

# upsert 시 PK(ymd, stock_code) 를 제외하고 갱신하는 컬럼
_UPSERT_COLS = (
    "stock_name", "open", "high", "low", "close", "volume", "rate", "action_type",
    "macd_cross", "obv_cross", "is_vol_limit", "is_under_bb_upper", "is_over_on_mid",
    "is_vol_surge", "is_bb_mid_breakout", "eps", "pbr", "per", "roe", "peg",
    "score", "rank_no", "shape_proba", "shape_exhaustion",
)


class TradeBuyTargetBasicDao(BaseDao):
    model = TradeBuyTargetBasic

    def __init__(self):
        self.__name__ = "TradeBuyTargetBasicDao"

    def select_latest_ymd(self, session) -> str | None:
        """기본 추천이 존재하는 가장 최근 ymd. 없으면 None."""
        return session.execute(select(func.max(TradeBuyTargetBasic.ymd))).scalar()

    def select_daily(self, session, ymd: str) -> list:
        """일자별 기본 추천(rank_no 순). ymd 가 없으면 빈 목록."""
        if not ymd:
            return []
        stmt = (
            select(TradeBuyTargetBasic)
            .where(TradeBuyTargetBasic.ymd == ymd)
            .order_by(TradeBuyTargetBasic.rank_no.is_(None), TradeBuyTargetBasic.rank_no,
                      TradeBuyTargetBasic.stock_code)
        )
        return [r.to_dict() for r in session.execute(stmt).scalars().all()]

    def select_recent_codes(self, session, from_ymd: str, to_ymd: str) -> set:
        """[from_ymd, to_ymd](양쪽 포함) 구간에 기본 추천에 등장한 종목코드 집합('최근 재추천 페널티' 판정용)."""
        stmt = (
            select(TradeBuyTargetBasic.stock_code)
            .where(TradeBuyTargetBasic.ymd >= from_ymd, TradeBuyTargetBasic.ymd <= to_ymd)
            .distinct()
        )
        return {r[0] for r in session.execute(stmt).all()}

    def delete_by_ymd(self, session, ymd: str) -> int:
        """해당 일자 전체 삭제."""
        return session.query(TradeBuyTargetBasic).filter(TradeBuyTargetBasic.ymd == ymd).delete()

    def upsert_bulk(self, session, data_list: list[dict]) -> None:
        """ymd + stock_code 기준 upsert. 입력 모양은 TradeBuyTargetStockDao.upsert_trade_buy_target_stock 과 같다
        (d['todayStock'] / d['indicator'] / d['fin'] 중첩 + score / rank_no / shape_proba)."""
        if not data_list:
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
                "shape_proba": d.get("shape_proba"),
                "shape_exhaustion": d.get("indicator", {}).get("shape_exhaustion"),
            }
            stmt = insert(TradeBuyTargetBasic).values(row)
            session.execute(stmt.on_duplicate_key_update(**{c: stmt.inserted[c] for c in _UPSERT_COLS}))
