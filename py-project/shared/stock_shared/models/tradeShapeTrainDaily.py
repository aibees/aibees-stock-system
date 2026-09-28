from sqlalchemy import Column, DateTime, Numeric, PrimaryKeyConstraint, String, func

from stock_shared.base import Base


class TradeShapeTrainDaily(Base):
    """shape_proba 모델 재학습용 일별 전종목 피처 스냅샷 (16_shape_train_daily_ddl.sql).

    StockBuyCheckJob 이 매 평일 20:00 에 전종목 피처를 append 하고,
    ShapeLabelJob 이 5봉 경과분의 net_edge_fwd(라벨)를 나중에 채운다.

    피처는 **fillna(0.0) 이전 raw 값**이다 — 결측은 반드시 None 으로 들어와야 한다.
    (0 으로 채워 쌓으면 "lookback 부족"이 "관측값 0"으로 학습된다)
    """

    __tablename__ = "trade_shape_train_daily"

    __table_args__ = (PrimaryKeyConstraint("coin", "datetime"),)

    coin = Column(String(10), nullable=False)
    datetime = Column(String(10), nullable=False)

    # SHAPE_FEATURE_COLUMNS 14종 — stock_shared.ml.shape_features 와 동일 순서/이름 유지
    shape_total_ret_14 = Column(Numeric(18, 8), nullable=True)
    shape_min_ret_14 = Column(Numeric(18, 8), nullable=True)
    shape_bars_since_min = Column(Numeric(18, 8), nullable=True)
    shape_recovery_from_min = Column(Numeric(18, 8), nullable=True)
    shape_early_ret_9 = Column(Numeric(18, 8), nullable=True)
    shape_late_ret_5 = Column(Numeric(18, 8), nullable=True)
    shape_down_ratio_14 = Column(Numeric(18, 8), nullable=True)
    shape_path_std_14 = Column(Numeric(18, 8), nullable=True)
    shape_vol_trend = Column(Numeric(18, 8), nullable=True)
    ind_rsi14 = Column(Numeric(18, 8), nullable=True)
    ind_macd_hist_norm = Column(Numeric(18, 8), nullable=True)
    ind_vol_ratio_today = Column(Numeric(18, 8), nullable=True)
    obv_gap_norm = Column(Numeric(18, 8), nullable=True)
    obv_slope3 = Column(Numeric(18, 8), nullable=True)

    shape_ret_1d_today = Column(Numeric(18, 8), nullable=True)

    open = Column(Numeric(18, 8), nullable=True)
    high = Column(Numeric(18, 8), nullable=True)
    low = Column(Numeric(18, 8), nullable=True)
    close = Column(Numeric(18, 8), nullable=True)
    volume = Column(Numeric(18, 8), nullable=True)

    shape_proba_at_scan = Column(Numeric(6, 4), nullable=True)
    composite_eligible = Column(String(1), nullable=True)
    action_type = Column(String(20), nullable=True)

    net_edge_fwd = Column(Numeric(10, 4), nullable=True)
    labeled_at = Column(DateTime, nullable=True)

    scanned_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
