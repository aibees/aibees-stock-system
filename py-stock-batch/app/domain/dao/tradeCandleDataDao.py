
from sqlalchemy import select, update, and_, func, desc, delete

from app.domain.dto.userCoinInfo import UserCoinInfo
from sqlalchemy.dialects.mysql import insert as mysql_insert
import logging
from app.domain.model.tradeCandleData import TradeCandleData

logging.basicConfig(level=logging.ERROR)


class TradeCandleDataDao:
    def __init__(self):
        self.__name__ = 'TradeCandleDataDao'

    def select_candle_data(self, session, data:dict):
        # 선택적 날짜 범위 필터 (datetime 은 'YYYY-MM-DD HH:MM:SS' varchar — 문자열 비교)
        conds = [TradeCandleData.coin == data['coin_code']]

        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date:
            conds.append(TradeCandleData.datetime >= start_date)
        if end_date:
            # 날짜만('YYYY-MM-DD') 들어오면 그날 끝까지 포함되도록 보정
            if len(end_date) <= 10:
                end_date = end_date + ' 23:59:59'
            conds.append(TradeCandleData.datetime <= end_date)

        stmt = select(
            TradeCandleData
        ).where(
            *conds
        ).order_by(TradeCandleData.datetime)

        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    def upsert_candle_data(self, session, candle_data: UserCoinInfo) -> None:
        stmt = mysql_insert(TradeCandleData).values(
            coin=candle_data.coin_code,
            datetime=candle_data.datetime,
            open=candle_data.open,
            high=candle_data.high,
            low=candle_data.low,
            close=candle_data.close,
            volume=candle_data.volume,
        )

        stmt = stmt.on_duplicate_key_update(
            open=stmt.inserted.open,
            high=stmt.inserted.high,
            low=stmt.inserted.low,
            close=stmt.inserted.close,
            volume=stmt.inserted.volume,
        )

        session.execute(stmt)

    def update_candle_regime(self, session, candle_data: UserCoinInfo) -> None:
        stmt = update(TradeCandleData).where(
            TradeCandleData.coin == candle_data.coin_code,
            TradeCandleData.datetime == candle_data.datetime,
        ).values(
            regime=candle_data.regime
        )

        session.execute(stmt)

    def update_candle_data(self, session, candle_data: UserCoinInfo) -> None:
        stmt = update(
            TradeCandleData
        ).where(
            TradeCandleData.coin == candle_data.coin_code,
            TradeCandleData.datetime == candle_data.datetime
        ).values(
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
            # obv_b=candle_data.obv_b,
            rsi=candle_data.rsi,
            rsi_signal=candle_data.rsi_signal,
            rsi_cross=candle_data.rsi_cross,
            # vol_ratio=candle_data.vol_ratio,
            score_trend=candle_data.score_trend,
            score_momentum=candle_data.score_momentum,
            score_volatility=candle_data.score_volatility,
            score_volume=candle_data.score_volume,
            score_total=candle_data.score,
            watch_action=candle_data.action,
            active_action=candle_data.active_action,
            regime=candle_data.regime
        )

        session.execute(stmt)


    def upsert_candle_data_kis(self, session, candle_data: UserCoinInfo) -> None:
        """OHLCV + KIS 지표를 한 번에 insert/update (백테스트 적재용)"""
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
        update_cols = {k: stmt.inserted[k] for k in values if k not in ('coin', 'datetime')}
        stmt = stmt.on_duplicate_key_update(**update_cols)

        session.execute(stmt)

    def update_candle_data_kis(self, session, candle_data: UserCoinInfo) -> None:
        stmt = update(
            TradeCandleData
        ).where(
            TradeCandleData.coin == candle_data.coin_code,
            TradeCandleData.datetime == candle_data.datetime
        ).values(
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
            vol_surge_n=candle_data.vol_surge_n
        )

        session.execute(stmt)