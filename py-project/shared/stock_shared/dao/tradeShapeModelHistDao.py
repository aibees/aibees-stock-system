import logging

from sqlalchemy import select

from stock_shared.models.tradeShapeModelHist import TradeShapeModelHist

logging.basicConfig(level=logging.ERROR)


class TradeShapeModelHistDao:
    """shape 모델 재학습 이력(trade_shape_model_hist). 쓰기는 ShapeTrainJob 만."""

    def __init__(self):
        self.__name__ = "TradeShapeModelHistDao"

    def insert_run(self, session, row: dict) -> int:
        """학습 실행 1건 기록. 반환: 1.

        run_id 가 PK 이므로 같은 초에 두 번 돌면 충돌한다 — 그건 실제로 이상 상황
        (중복 실행)이라 조용히 덮지 않고 예외를 그대로 올린다.
        """
        session.add(TradeShapeModelHist(**row))
        return 1

    def select_last_promoted(self, session) -> dict | None:
        """가장 최근 승격 이력. 롤백 대상(backup_path) 확인용."""
        row = session.execute(
            select(TradeShapeModelHist)
            .where(TradeShapeModelHist.promote_yn == "Y")
            .order_by(TradeShapeModelHist.run_id.desc())
            .limit(1)
        ).scalars().first()
        return row.to_dict() if row else None

    def select_recent(self, session, limit: int = 20) -> list[dict]:
        """최근 실행 이력(승격 여부 무관). 지표 추이 확인용."""
        rows = session.execute(
            select(TradeShapeModelHist)
            .order_by(TradeShapeModelHist.run_id.desc())
            .limit(limit)
        ).scalars().all()
        return [r.to_dict() for r in rows]
