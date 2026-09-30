from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, func

from stock_shared.base import Base


class TradeShapeModelHist(Base):
    """shape 모델 재학습 실행 이력 (19_shape_model_hist_ddl.sql).

    ShapeTrainJob 이 매 실행마다 1행 INSERT 한다(승격 여부 무관).
    live_* 가 NULL 이면 그날 라이브 모델을 같은 holdout 으로 채점할 수 없었던 것이다.
    """

    __tablename__ = "trade_shape_model_hist"

    run_id = Column(String(20), primary_key=True)
    run_ymd = Column(String(10), nullable=False)

    train_rows = Column(Integer, nullable=True)
    train_days = Column(Integer, nullable=True)
    train_pos_rate = Column(Numeric(6, 4), nullable=True)
    holdout_rows = Column(Integer, nullable=True)
    holdout_days = Column(Integer, nullable=True)
    holdout_pos_rate = Column(Numeric(6, 4), nullable=True)
    holdout_start = Column(String(10), nullable=True)
    holdout_end = Column(String(10), nullable=True)
    train_end = Column(String(10), nullable=True)
    dropped_incomplete = Column(Integer, nullable=True)
    dropped_unlabeled = Column(Integer, nullable=True)

    cand_auc = Column(Numeric(6, 4), nullable=True)
    cand_prec_at_k = Column(Numeric(6, 4), nullable=True)
    cand_lift_at_k = Column(Numeric(8, 4), nullable=True)

    live_auc = Column(Numeric(6, 4), nullable=True)
    live_prec_at_k = Column(Numeric(6, 4), nullable=True)
    live_lift_at_k = Column(Numeric(8, 4), nullable=True)

    promote_yn = Column(String(1), nullable=False, server_default="N")
    gate_reason = Column(String(1000), nullable=True)

    candidate_path = Column(String(500), nullable=True)
    backup_path = Column(String(500), nullable=True)
    sklearn_version = Column(String(20), nullable=True)
    model_params = Column(String(500), nullable=True)
    feature_cols = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
