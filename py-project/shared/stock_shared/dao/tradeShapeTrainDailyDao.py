import logging

from sqlalchemy import bindparam, func, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
from stock_shared.models.tradeShapeTrainDaily import TradeShapeTrainDaily

logging.basicConfig(level=logging.ERROR)

_PK = ("coin", "datetime")

# 일별 적재가 쓰는 컬럼. 라벨(net_edge_fwd/labeled_at)은 여기 없다 —
# ShapeLabelJob 만 건드리며, 재적재가 이미 확정된 라벨을 덮어쓰면 안 된다.
_DAILY_COLUMNS = (
    list(_PK)
    + list(SHAPE_FEATURE_COLUMNS)
    + [
        "shape_ret_1d_today",
        "open", "high", "low", "close", "volume",
        "shape_proba_at_scan", "composite_eligible", "action_type",
    ]
)


class TradeShapeTrainDailyDao:
    """shape 재학습용 일별 피처 스냅샷(trade_shape_train_daily).

    적재는 StockBuyCheckJob, 라벨 확정은 ShapeLabelJob 이 담당한다.
    """

    def __init__(self):
        self.__name__ = "TradeShapeTrainDailyDao"

    # ------------------------------------------------------------------
    # 적재 (StockBuyCheckJob)
    # ------------------------------------------------------------------
    @staticmethod
    def daily_columns() -> list:
        """적재 시 채워야 하는 컬럼 목록(호출부가 dict 키를 맞추는 데 사용)."""
        return list(_DAILY_COLUMNS)

    def upsert_daily_bulk(self, session, rows: list[dict]) -> int:
        """전종목 피처 스냅샷 일괄 upsert. 반환: 시도한 행 수.

        같은 (coin, datetime) 재실행 시 피처/OHLCV 는 최신값으로 덮되
        **net_edge_fwd / labeled_at 은 건드리지 않는다**(라벨 보존).
        """
        if not rows:
            logging.info("[trade_shape_train_daily] 적재할 행이 없습니다.")
            return 0

        # 누락 키가 있으면 executemany 파라미터 수가 어긋나므로 전 컬럼을 채워 정규화한다.
        norm = [{c: r.get(c) for c in _DAILY_COLUMNS} for r in rows]

        stmt = mysql_insert(TradeShapeTrainDaily)
        stmt = stmt.on_duplicate_key_update(
            **{c: stmt.inserted[c] for c in _DAILY_COLUMNS if c not in _PK}
        )
        session.execute(stmt, norm)
        return len(norm)

    # ------------------------------------------------------------------
    # 라벨 (ShapeLabelJob)
    # ------------------------------------------------------------------
    def select_unlabeled_coins(self, session, since: str) -> list[str]:
        """since(YYYY-MM-DD) 이후에 라벨 미확정 행이 있는 종목코드 목록."""
        rows = session.execute(
            select(TradeShapeTrainDaily.coin)
            .where(
                TradeShapeTrainDaily.net_edge_fwd.is_(None),
                TradeShapeTrainDaily.datetime >= since,
            )
            .group_by(TradeShapeTrainDaily.coin)
        ).scalars().all()
        return list(rows)

    def select_series(self, session, coins: list[str], since: str) -> list[dict]:
        """라벨 계산에 필요한 최소 컬럼만 종목·날짜 오름차순으로 조회."""
        if not coins:
            return []
        rows = session.execute(
            select(
                TradeShapeTrainDaily.coin,
                TradeShapeTrainDaily.datetime,
                TradeShapeTrainDaily.close,
                TradeShapeTrainDaily.high,
                TradeShapeTrainDaily.low,
                TradeShapeTrainDaily.net_edge_fwd,
            )
            .where(
                TradeShapeTrainDaily.coin.in_(coins),
                TradeShapeTrainDaily.datetime >= since,
            )
            .order_by(TradeShapeTrainDaily.coin, TradeShapeTrainDaily.datetime)
        ).all()
        return [
            {"coin": r[0], "datetime": r[1], "close": r[2],
             "high": r[3], "low": r[4], "net_edge_fwd": r[5]}
            for r in rows
        ]

    def update_labels_bulk(self, session, rows: list[dict]) -> int:
        """확정된 라벨 일괄 UPDATE. rows = [{coin, datetime, net_edge_fwd}, ...]

        **ORM 클래스가 아니라 Core 테이블로 UPDATE 한다.** SQLAlchemy 2.0 에서
        update(ORM클래스) + executemany 는 ORM bulk-update 경로로 들어가는데,
        그 경로는 커스텀 bindparam 기반 WHERE 와 맞지 않아 두 단계로 터진다:
          1) 그냥 두면 — "bulk synchronize of persistent objects not supported when
             using bulk update with additional WHERE criteria"
             (2026-10-02 21:40 ShapeLabelJob 실제 실패)
          2) synchronize_session=None 을 주면 — "per-row ORM Bulk UPDATE by Primary
             Key requires that records contain primary key values"
             (파라미터 키가 b_coin/b_datetime 이라 PK 로 인식되지 않는다)
        update(테이블) 은 Core 문장이라 ORM 기계장치를 타지 않고 의도한 대로
        단일 UPDATE 를 executemany 로 보낸다. 이 DAO 는 select() 결과를 dict 로만
        들고 영속 객체를 보유하지 않으므로 ORM 동기화가 애초에 불필요하다.
        labeled_at 은 func.now() 로 **DB 시각**을 쓴다(앱 시각을 넣으면 다른
        타임스탬프 컬럼과 기준이 어긋난다).

        ※ 백필 전까지는 갱신할 행이 0건이어서 아래 `if not rows` 에 걸려
          이 버그가 드러나지 않았다.
        """
        if not rows:
            return 0
        tbl = TradeShapeTrainDaily.__table__
        stmt = (
            update(tbl)
            .where(
                tbl.c.coin == bindparam("b_coin"),
                tbl.c.datetime == bindparam("b_datetime"),
            )
            .values(net_edge_fwd=bindparam("b_net_edge_fwd"), labeled_at=func.now())
        )
        session.execute(
            stmt,
            [
                {"b_coin": r["coin"], "b_datetime": r["datetime"],
                 "b_net_edge_fwd": r["net_edge_fwd"]}
                for r in rows
            ],
        )
        return len(rows)

    # ------------------------------------------------------------------
    # 학습 (ShapeTrainJob)
    # ------------------------------------------------------------------
    def select_training_rows(self, session, since: str | None = None,
                             until: str | None = None) -> list[dict]:
        """라벨이 확정된 학습용 행을 날짜 오름차순으로 조회한다.

        피처 14종 + datetime/coin + 라벨만 뜬다(OHLCV/평가필드는 학습에 안 쓴다 —
        수십만 행 규모라 불필요한 컬럼을 끌면 메모리만 먹는다).

        정렬은 **datetime 우선**이다. ShapeTrainJob 의 시간분할이 날짜 기준이라
        종목 우선 정렬이면 분할 경계에서 종목별로 뒤섞여 디버깅이 어렵다.
        """
        cols = [TradeShapeTrainDaily.coin, TradeShapeTrainDaily.datetime] + [
            getattr(TradeShapeTrainDaily, c) for c in SHAPE_FEATURE_COLUMNS
        ] + [TradeShapeTrainDaily.net_edge_fwd]

        stmt = select(*cols).where(TradeShapeTrainDaily.net_edge_fwd.isnot(None))
        if since:
            stmt = stmt.where(TradeShapeTrainDaily.datetime >= since)
        if until:
            stmt = stmt.where(TradeShapeTrainDaily.datetime <= until)
        stmt = stmt.order_by(TradeShapeTrainDaily.datetime, TradeShapeTrainDaily.coin)

        keys = ["coin", "datetime"] + list(SHAPE_FEATURE_COLUMNS) + ["net_edge_fwd"]
        return [dict(zip(keys, r)) for r in session.execute(stmt).all()]

    # ------------------------------------------------------------------
    # 모니터링
    # ------------------------------------------------------------------
    def count_summary(self, session) -> dict:
        """적재/라벨 현황 요약(배치 로그용)."""
        row = session.execute(
            select(
                func.count().label("total"),
                func.count(TradeShapeTrainDaily.net_edge_fwd).label("labeled"),
                func.min(TradeShapeTrainDaily.datetime).label("min_dt"),
                func.max(TradeShapeTrainDaily.datetime).label("max_dt"),
            )
        ).one()
        return {"total": row[0], "labeled": row[1], "min_dt": row[2], "max_dt": row[3]}
