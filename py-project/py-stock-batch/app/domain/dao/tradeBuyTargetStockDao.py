from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.mysql import insert
from datetime import datetime
import logging

from app.domain.model.tradeBuyTargetStock import TradeBuyTargetStock

logging.basicConfig(level=logging.ERROR)


class TradeBuyTargetStockDao:
    def __init__(self):
        self.__name__ = 'TradeBuyTargetStockDao'


    def select_stock_master_list(self, session, param:dict) -> list:
        stmt = select(
            TradeBuyTargetStock
        ).where(
            TradeBuyTargetStock.ymd == param.get('ymd')
        ).order_by(
            TradeBuyTargetStock.stock_code.asc()
        )

        result = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in result]


    def delete_by_ymd(self, session, ymd: str) -> int:
        cnt = session.query(TradeBuyTargetStock).filter(
            TradeBuyTargetStock.ymd == ymd
        ).delete()
        return cnt

    def upsert_trade_buy_target_stock(self, session, data_list: list[dict]):
        """
        ymd와 stock_code를 기준으로 데이터가 없으면 Insert, 이미 존재하면 Update(Upsert)를 수행합니다.
        """
        if not data_list:
            print("Upsert할 데이터가 없습니다.")
            return

        for d in data_list:
            save_date = {
                'action_type': d['action_type'],
                'stock_code': d['stock_code'],
                'stock_name': d['stock_name'],
                'ymd': d['ymd'],
                'open': d['todayStock']['open'],
                'high': d['todayStock']['high'],
                'low': d['todayStock']['low'],
                'close': d['todayStock']['close'],
                'volume': d['todayStock']['volume'],
                'rate': d['todayStock']['rate'],
                'macd_cross': d['indicator']['macd_cross'],
                'obv_cross': d['indicator']['obv_cross'],
                'is_vol_limit': d['indicator']['is_vol_limit'],
                'is_under_bb_upper': d['indicator']['is_under_bb_upper'],
                'is_over_on_mid': d['indicator']['is_over_on_mid'],
                'is_vol_surge': d['indicator']['is_vol_surge'],
                'is_bb_mid_breakout': d['indicator']['is_bb_mid_breakout'],
                'eps': d['fin']['eps'],
                'pbr': d['fin']['pbr'],
                'per': d['fin']['per'],
                'roe': d['fin']['roe'],
                'peg': d['fin']['peg'],
                # 종합점수/순위: 랭킹 산정 후 일괄 저장 경로에서만 채워진다.
                # (단건 저장 등 미산정 상태면 None → 기존 동작과 동일)
                'score': d.get('score'),
                'rank_no': d.get('rank_no'),
            }

            # 1. MySQL 전용 insert 객체 생성
            stmt = insert(TradeBuyTargetStock).values(save_date)

            # 2. 업데이트할 컬럼 매핑 (stmt.inserted는 Insert 시도했던 새로운 데이터를 의미함)
            # 기준키인 ymd, stock_code는 업데이트에서 제외합니다.
            update_dict = {
                'stock_name': stmt.inserted['stock_name'],
                'open': stmt.inserted['open'],
                'high': stmt.inserted['high'],
                'low': stmt.inserted['low'],
                'close': stmt.inserted['close'],
                'volume': stmt.inserted['volume'],
                'rate': stmt.inserted['rate'],
                'action_type': stmt.inserted['action_type'],
                'macd_cross': stmt.inserted['macd_cross'],
                'obv_cross': stmt.inserted['obv_cross'],
                'is_vol_limit': stmt.inserted['is_vol_limit'],
                'is_under_bb_upper': stmt.inserted['is_under_bb_upper'],
                'is_over_on_mid': stmt.inserted['is_over_on_mid'],
                'is_vol_surge': stmt.inserted['is_vol_surge'],
                'is_bb_mid_breakout': stmt.inserted['is_bb_mid_breakout'],
                'eps': stmt.inserted['eps'],
                'pbr': stmt.inserted['pbr'],
                'per': stmt.inserted['per'],
                'roe': stmt.inserted['roe'],
                'peg': stmt.inserted['peg'],
                'score': stmt.inserted['score'],
                'rank_no': stmt.inserted['rank_no'],
            }

            # 3. ON DUPLICATE KEY UPDATE 구문 완성
            upsert_stmt = stmt.on_duplicate_key_update(**update_dict)

            session.execute(upsert_stmt)

    def update_rank(self, session, ymd: str, stock_code: str, score, rank_no) -> None:
        """이미 저장된 매수타겟 행의 종합점수/순위만 갱신"""
        stmt = update(TradeBuyTargetStock).where(
            and_(
                TradeBuyTargetStock.ymd == ymd,
                TradeBuyTargetStock.stock_code == stock_code,
            )
        ).values(score=score, rank_no=rank_no)
        session.execute(stmt)