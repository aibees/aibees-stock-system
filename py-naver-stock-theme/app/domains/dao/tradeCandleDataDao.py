from sqlalchemy import select, and_
from sqlalchemy.dialects.mysql import insert

from app.domains.dao.baseDao import BaseDao
from app.domains.models.tradeCandleData import TradeCandleData

import logging
logging.basicConfig(level=logging.ERROR)


class TradeCandleDataDao(BaseDao):
    model = TradeCandleData

    def __init__(self):
        self.__name__ = 'TradeCandleDataDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by coin
    # ================================================================
    def select_by_coin(self, session, coin: str):
        stmt = select(TradeCandleData).where(
            TradeCandleData.coin == coin
        ).order_by(TradeCandleData.datetime.asc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by coin + datetime range
    # ================================================================
    def select_by_coin_and_range(self, session, coin: str, from_dt: str, to_dt: str):
        stmt = select(TradeCandleData).where(
            and_(
                TradeCandleData.coin == coin,
                TradeCandleData.datetime >= from_dt,
                TradeCandleData.datetime <= to_dt,
            )
        ).order_by(TradeCandleData.datetime.asc())
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select latest N rows by coin
    # ================================================================
    def select_latest(self, session, coin: str, limit: int = 100):
        stmt = select(TradeCandleData).where(
            TradeCandleData.coin == coin
        ).order_by(TradeCandleData.datetime.desc()).limit(limit)
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in reversed(results)]

    # upsert (bulk friendly)
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        stmt = insert(TradeCandleData).values(**data)
        upsert_stmt = stmt.on_duplicate_key_update(
            **{k: v for k, v in data.items() if k not in ('coin', 'datetime')}
        )
        session.execute(upsert_stmt)

    # select_candle_data: 배치 경로와 동일한 서명 (coin_code, start_date?, end_date?)
    # ================================================================
    def select_candle_data(self, session, data: dict):
        """datetime 오름차순 조회. end_date 날짜만 오면 23:59:59 보정."""
        conds = [TradeCandleData.coin == data['coin_code']]

        start_date = data.get('start_date')
        end_date   = data.get('end_date')
        if start_date:
            conds.append(TradeCandleData.datetime >= start_date)
        if end_date:
            if len(end_date) <= 10:
                end_date = end_date + ' 23:59:59'
            conds.append(TradeCandleData.datetime <= end_date)

        stmt = select(TradeCandleData).where(*conds).order_by(TradeCandleData.datetime)
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # upsert_candle_data_kis: OHLCV + 전 지표 한 번에 UPSERT (배치 경로 동일)
    # ================================================================
    def upsert_candle_data_kis(self, session, coin_info) -> None:
        """UserCoinInfo 객체를 받아 KIS 지표 전체 upsert."""
        values = dict(
            coin=coin_info.coin_code,
            datetime=coin_info.datetime,
            open=coin_info.open,
            high=coin_info.high,
            low=coin_info.low,
            close=coin_info.close,
            volume=coin_info.volume,
            ema20=coin_info.ema20,
            ema60=coin_info.ema60,
            ema120=coin_info.ema120,
            bb_mid=coin_info.bb_mid,
            bb_mid_breakout=coin_info.bb_mid_breakout,
            bb_lower=coin_info.bb_lower,
            bb_lower_chk=coin_info.bb_lower_chk,
            bb_upper=coin_info.bb_upper,
            bb_upper_chk=coin_info.bb_upper_chk,
            bb_width=coin_info.bb_width,
            bb_width_avg=coin_info.bb_width_avg,
            recent_high=coin_info.recent_high,
            macd=coin_info.macd,
            macd_s=coin_info.macd_s,
            macd_lower_mean=coin_info.macd_lower_mean,
            macd_recent_min=coin_info.macd_recent_min,
            macd_recent_max=coin_info.macd_recent_max,
            macd_upper_mean=coin_info.macd_upper_mean,
            macd_g_cross_n=coin_info.macd_g_cross_n,
            macd_d_cross_n=coin_info.macd_d_cross_n,
            obv=coin_info.obv,
            obv_signal=coin_info.obv_signal,
            obv_g_cross_n=coin_info.obv_g_cross_n,
            obv_d_cross_n=coin_info.obv_d_cross_n,
            rsi=coin_info.rsi,
            atr=coin_info.atr,
            vol_surge_n=coin_info.vol_surge_n,
        )

        stmt = insert(TradeCandleData).values(**values)
        update_cols = {k: stmt.inserted[k] for k in values if k not in ('coin', 'datetime')}
        stmt = stmt.on_duplicate_key_update(**update_cols)
        session.execute(stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
