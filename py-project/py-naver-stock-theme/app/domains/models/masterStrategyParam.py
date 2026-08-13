"""
master_strategy_param — 매매전략 파라미터 조정 화면(TradeSetting) 메타 엔티티.

Vue 에 하드코딩돼 있던 GROUPS 상수를 DB 로 옮긴 것.
그룹 정보(group_*)는 필드 행마다 반복 저장(단일 테이블 평탄화)하고,
서비스단(strategyParamGuideService)에서 group_id 로 묶어 그룹 배열을 만든다.

DDL: py-project/sql/master_strategy_param.sql
"""
from sqlalchemy import Column, String, Integer, DateTime, PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import DECIMAL, JSON

from stock_shared.base import Base


class MasterStrategyParam(Base):
    __tablename__ = 'master_strategy_param'

    # ── 식별 ──────────────────────────────────────────────────────────
    strategy_code = Column(String(10), nullable=False)   # 'S1' = KospiStrategy0
    param_key = Column(String(64), nullable=False)       # user_options 컬럼명

    # ── 그룹(평탄화) ──────────────────────────────────────────────────
    group_id = Column(String(4), nullable=False)
    group_title = Column(String(100), nullable=False)
    group_desc = Column(String(500), nullable=True)
    group_priority = Column(Integer, nullable=False, default=0)
    group_master_key = Column(String(64), nullable=True)
    group_order = Column(Integer, nullable=False, default=0)

    # ── 필드 ──────────────────────────────────────────────────────────
    sort_order = Column(Integer, nullable=False, default=0)
    label = Column(String(100), nullable=False)
    unit = Column(String(10), nullable=True)
    value_type = Column(String(10), nullable=False)      # pct/float/int/bool/enum
    ui_type = Column(String(20), nullable=True)          # stepper | None(slider)

    default_value = Column(String(50), nullable=True)    # 내부 저장 단위 문자열
    min_value = Column(DECIMAL(14, 4), nullable=True)
    max_value = Column(DECIMAL(14, 4), nullable=True)
    step_value = Column(DECIMAL(14, 4), nullable=True)

    null_label = Column(String(20), nullable=True)
    null_slider = Column(DECIMAL(14, 4), nullable=True)

    options_json = Column(JSON, nullable=True)           # enum 선택지
    disable_json = Column(JSON, nullable=True)           # 조건부 비활성 규칙

    hint = Column(String(500), nullable=True)

    # ── 공통 ──────────────────────────────────────────────────────────
    enabled_flag = Column(String(1), nullable=False, default='Y')
    created_date = Column(DateTime, nullable=True)
    updated_date = Column(DateTime, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('strategy_code', 'param_key'),
    )

    # ── 직렬화 ────────────────────────────────────────────────────────
    @staticmethod
    def _num(v):
        """DECIMAL → float (JSON 직렬화 및 FE 숫자 비교용). None 은 그대로."""
        return float(v) if v is not None else None

    def to_field_dict(self) -> dict:
        """FE 필드 1건 포맷. Vue 의 기존 필드 객체 키와 맞춘다.

        default_value 는 DB 에 문자열로 저장되므로 value_type 기준으로 캐스팅한다.
        NULL 이면 '기본값 없음(미사용)' 을 뜻하므로 None 을 유지한다.
        """
        return {
            'k': self.param_key,
            'label': self.label,
            'unit': self.unit,
            'type': self.value_type,
            'ui': self.ui_type,
            'def': self._cast_default(),
            'min': self._num(self.min_value),
            'max': self._num(self.max_value),
            'step': self._num(self.step_value),
            'nullLabel': self.null_label,
            'nullSlider': self._num(self.null_slider),
            'options': self.options_json,
            'disable': self.disable_json,
            'hint': self.hint,
            'sortOrder': self.sort_order,
        }

    def _cast_default(self):
        v = self.default_value
        if v is None or v == '':
            return None
        t = self.value_type
        try:
            if t in ('pct', 'float'):
                return float(v)
            if t in ('int', 'bool'):
                return int(float(v))
        except (TypeError, ValueError):
            return None
        return v          # enum 등 문자열 그대로

    def to_dict(self) -> dict:
        """관리자 CRUD 응답용 원본 포맷(컬럼명 그대로)."""
        return {
            'strategy_code': self.strategy_code,
            'param_key': self.param_key,
            'group_id': self.group_id,
            'group_title': self.group_title,
            'group_desc': self.group_desc,
            'group_priority': self.group_priority,
            'group_master_key': self.group_master_key,
            'group_order': self.group_order,
            'sort_order': self.sort_order,
            'label': self.label,
            'unit': self.unit,
            'value_type': self.value_type,
            'ui_type': self.ui_type,
            'default_value': self.default_value,
            'min_value': self._num(self.min_value),
            'max_value': self._num(self.max_value),
            'step_value': self._num(self.step_value),
            'null_label': self.null_label,
            'null_slider': self._num(self.null_slider),
            'options_json': self.options_json,
            'disable_json': self.disable_json,
            'hint': self.hint,
            'enabled_flag': self.enabled_flag,
        }
