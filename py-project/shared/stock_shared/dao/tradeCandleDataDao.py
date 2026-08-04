import logging

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.tradeCandleData import TradeCandleData
from stock_shared.vo.userCoinInfo import UserCoinInfo

logging.basicConfig(level=logging.ERROR)

_PK = ("coin", "datetime")


class TradeCandleDataDao(BaseDao):
    model = TradeCandleData

    def __init__(self):
        self.__name__ = "TradeCandleDataDao"

    # ------------------------------------------------------------------
    # select
    # ------------------------------------------------------------------
    def select_by_coin(self, session, coin: str):
        """종목 전체 캔들 조회 (datetime 오름차순)."""
        stmt = (
            select(TradeCandleData)
            .where(TradeCandleData.coin == coin)
            .order_by(TradeCandleData.datetime.asc())
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    def select_by_coin_and_range(self, session, coin: str, from_dt: str, to_dt: str):
        """종목 + datetime 범위 조회."""
        stmt = (
            select(TradeCandleData)
            .where(
                and_(
                    TradeCandleData.coin == coin,
                    TradeCandleData.datetime >= from_dt,
                    TradeCandleData.datetime <= to_dt,
                )
            )
            .order_by(TradeCandleData.datetime.asc())
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    def select_latest(self, session, coin: str, limit: int = 100):
        """최근 N건을 시간 오름차순으로 반환."""
        stmt = (
            select(TradeCandleData)
            .where(TradeCandleData.coin == coin)
            .order_by(TradeCandleData.datetime.desc())
            .limit(limit)
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in reversed(results)]

    def select_candle_data(self, session, data: dict):
        """
        datetime 오름차순 조회.

        datetime 은 'YYYY-MM-DD HH:MM:SS' varchar 이므로 문자열 비교를 사용한다.
        end_date 가 날짜만('YYYY-MM-DD') 오면 23:59:59 로 보정한다.
        """
        conds = [TradeCandleData.coin == data["coin_code"]]

        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date:
            conds.append(TradeCandleData.datetime >= start_date)
        if end_date:
            if len(end_date) <= 10:
                end_date = end_date + " 23:59:59"
            conds.append(TradeCandleData.datetime <= end_date)

        stmt = (
            select(TradeCandleData).where(*conds).order_by(TradeCandleData.datetime)
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # ------------------------------------------------------------------
    # upsert / update
    # ------------------------------------------------------------------
    def upsert(self, session, data: dict) -> None:
        """dict 기반 범용 upsert (PK 제외 전 컬럼 갱신)."""
        stmt = mysql_insert(TradeCandleData).values(**data)
        upsert_stmt = stmt.on_duplicate_key_update(
            **{k: v for k, v in data.items() if k not in _PK}
        )
        session.execute(upsert_stmt)

    def upsert_candle_data(self, session, candle_data: UserCoinInfo) -> None:
        """OHLCV 만 upsert."""
        values = dict(
            coin=candle_data.coin_code,
            datetime=candle_data.datetime,
            open=candle_data.open,
            high=candle_data.high,
            low=candle_data.low,
            close=candle_data.close,
            volume=candle_data.volume,
        )
        stmt = mysql_insert(TradeCandleData).values(**values)
        stmt = stmt.on_duplicate_key_update(
            **{k: stmt.inserted[k] for k in values if k not in _PK}
        )
        session.execute(stmt)

    def upsert_candle_data_kis(self, session, candle_data: UserCoinInfo) -> None:
        """OHLCV + KIS 지표를 한 번에 insert/update (백테스트 적재용)."""
        values = dict(
            coin=candle_data.coin_code,
            datetime=candle_data.datetime,
            open=candle_data.open,
            high=candle_data.high,
            low=candle_data.low,
            close=candle_data.close,
            volume=candle_data.volume,
            ema20=candle_data.ema20,
            ema60=candle_data.ema60,
            ema120=candle_data.ema120,
            bb_mid=candle_data.bb_mid,
            bb_mid_breakout=candle_data.bb_mid_breakout,
            bb_lower=candle_data.bb_lower,
            bb_lower_chk=candle_data.bb_lower_chk,
            bb_upper=candle_data.bb_upper,
            bb_upper_chk=candle_data.bb_upper_chk,
            bb_width=candle_data.bb_width,
            bb_width_avg=candle_data.bb_width_avg,
            recent_high=candle_data.recent_high,
            macd=candle_data.macd,
            macd_s=candle_data.macd_s,
            macd_lower_mean=candle_data.macd_lower_mean,
            macd_recent_min=candle_data.macd_recent_min,
            macd_recent_max=candle_data.macd_recent_max,
            macd_upper_mean=candle_data.macd_upper_mean,
            macd_g_cross_n=candle_data.macd_g_cross_n,
            macd_d_cross_n=candle_data.macd_d_cross_n,
            obv=candle_data.obv,
            obv_signal=candle_data.obv_signal,
            obv_g_cross_n=candle_data.obv_g_cross_n,
            obv_d_cross_n=candle_data.obv_d_cross_n,
            rsi=candle_data.rsi,
            atr=candle_data.atr,
            vol_surge_n=candle_data.vol_surge_n,
        )

        stmt = mysql_insert(TradeCandleData).values(**values)
        # PK(coin, datetime) 제외한 전 컬럼을 갱신
        stmt = stmt.on_duplicate_key_update(
            **{k: stmt.inserted[k] for k in values if k not in _PK}
        )
        session.execute(stmt)

    def update_candle_regime(self, session, candle_data: UserCoinInfo) -> None:
        """regime 컬럼만 갱신."""
        stmt = (
            update(TradeCandleData)
            .where(
                TradeCandleData.coin == candle_data.coin_code,
                TradeCandleData.datetime == candle_data.datetime,
            )
            .values(regime=candle_data.regime)
        )
        session.execute(stmt)

    def update_candle_data(self, session, candle_data: UserCoinInfo) -> None:
        """업비트 경로 지표 일괄 갱신."""
        stmt = (
            update(TradeCandleData)
            .where(
                TradeCandleData.coin == candle_data.coin_code,
                TradeCandleData.datetime == candle_data.datetime,
            )
            .values(
                ema20=candle_data.ema20,
                ema60=candle_data.ema60,
                ema120=candle_data.ema120,
                bb_mid=candle_data.bb_mid,
                bb_lower=candle_data.bb_lower,
                bb_lower_chk=candle_data.bb_lower_chk,
                bb_upper=candle_data.bb_upper,
                bb_upper_chk=candle_data.bb_upper_chk,
                bb_width=candle_data.bb_width,
                bb_width_avg=candle_data.bb_width_avg,
                macd=candle_data.macd,
                macd_s=candle_data.macd_s,
                macd_lower_mean=candle_data.macd_lower_mean,
                macd_recent_min=candle_data.macd_recent_min,
                macd_recent_max=candle_data.macd_recent_max,
                macd_upper_mean=candle_data.macd_upper_mean,
                fs_k=candle_data.fs_k,
                fs_d=candle_data.fs_d,
                roc=candle_data.roc,
                atr=candle_data.atr,
                obv=candle_data.obv,
                obv_signal=candle_data.obv_signal,
                obv_cross=candle_data.obv_cross,
                obv_recent_max=candle_data.obv_recent_max,
                obv_recent_min=candle_data.obv_recent_min,
                rsi=candle_data.rsi,
                rsi_signal=candle_data.rsi_signal,
                rsi_cross=candle_data.rsi_cross,
                score_trend=candle_data.score_trend,
                score_momentum=candle_data.score_momentum,
                score_volatility=candle_data.score_volatility,
                score_volume=candle_data.score_volume,
                score_total=candle_data.score,
                watch_action=candle_data.action,
                active_action=candle_data.active_action,
                regime=candle_data.regime,
            )
        )
        session.execute(stmt)

    def update_candle_data_kis(self, session, candle_data: UserCoinInfo) -> None:
        """KIS 경로 지표 일괄 갱신."""
        stmt = (
            update(TradeCandleData)
            .where(
                TradeCandleData.coin == candle_data.coin_code,
                TradeCandleData.datetime == candle_data.datetime,
            )
            .values(
                ema20=candle_data.ema20,
                ema60=candle_data.ema60,
                ema120=candle_data.ema120,
                bb_mid=candle_data.bb_mid,
                bb_mid_breakout=candle_data.bb_mid_breakout,
                bb_lower=candle_data.bb_lower,
                bb_lower_chk=candle_data.bb_lower_chk,
                bb_upper=candle_data.bb_upper,
                bb_upper_chk=candle_data.bb_upper_chk,
                bb_width=candle_data.bb_width,
                bb_width_avg=candle_data.bb_width_avg,
                macd=candle_data.macd,
                macd_s=candle_data.macd_s,
                macd_lower_mean=candle_data.macd_lower_mean,
                macd_recent_min=candle_data.macd_recent_min,
                macd_recent_max=candle_data.macd_recent_max,
                macd_upper_mean=candle_data.macd_upper_mean,
                macd_g_cross_n=candle_data.macd_g_cross_n,
                macd_d_cross_n=candle_data.macd_d_cross_n,
                obv=candle_data.obv,
                obv_signal=candle_data.obv_signal,
                obv_cross=candle_data.obv_cross,
                obv_recent_max=candle_data.obv_recent_max,
                obv_recent_min=candle_data.obv_recent_min,
                obv_g_cross_n=candle_data.obv_g_cross_n,
                obv_d_cross_n=candle_data.obv_d_cross_n,
                vol_surge_n=candle_data.vol_surge_n,
            )
        )
        session.execute(stmt)
