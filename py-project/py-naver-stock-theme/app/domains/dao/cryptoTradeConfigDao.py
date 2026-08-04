from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from app.domains.models.cryptoTradeConfig import CryptoTradeConfig

import logging
logging.basicConfig(level=logging.ERROR)


class CryptoTradeConfigDao(BaseDao):
    model = CryptoTradeConfig

    def __init__(self):
        self.__name__ = 'CryptoTradeConfigDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select enabled configs
    # ================================================================
    def select_enabled(self, session):
        stmt = select(CryptoTradeConfig).where(CryptoTradeConfig.enabled_flag == 'Y')
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    # select by config_id
    # ================================================================
    def select_by_config_id(self, session, config_id: str):
        stmt = select(CryptoTradeConfig).where(CryptoTradeConfig.config_id == config_id)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # upsert
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        stmt = insert(CryptoTradeConfig).values(
            config_id=data['config_id'],
            symbol=data['symbol'],
            exchange_id=data.get('exchange_id', 'upbit'),
            timeframe=data.get('timeframe', '1d'),
            strategy_type=data.get('strategy_type', 'SQUEEZE_BREAKOUT'),
            bb_period=data.get('bb_period', 20),
            bb_std_mult=data.get('bb_std_mult', 2.00),
            rsi_period=data.get('rsi_period', 14),
            macd_fast=data.get('macd_fast', 12),
            macd_slow=data.get('macd_slow', 26),
            macd_signal=data.get('macd_signal', 9),
            obv_lookback=data.get('obv_lookback', 20),
            squeeze_lookback=data.get('squeeze_lookback', 20),
            squeeze_threshold_pct=data.get('squeeze_threshold_pct', 20.00),
            rsi_upper_limit=data.get('rsi_upper_limit', 75.00),
            rsi_lower_limit=data.get('rsi_lower_limit', 25.00),
            buy_amount_krw=data.get('buy_amount_krw', 50000.00),
            target_profit_pct=data.get('target_profit_pct', 5.00),
            stop_loss_pct=data.get('stop_loss_pct', -3.00),
            enabled_flag=data.get('enabled_flag', 'Y'),
            trail_pct=data.get('trail_pct', 0.00),
            trail_activation_pct=data.get('trail_activation_pct', 2.00),
        )
        upsert_stmt = stmt.on_duplicate_key_update(
            symbol=data['symbol'],
            exchange_id=data.get('exchange_id', 'upbit'),
            timeframe=data.get('timeframe', '1d'),
            strategy_type=data.get('strategy_type', 'SQUEEZE_BREAKOUT'),
            bb_period=data.get('bb_period', 20),
            bb_std_mult=data.get('bb_std_mult', 2.00),
            rsi_period=data.get('rsi_period', 14),
            macd_fast=data.get('macd_fast', 12),
            macd_slow=data.get('macd_slow', 26),
            macd_signal=data.get('macd_signal', 9),
            obv_lookback=data.get('obv_lookback', 20),
            squeeze_lookback=data.get('squeeze_lookback', 20),
            squeeze_threshold_pct=data.get('squeeze_threshold_pct', 20.00),
            rsi_upper_limit=data.get('rsi_upper_limit', 75.00),
            rsi_lower_limit=data.get('rsi_lower_limit', 25.00),
            buy_amount_krw=data.get('buy_amount_krw', 50000.00),
            target_profit_pct=data.get('target_profit_pct', 5.00),
            stop_loss_pct=data.get('stop_loss_pct', -3.00),
            enabled_flag=data.get('enabled_flag', 'Y'),
            trail_pct=data.get('trail_pct', 0.00),
            trail_activation_pct=data.get('trail_activation_pct', 2.00),
        )
        session.execute(upsert_stmt)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
