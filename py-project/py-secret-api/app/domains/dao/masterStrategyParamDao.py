"""
masterStrategyParamDao — master_strategy_param CRUD.

조회는 화면 렌더링 순서(group_order → sort_order)를 그대로 보장한다.
그룹 조립은 DAO 가 아니라 서비스(strategyParamGuideService)에서 한다.
"""
import logging
from datetime import datetime

from sqlalchemy import select, delete, and_

from app.domains.models.masterStrategyParam import MasterStrategyParam

logging.basicConfig(level=logging.ERROR)


class MasterStrategyParamDao:
    def __init__(self):
        self.__name__ = 'MasterStrategyParamDao'

    # 수정 가능 컬럼 화이트리스트 (PK 제외)
    UPDATABLE = {
        'group_id', 'group_title', 'group_desc', 'group_priority',
        'group_master_key', 'group_order', 'sort_order', 'label', 'unit',
        'value_type', 'ui_type', 'default_value', 'min_value', 'max_value',
        'step_value', 'null_label', 'null_slider', 'options_json',
        'disable_json', 'hint', 'enabled_flag',
    }

    # ================================================================
    # 조회 — 화면 렌더링용 (enabled_flag='Y' 만)
    # ================================================================
    def select_params(self, session, strategy_code: str, include_disabled: bool = False):
        conds = [MasterStrategyParam.strategy_code == strategy_code]
        if not include_disabled:
            conds.append(MasterStrategyParam.enabled_flag == 'Y')

        stmt = (
            select(MasterStrategyParam)
            .where(and_(*conds))
            .order_by(
                MasterStrategyParam.group_order,
                MasterStrategyParam.group_id,
                MasterStrategyParam.sort_order,
            )
        )
        return session.execute(stmt).scalars().all()

    def select_one(self, session, strategy_code: str, param_key: str):
        stmt = select(MasterStrategyParam).where(
            and_(
                MasterStrategyParam.strategy_code == strategy_code,
                MasterStrategyParam.param_key == param_key,
            )
        )
        return session.execute(stmt).scalars().first()

    # ================================================================
    # 등록 (관리자)
    # ================================================================
    def insert_param(self, session, data: dict) -> None:
        now = datetime.now()
        row = MasterStrategyParam(
            strategy_code=data['strategy_code'],
            param_key=data['param_key'],
            created_date=now,
            updated_date=now,
        )
        for col in self.UPDATABLE:
            if col in data:
                setattr(row, col, data[col])
        session.add(row)

    # ================================================================
    # 수정 (관리자) — 넘어온 컬럼만
    # ================================================================
    def update_param(self, session, strategy_code: str, param_key: str, data: dict) -> bool:
        row = self.select_one(session, strategy_code, param_key)
        if row is None:
            return False
        for col, val in data.items():
            if col in self.UPDATABLE:
                setattr(row, col, val)
        row.updated_date = datetime.now()
        return True

    # ================================================================
    # 삭제 (관리자)
    # ================================================================
    def delete_param(self, session, strategy_code: str, param_key: str) -> int:
        stmt = delete(MasterStrategyParam).where(
            and_(
                MasterStrategyParam.strategy_code == strategy_code,
                MasterStrategyParam.param_key == param_key,
            )
        )
        return session.execute(stmt).rowcount
