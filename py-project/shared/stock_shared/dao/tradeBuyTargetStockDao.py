import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.tradeBuyTargetStock import TradeBuyTargetStock

logging.basicConfig(level=logging.ERROR)

# py-naver-stock-theme 의 Literal 상수와 동일한 값.
# shared 는 특정 프로젝트 모듈에 의존하지 않기 위해 값을 직접 정의한다.
_YMD = "ymd"
_STOCK_CODE = "stock_code"
_ISO_DATE_FORMAT = "%Y%m%d"

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


class TradeBuyTargetStockDao(BaseDao):
    model = TradeBuyTargetStock

    def __init__(self):
        self.__name__ = "TradeBuyTargetStockDao"

    # ------------------------------------------------------------------
    # select
    # ------------------------------------------------------------------
    def select_target_codes_since(self, session, from_ymd: str) -> list:
        """from_ymd(포함) 이후 매수추천에 한 번이라도 등장한 종목 목록(중복 제거).

        반환: [{'stock_code':…, 'stock_name':…, 'first_ymd':…, 'target_cnt':…}, …]
              추천이 잦았던 순 → 최근 등장 순으로 정렬.
        캔들 백필 배치가 적재 대상을 뽑을 때 쓴다.
        """
        stmt = (
            select(
                TradeBuyTargetStock.stock_code,
                func.max(TradeBuyTargetStock.stock_name).label("stock_name"),
                func.min(TradeBuyTargetStock.ymd).label("first_ymd"),
                func.max(TradeBuyTargetStock.ymd).label("last_ymd"),
                func.count().label("target_cnt"),
            )
            .where(TradeBuyTargetStock.ymd >= from_ymd)
            .group_by(TradeBuyTargetStock.stock_code)
            .order_by(func.count().desc(), func.max(TradeBuyTargetStock.ymd).desc())
        )
        return [dict(r) for r in session.execute(stmt).mappings().all()]

    def select_latest_ymd(self, session) -> str | None:
        """매수타겟이 존재하는 가장 최근 ymd. 데이터가 없으면 None."""
        return session.execute(
            select(func.max(TradeBuyTargetStock.ymd))
        ).scalar()

    def select_trade_buy_target_daily(self, session, data: dict):
        """일자별 매수타겟 조회 (rank_no 순).

        ymd 미지정(None/빈값)이면 **가장 최근 영업일자**를 자동으로 찾아 쓴다.

        ※ 예전엔 `data.get(_YMD, 오늘)` 이었는데, 라우터가
          `request.args.get('ymd')` 를 그대로 넘기는 탓에 파라미터가 없으면
          '키는 있고 값이 None' 이 된다. dict.get 은 이때 기본값을 쓰지 않고
          None 을 반환하므로 `WHERE ymd IS NULL` 이 되어 항상 빈 배열이었다.
          (기본값이 오늘이어도 배치 전이면 어차피 빈 배열이라 무용지물)
        """
        ymd = data.get(_YMD) or self.select_latest_ymd(session)
        if not ymd:
            return []

        stmt = (
            select(TradeBuyTargetStock)
            .where(TradeBuyTargetStock.ymd == ymd)
            .order_by(TradeBuyTargetStock.rank_no)
        )
        results = session.execute(stmt).scalars().all()
        return [item.to_dict() for item in results]

    def select_stock_master_list(self, session, param: dict) -> list:
        """일자별 매수타겟 조회 (stock_code 순, 배치용)."""
        stmt = (
            select(TradeBuyTargetStock)
            .where(TradeBuyTargetStock.ymd == param.get(_YMD))
            .order_by(TradeBuyTargetStock.stock_code.asc())
        )
        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    def select_trade_recent_record(self, session, data: dict) -> dict:
        """직전 30일(전일까지) 내 해당 종목의 최근 1건 조회."""
        stock_code = data.get(_STOCK_CODE, None)
        if not stock_code:
            raise Exception("no stock code")

        today = datetime.today()
        date_from = (today - timedelta(days=30)).strftime(_ISO_DATE_FORMAT)
        date_to = (today - timedelta(days=1)).strftime(_ISO_DATE_FORMAT)

        stmt = (
            select(TradeBuyTargetStock)
            .where(
                TradeBuyTargetStock.stock_code == stock_code,
                TradeBuyTargetStock.ymd.between(date_from, date_to),
            )
            .order_by(TradeBuyTargetStock.ymd.desc())
            .limit(1)
        )
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # ------------------------------------------------------------------
    # insert / update / delete
    # ------------------------------------------------------------------
    def delete_by_ymd(self, session, ymd: str) -> int:
        """해당 일자 전체 삭제."""
        return (
            session.query(TradeBuyTargetStock)
            .filter(TradeBuyTargetStock.ymd == ymd)
            .delete()
        )

    def upsert_trade_buy_target_stock(self, session, data_list: list[dict]):
        """
        ymd + stock_code 기준 Upsert.

        입력 dict 는 중첩 구조를 가진다:
          d['todayStock'] : open/high/low/close/volume/rate
          d['indicator']  : macd_cross/obv_cross/is_* 플래그
          d['fin']        : eps/pbr/per/roe/peg
          d['score'], d['rank_no'] 는 랭킹 산정 후 일괄 저장 경로에서만 채워진다.
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

            stmt = insert(TradeBuyTargetStock).values(row)
            upsert_stmt = stmt.on_duplicate_key_update(
                **{c: stmt.inserted[c] for c in _UPSERT_COLS}
            )
            session.execute(upsert_stmt)

    def update_rank(self, session, ymd: str, stock_code: str, score, rank_no) -> None:
        """이미 저장된 매수타겟 행의 종합점수/순위만 갱신."""
        stmt = (
            update(TradeBuyTargetStock)
            .where(
                and_(
                    TradeBuyTargetStock.ymd == ymd,
                    TradeBuyTargetStock.stock_code == stock_code,
                )
            )
            .values(score=score, rank_no=rank_no)
        )
        session.execute(stmt)
