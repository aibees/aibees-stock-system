"""
strategyParamGuideService — 매매전략 파라미터 화면 메타 조립 / 검증.

master_strategy_param 은 단일 테이블 평탄화 구조라, 그룹 정보(group_*)가
필드 행마다 반복 저장돼 있다. 이 서비스가 group_id 로 묶어 Vue 가 그대로
v-for 를 돌릴 수 있는 그룹 배열로 변환한다.

응답 형태 (GET /api/v1/strategy/param-guide):
    {
      "strategy_code": "S1",
      "groups": [
        {
          "id": "A", "title": "...", "desc": "...", "priority": 1,
          "master": null,
          "fields": [ { "k": "s1_stop_loss_pct", "label": "손실", ... } ]
        }
      ]
    }

그룹 마스터 토글(group_master_key)로 지정된 param 은 카드 헤더에 렌더링되므로
fields 배열에서 빼고 master_field 로 따로 내려준다. FE 가 두 번 그리지 않게 하기 위함.
"""
import logging

from app.domains.dao.masterStrategyParamDao import MasterStrategyParamDao

logging.basicConfig(level=logging.ERROR)

VALUE_TYPES = {'pct', 'float', 'int', 'bool', 'enum'}
UI_TYPES = {None, '', 'stepper', 'slider'}


class StrategyParamGuideService:
    def __init__(self):
        self.dao = MasterStrategyParamDao()

    # ================================================================
    # 화면 렌더링용 그룹 트리
    # ================================================================
    def get_guide(self, session, strategy_code: str = 'S1',
                  include_disabled: bool = False) -> dict:
        rows = self.dao.select_params(session, strategy_code, include_disabled)

        groups: list[dict] = []
        index: dict[str, dict] = {}

        for r in rows:
            g = index.get(r.group_id)
            if g is None:
                g = {
                    'id': r.group_id,
                    'title': r.group_title,
                    'desc': r.group_desc,
                    'priority': r.group_priority,
                    'master': r.group_master_key,
                    'master_field': None,
                    'fields': [],
                }
                index[r.group_id] = g
                groups.append(g)

            field = r.to_field_dict()
            # 마스터 토글은 카드 헤더 전용 → fields 에서 분리
            if r.group_master_key and r.param_key == r.group_master_key:
                g['master_field'] = field
            else:
                g['fields'].append(field)

        return {'strategy_code': strategy_code, 'groups': groups}

    # ================================================================
    # 관리자 CRUD 입력 검증
    # ================================================================
    def validate(self, data: dict, for_insert: bool) -> str | None:
        """문제가 있으면 에러 메시지, 없으면 None."""
        if for_insert:
            for req in ('strategy_code', 'param_key', 'group_id', 'group_title',
                        'label', 'value_type'):
                if not data.get(req):
                    return f'{req} 는 필수입니다.'

        vt = data.get('value_type')
        if vt is not None and vt not in VALUE_TYPES:
            return f"value_type 은 {'/'.join(sorted(VALUE_TYPES))} 중 하나여야 합니다."

        ui = data.get('ui_type')
        if 'ui_type' in data and ui not in UI_TYPES:
            return "ui_type 은 stepper, slider 또는 null 이어야 합니다."

        flag = data.get('enabled_flag')
        if flag is not None and flag not in ('Y', 'N'):
            return 'enabled_flag 는 Y 또는 N 이어야 합니다.'

        # min/max/step 숫자 검증
        for col in ('min_value', 'max_value', 'step_value', 'null_slider'):
            v = data.get(col)
            if v is not None and not isinstance(v, (int, float)):
                return f'{col} 는 숫자여야 합니다.'

        mn, mx = data.get('min_value'), data.get('max_value')
        if isinstance(mn, (int, float)) and isinstance(mx, (int, float)) and mn > mx:
            return 'min_value 는 max_value 보다 클 수 없습니다.'

        for col in ('group_priority', 'group_order', 'sort_order'):
            v = data.get(col)
            if v is not None and not isinstance(v, int):
                return f'{col} 는 정수여야 합니다.'

        # enum 이면 선택지 필수
        if vt == 'enum':
            opts = data.get('options_json')
            if not isinstance(opts, list) or not opts:
                return "value_type=enum 이면 options_json 이 비어 있을 수 없습니다."
            for o in opts:
                if not isinstance(o, dict) or 'v' not in o or 'label' not in o:
                    return "options_json 항목은 {'v':..., 'label':...} 형태여야 합니다."

        # disable_json 형태 검증
        dj = data.get('disable_json')
        if dj is not None:
            if not isinstance(dj, dict):
                return 'disable_json 은 객체여야 합니다.'
            for key in dj:
                if key not in ('onFalse', 'onBlank'):
                    return f"disable_json 의 키는 onFalse/onBlank 만 허용합니다: {key}"
                if not isinstance(dj[key], list):
                    return f'disable_json.{key} 는 배열이어야 합니다.'

        return None
