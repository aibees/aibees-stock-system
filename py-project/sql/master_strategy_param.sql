-- =============================================================================
-- master_strategy_param — 매매전략 파라미터 조정 화면(TradeSetting) 메타
--
-- 목적: Vue 에 하드코딩돼 있던 GROUPS 상수(그룹 제목/설명/우선순위 + 필드별
--       label·unit·type·min·max·step·default·hint·disable 규칙)를 DB 로 이관.
--       화면은 GET /api/v1/strategy/param-guide 로 이 테이블을 읽어 렌더링한다.
--
-- 구조: 단일 테이블. 그룹 정보(group_*)는 필드 행마다 반복 저장(평탄화)하고
--       서비스단에서 group_id 로 묶어 그룹 배열을 조립한다.
--
-- 적용 대상: stock, stock_dev  (아래 USE 를 바꿔 각각 실행)
-- =============================================================================

-- USE stock_dev;

DROP TABLE IF EXISTS master_strategy_param;

CREATE TABLE master_strategy_param (
    -- ── 식별 ──────────────────────────────────────────────────────────
    strategy_code     VARCHAR(10)   NOT NULL                  COMMENT '전략 코드. S1=KospiStrategy1',
    param_key         VARCHAR(64)   NOT NULL                  COMMENT 'user_options 컬럼명. 예) s1_stop_loss_pct',

    -- ── 그룹(평탄화) ──────────────────────────────────────────────────
    group_id          VARCHAR(4)    NOT NULL                  COMMENT '그룹 식별자 A~D',
    group_title       VARCHAR(100)  NOT NULL                  COMMENT '그룹 카드 제목',
    group_desc        VARCHAR(500)      NULL                  COMMENT '그룹 설명. <br/> 등 간단한 HTML 허용',
    group_priority    INT           NOT NULL DEFAULT 0        COMMENT '매도 판정 우선순위 배지(1 손절 > 2 익절 > 3 트레일링 > 4 타임스탑)',
    group_master_key  VARCHAR(64)       NULL                  COMMENT '그룹 마스터 토글 param_key. 예) s1_use_trailing',
    group_order       INT           NOT NULL DEFAULT 0        COMMENT '그룹 정렬 순서',

    -- ── 필드 ──────────────────────────────────────────────────────────
    sort_order        INT           NOT NULL DEFAULT 0        COMMENT '그룹 내 필드 정렬 순서',
    label             VARCHAR(100)  NOT NULL                  COMMENT '필드 라벨',
    unit              VARCHAR(10)       NULL                  COMMENT "표시 단위. '%','배','봉'. 없으면 NULL",
    value_type        VARCHAR(10)   NOT NULL                  COMMENT "pct(내부 소수·화면 %) / float / int / bool / enum",
    ui_type           VARCHAR(20)       NULL                  COMMENT "stepper 면 +/- 버튼, NULL 이면 slider+number",

    default_value     VARCHAR(50)       NULL                  COMMENT '전략 클래스 기본값(내부 저장 단위 문자열). NULL 이면 미설정이 기본',
    min_value         DECIMAL(14,4)     NULL                  COMMENT '화면 표시 단위 기준 최솟값',
    max_value         DECIMAL(14,4)     NULL                  COMMENT '화면 표시 단위 기준 최댓값',
    step_value        DECIMAL(14,4)     NULL                  COMMENT '화면 표시 단위 기준 증감폭',

    null_label        VARCHAR(20)       NULL                  COMMENT "비우기 버튼 문구. NULL 이면 '기본값'. 예) '미사용'",
    null_slider       DECIMAL(14,4)     NULL                  COMMENT 'default_value 가 NULL 일 때 슬라이더 시작 위치(표시 단위)',

    options_json      JSON              NULL                  COMMENT 'enum 선택지. [{"v":"close","label":"종가 고점"}]',
    disable_json      JSON              NULL                  COMMENT '조건부 비활성 규칙. {"onFalse":["s1_use_trailing"],"onBlank":["s1_trail_drawdown_pct"]}',

    hint              VARCHAR(500)      NULL                  COMMENT '필드 하단 안내 문구',

    -- ── 공통 ──────────────────────────────────────────────────────────
    enabled_flag      CHAR(1)       NOT NULL DEFAULT 'Y'      COMMENT '노출 여부 Y/N',
    created_date      DATETIME          NULL,
    updated_date      DATETIME          NULL,

    PRIMARY KEY (strategy_code, param_key),
    KEY idx_msp_render (strategy_code, enabled_flag, group_order, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='매매전략 파라미터 화면 메타';


-- =============================================================================
-- 시드 데이터 — TradeSetting.vue GROUPS 상수와 1:1
-- =============================================================================
INSERT INTO master_strategy_param
(strategy_code, param_key, group_id, group_title, group_desc, group_priority, group_master_key, group_order,
 sort_order, label, unit, value_type, ui_type, default_value, min_value, max_value, step_value,
 null_label, null_slider, options_json, disable_json, hint, enabled_flag, created_date, updated_date)
VALUES

-- ── A. 손실 감수매도 기준 ────────────────────────────────────────────
('S1', 's1_stop_loss_pct', 'A', '손실 감수매도 기준',
 '일정% 손절 또는 OBV 데드크로스(세력 청산 신호). <br/>가장 먼저 평가되는 최우선 조건입니다.', 1, NULL, 1,
 1, '손실', '%', 'pct', NULL, '0.05', 2, 15, 0.5,
 NULL, NULL, NULL, NULL,
 '진입가 대비 −N% 하회 시 전량 손절합니다.', 'Y', NOW(), NOW()),

('S1', 's1_obv_dead_min_bars', 'A', '손실 감수매도 기준',
 '일정% 손절 또는 OBV 데드크로스(세력 청산 신호). <br/>가장 먼저 평가되는 최우선 조건입니다.', 1, NULL, 1,
 2, 'OBV 데드크로스 무시 봉 갯수', NULL, 'int', 'stepper', '5', 0, 20, 1,
 NULL, NULL, NULL, NULL,
 '진입 후 이 봉수 이내의 OBV 데드크로스는 노이즈로 보고 무시합니다.', 'Y', NOW(), NOW()),

-- ── B. 이익 실현매도 기준 ────────────────────────────────────────────
('S1', 's1_take_profit_pct', 'B', '이익 실현매도 기준',
 '진입가 대비 목표 수익 도달 시 전량 익절합니다.', 2, NULL, 2,
 1, '이익', '%', 'pct', NULL, '0.30', 5, 100, 5,
 NULL, NULL, NULL, NULL,
 '진입가 대비 +N% 도달 시 전량 익절합니다.', 'Y', NOW(), NOW()),

-- ── C. 트레일링 스탑 ─────────────────────────────────────────────────
('S1', 's1_trail_activate_pct', 'C', '트레일링 스탑',
 '매수 시점부터 실시간 체결가로 고점을 추적하고, 그 고점에서 설정폭만큼 하락하면 청산합니다. <br/>비활성화하면 손절/익절 뿐입니다.', 3, 's1_use_trailing', 3,
 1, '활성화 기준', '%', 'pct', NULL, '0.08', 0, 50, 1,
 NULL, NULL, NULL, JSON_OBJECT('onFalse', JSON_ARRAY('s1_use_trailing')),
 '매입가 기준 해당 설정 % 이상일 때만 트레일링이 켜집니다.', 'Y', NOW(), NOW()),

('S1', 's1_k_trail_atr', 'C', '트레일링 스탑',
 '매수 시점부터 실시간 체결가로 고점을 추적하고, 그 고점에서 설정폭만큼 하락하면 청산합니다. <br/>비활성화하면 손절/익절 뿐입니다.', 3, 's1_use_trailing', 3,
 2, 'ATR 배수 (k)', '배', 'float', NULL, '3.0', 1, 6, 0.5,
 NULL, NULL, NULL, JSON_OBJECT('onFalse', JSON_ARRAY('s1_use_trailing')),
 'ATR 변동폭을 계산해 설정 배수만큼 빠졌을 때 청산합니다. 작을수록 타이트합니다.', 'Y', NOW(), NOW()),

('S1', 's1_trail_drawdown_pct', 'C', '트레일링 스탑',
 '매수 시점부터 실시간 체결가로 고점을 추적하고, 그 고점에서 설정폭만큼 하락하면 청산합니다. <br/>비활성화하면 손절/익절 뿐입니다.', 3, 's1_use_trailing', 3,
 3, '고점 대비 하락', '%', 'pct', NULL, '0.04', 1, 30, 0.5,
 '미사용', 5, NULL, JSON_OBJECT('onFalse', JSON_ARRAY('s1_use_trailing')),
 '고점에서 이 비율만큼 빠지면 청산합니다. 비우면(미사용) ATR 라인만 씁니다.', 'Y', NOW(), NOW()),

('S1', 's1_trail_dual', 'C', '트레일링 스탑',
 '매수 시점부터 실시간 체결가로 고점을 추적하고, 그 고점에서 설정폭만큼 하락하면 청산합니다. <br/>비활성화하면 손절/익절 뿐입니다.', 3, 's1_use_trailing', 3,
 4, 'ATR 라인과 이중 감시', NULL, 'bool', NULL, '1', NULL, NULL, NULL,
 NULL, NULL, NULL,
 JSON_OBJECT('onFalse', JSON_ARRAY('s1_use_trailing'), 'onBlank', JSON_ARRAY('s1_trail_drawdown_pct')),
 'ON = ATR 라인과 하락폭 라인 중 먼저 닿는 쪽에서 매도. OFF = 하락폭 라인 단독.', 'Y', NOW(), NOW()),

-- 그룹 C 마스터 토글. 카드 헤더에 렌더링되므로 sort_order = 0.
('S1', 's1_use_trailing', 'C', '트레일링 스탑',
 '매수 시점부터 실시간 체결가로 고점을 추적하고, 그 고점에서 설정폭만큼 하락하면 청산합니다. <br/>비활성화하면 손절/익절 뿐입니다.', 3, 's1_use_trailing', 3,
 0, '트레일링 사용', NULL, 'bool', NULL, '1', NULL, NULL, NULL,
 NULL, NULL, NULL, NULL,
 '끄면 트레일링 청산을 하지 않고 손절/익절만 감시합니다.', 'Y', NOW(), NOW()),

-- ── D. 동적 타임스탑 ─────────────────────────────────────────────────
('S1', 's1_max_hold_bars', 'D', '동적 타임스탑',
 '보유 봉수 한도에 도달하면 평가를 시작합니다. 추세가 살아있으면 매도를 보류할 수 있습니다.', 4, NULL, 4,
 1, '보유 한도', '봉', 'int', NULL, '12', 3, 60, 1,
 NULL, NULL, NULL, NULL,
 '이 봉수에 도달하면 타임스탑 평가를 시작합니다.', 'Y', NOW(), NOW()),

('S1', 's1_time_stop_extend', 'D', '동적 타임스탑',
 '보유 봉수 한도에 도달하면 평가를 시작합니다. 추세가 살아있으면 매도를 보류할 수 있습니다.', 4, NULL, 4,
 2, '추세 생존 시 연장', NULL, 'bool', NULL, '1', NULL, NULL, NULL,
 NULL, NULL, NULL, NULL,
 '수익 > 밴드 & ema20 위 & grace봉 내 신고가면 매도를 보류하고 트레일/손절에 위임합니다.', 'Y', NOW(), NOW()),

('S1', 's1_time_stop_band', 'D', '동적 타임스탑',
 '보유 봉수 한도에 도달하면 평가를 시작합니다. 추세가 살아있으면 매도를 보류할 수 있습니다.', 4, NULL, 4,
 3, '정체 판정 수익밴드', '%', 'pct', NULL, '0.02', 0, 10, 0.5,
 NULL, NULL, NULL, JSON_OBJECT('onFalse', JSON_ARRAY('s1_time_stop_extend')),
 '이 수익 이하면 정체로 보고 타임스탑을 실행합니다.', 'Y', NOW(), NOW()),

('S1', 's1_time_stop_grace', 'D', '동적 타임스탑',
 '보유 봉수 한도에 도달하면 평가를 시작합니다. 추세가 살아있으면 매도를 보류할 수 있습니다.', 4, NULL, 4,
 4, '신고가 grace 봉수', '봉', 'int', 'stepper', '3', 0, 10, 1,
 NULL, NULL, NULL, JSON_OBJECT('onFalse', JSON_ARRAY('s1_time_stop_extend')),
 '최근 이 봉수 이내에 신고가를 갱신해야 연장을 허용합니다.', 'Y', NOW(), NOW()),

('S1', 's1_max_hold_bars_hard', 'D', '동적 타임스탑',
 '보유 봉수 한도에 도달하면 평가를 시작합니다. 추세가 살아있으면 매도를 보류할 수 있습니다.', 4, NULL, 4,
 5, '절대 보유 한도', '봉', 'int', NULL, '20', 3, 120, 1,
 NULL, NULL, NULL, NULL,
 '연장을 포함한 절대 상한. 보유 한도보다 크거나 같아야 합니다.', 'Y', NOW(), NOW());
