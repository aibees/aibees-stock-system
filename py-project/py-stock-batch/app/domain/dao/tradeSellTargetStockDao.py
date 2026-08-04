from datetime import datetime
from sqlalchemy import select, update, and_
from sqlalchemy.dialects.mysql import insert

from app.domain.model.tradeSellTargetStock import TradeSellTargetStock


class TradeSellTargetStockDao:
    def __init__(self):
        self.__name__ = 'TradeSellTargetStockDao'

    # ── 조회 ──────────────────────────────────────────────────────────────
    def select_active_list(self, session, user_id: int) -> list:
        """user_id 기준 status='active'인 매도 모니터링 종목 조회"""
        stmt = select(TradeSellTargetStock).where(
            TradeSellTargetStock.user_id == user_id,
            TradeSellTargetStock.status == 'active'
        ).order_by(TradeSellTargetStock.stock_code.asc())

        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]

    def select_by_user_and_code(self, session, user_id: int, stock_code: str) -> dict | None:
        """복합 PK(user_id + stock_code) 기준 단건 조회"""
        stmt = select(TradeSellTargetStock).where(
            TradeSellTargetStock.user_id == user_id,
            TradeSellTargetStock.stock_code == stock_code,
        )
        obj = session.execute(stmt).scalars().first()
        return obj.to_dict() if obj else None

    # ── Upsert (배치에서 stock_sell_request 기반으로 자동 생성/갱신) ────────
    def upsert_check_result(self, session, data: dict) -> None:
        """
        체크 결과 전체를 upsert.
        - 행이 없으면 INSERT (진입 정보 + 초기 포지션 추적값 포함)
        - 행이 있으면 시세/판단/포지션 추적값만 UPDATE (진입 정보·created_at 보존)

        data 필수 키: user_id, stock_code
        진입 정보 키: stock_name, entry_date, entry_price, hold_qty
        체크 결과 키: curr_open/high/low/close/volume/rate,
                     bars_held, peak_close, peak_high, bars_since_peak, last_check_ymd,
                     action_type, profit_pct, stop_price, target_price, trail_line, sell_reason
        """
        now = datetime.now()
        entry_price = float(data.get('entry_price') or 0)

        row = {
            'user_id':         data['user_id'],
            'stock_code':      data['stock_code'],
            'stock_name':      data.get('stock_name', ''),
            'entry_date':      data.get('entry_date', ''),
            'entry_price':     entry_price,
            'entry_atr':       data.get('entry_atr', 0),
            'hold_qty':        data.get('hold_qty', 0),
            # 포지션 추적
            'bars_held':       data.get('bars_held', 0),
            'peak_close':      data.get('peak_close', entry_price),
            'peak_high':       data.get('peak_high', entry_price),
            'bars_since_peak': data.get('bars_since_peak', 0),
            'last_check_ymd':  data.get('last_check_ymd', ''),
            # 현재 시세
            'curr_open':       data.get('curr_open'),
            'curr_high':       data.get('curr_high'),
            'curr_low':        data.get('curr_low'),
            'curr_close':      data.get('curr_close'),
            'curr_volume':     data.get('curr_volume'),
            'curr_rate':       data.get('curr_rate'),
            # 매도 판단
            'action_type':     data.get('action_type', 'HOLD'),
            'profit_pct':      data.get('profit_pct'),
            'stop_price':      data.get('stop_price'),
            'target_price':    data.get('target_price'),
            'trail_line':      data.get('trail_line'),
            'sell_reason':     data.get('sell_reason'),
            # 상태
            'status':          'active',
            'checked_at':      now,
            'created_at':      now,
            'updated_at':      now,
        }

        stmt = insert(TradeSellTargetStock).values(row)
        # 기존 행이 있으면 포지션 추적 + 시세 + 판단 결과만 덮어씀
        # 진입 정보(entry_date, entry_price 등)·created_at은 최초 INSERT 값 유지
        stmt = stmt.on_duplicate_key_update(
            stock_name=stmt.inserted['stock_name'],
            hold_qty=stmt.inserted['hold_qty'],
            bars_held=stmt.inserted['bars_held'],
            peak_close=stmt.inserted['peak_close'],
            peak_high=stmt.inserted['peak_high'],
            bars_since_peak=stmt.inserted['bars_since_peak'],
            last_check_ymd=stmt.inserted['last_check_ymd'],
            curr_open=stmt.inserted['curr_open'],
            curr_high=stmt.inserted['curr_high'],
            curr_low=stmt.inserted['curr_low'],
            curr_close=stmt.inserted['curr_close'],
            curr_volume=stmt.inserted['curr_volume'],
            curr_rate=stmt.inserted['curr_rate'],
            action_type=stmt.inserted['action_type'],
            profit_pct=stmt.inserted['profit_pct'],
            stop_price=stmt.inserted['stop_price'],
            target_price=stmt.inserted['target_price'],
            trail_line=stmt.inserted['trail_line'],
            sell_reason=stmt.inserted['sell_reason'],
            checked_at=stmt.inserted['checked_at'],
            updated_at=stmt.inserted['updated_at'],
        )
        session.execute(stmt)

    # ── 갱신 (배치에서 체크 후 호출) ─────────────────────────────────────
    def update_check_result(self, session, data: dict) -> None:
        """
        매도 판단 결과 + 현재 시세 + 포지션 추적 값 일괄 업데이트.
        data 키: user_id, stock_code, action_type, profit_pct, stop_price, target_price,
                 trail_line, sell_reason,
                 curr_open, curr_high, curr_low, curr_close, curr_volume, curr_rate,
                 bars_held, peak_close, peak_high, bars_since_peak, last_check_ymd
        """
        stmt = update(TradeSellTargetStock).where(
            TradeSellTargetStock.user_id == data['user_id'],
            TradeSellTargetStock.stock_code == data['stock_code'],
        ).values(
            # 현재 시세
            curr_open=data.get('curr_open'),
            curr_high=data.get('curr_high'),
            curr_low=data.get('curr_low'),
            curr_close=data.get('curr_close'),
            curr_volume=data.get('curr_volume'),
            curr_rate=data.get('curr_rate'),
            # 포지션 추적
            bars_held=data.get('bars_held'),
            peak_close=data.get('peak_close'),
            peak_high=data.get('peak_high'),
            bars_since_peak=data.get('bars_since_peak'),
            last_check_ymd=data.get('last_check_ymd'),
            # 매도 판단
            action_type=data.get('action_type', 'HOLD'),
            profit_pct=data.get('profit_pct'),
            stop_price=data.get('stop_price'),
            target_price=data.get('target_price'),
            trail_line=data.get('trail_line'),
            sell_reason=data.get('sell_reason'),
            # 타임스탬프
            checked_at=datetime.now(),
            updated_at=datetime.now(),
        )
        session.execute(stmt)

    def update_status(self, session, user_id: int, stock_code: str, status: str) -> None:
        """status 변경 (예: 매도 체결 후 'sold' 처리)"""
        stmt = update(TradeSellTargetStock).where(
            TradeSellTargetStock.user_id == user_id,
            TradeSellTargetStock.stock_code == stock_code,
        ).values(status=status, updated_at=datetime.now())
        session.execute(stmt)
