"""
trade_candle_30m DAO — M3 30분봉 전용.

TradeCandleDataDao(일봉) 와 쿼리 형태가 같지만 대상 모델이 다르다.
중복을 줄이려 상속하지 않는 이유: 부모가 모듈 상수 TradeCandleData 를
직접 참조하는 구조라 모델만 갈아끼울 수 없다. 필요한 3개 메서드만 둔다.
"""
import logging

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.models.tradeCandle30m import TradeCandle30m

logging.basicConfig(level=logging.ERROR)

_PK = ("coin", "datetime")

# compute_indicator_df 결과에서 적재하는 컬럼.
# tradeCandleDataDao._KIS_COLS 와 동일하게 유지할 것.
_KIS_COLS = (
    "open", "high", "low", "close", "volume",
    "ema20", "ema60", "ema120",
    "bb_mid", "bb_mid_breakout", "bb_lower", "bb_lower_chk",
    "bb_upper", "bb_upper_chk", "bb_width", "bb_width_avg", "recent_high",
    "macd", "macd_s", "macd_lower_mean", "macd_upper_mean",
    "macd_recent_min", "macd_recent_max", "macd_g_cross_n", "macd_d_cross_n",
    "obv", "obv_signal", "obv_g_cross_n", "obv_d_cross_n",
    "rsi", "atr", "vol_surge_n",
)


def _clean(v):
    """NaN/NaT → None. pandas 값이 그대로 넘어가면 MySQL 이 거부한다."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN 은 자기 자신과 다르다
        return None
    return v


class TradeCandle30mDao(BaseDao):
    model = TradeCandle30m

    def __init__(self):
        self.__name__ = "TradeCandle30mDao"

    # ------------------------------------------------------------------
    # select
    # ------------------------------------------------------------------
    def select_latest(self, session, coin: str, limit: int = 250) -> list:
        """최근 N봉을 **시간 오름차순**으로 반환.

        M3 분석의 기본 진입점. 지표 계산은 오름차순 전제이므로
        DESC LIMIT 로 뽑은 뒤 뒤집어 준다.
        """
        stmt = (
            select(TradeCandle30m)
            .where(TradeCandle30m.coin == coin)
            .order_by(TradeCandle30m.datetime.desc())
            .limit(limit)
        )
        rows = session.execute(stmt).scalars().all()
        return [r.to_dict() for r in reversed(rows)]

    def select_by_range(self, session, coin: str, from_dt: str, to_dt: str) -> list:
        """datetime 범위 조회 (오름차순).

        datetime 은 'YYYY-MM-DD HH:MM:SS' varchar 라 문자열 비교로 동작한다.
        to_dt 가 날짜만('YYYY-MM-DD') 오면 하루 끝까지로 보정한다.
        """
        if to_dt and len(to_dt) <= 10:
            to_dt = to_dt + " 23:59:59"
        stmt = (
            select(TradeCandle30m)
            .where(and_(
                TradeCandle30m.coin == coin,
                TradeCandle30m.datetime >= from_dt,
                TradeCandle30m.datetime <= to_dt,
            ))
            .order_by(TradeCandle30m.datetime.asc())
        )
        rows = session.execute(stmt).scalars().all()
        return [r.to_dict() for r in rows]

    def count_by_coin(self, session, coin: str) -> int:
        """적재된 봉 수. 백필 충분성 판단용."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(TradeCandle30m).where(
            TradeCandle30m.coin == coin)
        return int(session.execute(stmt).scalar() or 0)

    def select_bounds(self, session, coin: str) -> dict:
        """적재 구간 (min/max datetime). 백필 재개 지점 판단용."""
        from sqlalchemy import func
        stmt = select(
            func.min(TradeCandle30m.datetime),
            func.max(TradeCandle30m.datetime),
        ).where(TradeCandle30m.coin == coin)
        first, last = session.execute(stmt).one()
        return {"first": first, "last": last}

    # ------------------------------------------------------------------
    # upsert
    # ------------------------------------------------------------------
    def upsert_candle_bulk(self, session, coin: str, records: list,
                           chunk_size: int = 500) -> int:
        """compute_indicator_df 결과(records)를 통째로 UPSERT.

        records = df.to_dict(orient='records') 를 그대로 받는다.
        PK(coin, datetime) 기준이라 재실행해도 중복이 쌓이지 않고 최신값으로 덮인다.
        → 당일 봉을 30분마다 전량 덮어쓰는 갱신 방식이 안전하게 성립한다.

        반환: 적재 시도한 행 수.
        """
        if not records:
            return 0

        rows = []
        for r in records:
            dt = r.get("datetime")
            if not dt:
                continue                      # PK 없는 행은 버린다
            row = {"coin": coin, "datetime": str(dt)[:19]}
            for c in _KIS_COLS:
                row[c] = _clean(r.get(c))
            rows.append(row)

        if not rows:
            return 0

        for i in range(0, len(rows), chunk_size):
            batch = rows[i:i + chunk_size]
            stmt = mysql_insert(TradeCandle30m).values(batch)
            stmt = stmt.on_duplicate_key_update(
                **{k: stmt.inserted[k] for k in batch[0] if k not in _PK}
            )
            session.execute(stmt)

        return len(rows)

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------
    def delete_by_day(self, session, coin: str, ymd: str) -> None:
        """특정 일자 봉 전체 삭제 (YYYY-MM-DD). 재수집 전 정리용."""
        stmt = delete(TradeCandle30m).where(and_(
            TradeCandle30m.coin == coin,
            TradeCandle30m.datetime >= f"{ymd} 00:00:00",
            TradeCandle30m.datetime <= f"{ymd} 23:59:59",
        ))
        session.execute(stmt)
