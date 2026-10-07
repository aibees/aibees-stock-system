<template>
    <div id="buy-param-setting">
        <BrandHeader :title="title" back="/trade" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-right">
                    <button class="btn-refresh" @click="reloadAll" :disabled="isLoading">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M23 4v6h-6" /><path d="M1 20v-6h6" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                        </svg>
                        초기화
                    </button>
                </div>
            </section>

            <!-- ── 모드 탭 ── -->
            <nav class="mode-tab-nav">
                <button v-for="m in MODE_TABS" :key="m.code" type="button"
                    :class="['mode-tab-btn', { active: activeMode === m.code }]"
                    @click="activeMode = m.code">
                    <span class="mt-code">{{ m.code }}</span>
                    <span class="mt-name">{{ m.name }}</span>
                </button>
            </nav>

            <!-- ══════════ M1 : 현행 설정 ══════════ -->
            <template v-if="activeMode === 'M1'">

            <!-- ── 로딩 스켈레톤 ── -->
            <div v-if="isLoading" class="loader-rows">
                <div v-for="n in 5" :key="n" class="skeleton-row"></div>
            </div>

            <form v-else class="setting-form" @submit.prevent="save">

                <!-- ════════════════════════════════════════════════
                     1. 매수 후보 우선순위 (개인화)
                ═════════════════════════════════════════════════ -->
                <section class="setting-card order-card">
                    <header class="card-head">
                        <div class="ch-left">
                            <h3>매수 후보 우선순위</h3>
                        </div>
                    </header>

                    <ul class="order-list">
                        <li v-for="(row, idx) in orderRows" :key="row.field"
                            :class="['order-row', { off: !row.on, dragging: dragIndex === idx }]"
                            draggable="true"
                            @dragstart="onDragStart(idx)"
                            @dragover.prevent="onDragOver(idx)"
                            @dragend="dragIndex = null"
                            @drop.prevent="dragIndex = null">

                            <span class="or-handle" title="드래그해서 순서 변경">⠿</span>

                            <span class="or-rank">{{ row.on ? activeRank(idx) : '–' }}</span>

                            <div class="or-main">
                                <span class="or-label">{{ ORDER_FIELD_META[row.field].label }}</span>
                            </div>

                            <div class="or-dir">
                                <button type="button" v-for="d in ['desc', 'asc']" :key="d"
                                    :class="['dir-chip', { on: row.dir === d }]"
                                    :disabled="!row.on"
                                    @click="row.dir = d">
                                    {{ d === 'desc' ? ORDER_FIELD_META[row.field].descLabel : ORDER_FIELD_META[row.field].ascLabel }}
                                </button>
                            </div>

                            <div class="or-move">
                                <button type="button" class="mv-btn" :disabled="idx === 0" @click="move(idx, -1)">↑</button>
                                <button type="button" class="mv-btn" :disabled="idx === orderRows.length - 1" @click="move(idx, 1)">↓</button>
                            </div>

                            <button type="button"
                                :class="['toggle-btn', row.on ? 'active' : 'inactive']"
                                role="switch" :aria-checked="row.on"
                                @click="toggleOrderRow(row)">
                                <span class="toggle-knob"></span>
                            </button>
                        </li>
                    </ul>

                    <p v-if="orderError" class="field-error block">{{ orderError }}</p>

                </section>

                <!-- ════════════════════════════════════════════════
                     2. 후보 선정 조건 (관리자 전용)
                ═════════════════════════════════════════════════ -->
                <section v-if="!canEditStrategy" class="admin-notice">
                    <span class="an-icon">🔒</span>
                    <div>
                        <b>아래 조건은 관리자만 변경할 수 있습니다.</b>
                        <p>
                            매수타겟은 전 사용자가 공유하는 하나의 추천 목록으로 생성됩니다.
                            개인이 바꿔도 본인 결과에만 반영되지 않고 전원에게 영향을 주기 때문에 잠겨 있습니다.
                            현재 적용 중인 값은 참고용으로 표시됩니다.
                        </p>
                    </div>
                </section>

                <section v-for="g in STRATEGY_GROUPS" :key="g.id" class="setting-card"
                    :class="{ locked: !canEditStrategy }">
                    <header class="card-head">
                        <div class="ch-left">
                            <h3>{{ g.title }}</h3>
                        </div>
                        <span v-if="!canEditStrategy" class="lock-badge">관리자 전용</span>
                    </header>

                    <div class="field-list">
                        <div v-for="f in g.fields" :key="f.k"
                            :class="['field-row', { disabled: isFieldDisabled(f.k) }]">

                            <div class="fr-head">
                                <label :for="f.k">
                                    {{ f.label }}
                                    <span v-if="f.unit" class="fr-unit">({{ f.unit }})</span>
                                </label>
                                <div class="fr-right">
                                    <span class="fr-def">
                                        기본 {{ defDisplay(f) }}<template v-if="f.unit === '%'">%</template>
                                    </span>
                                    <button v-if="f.type !== 'bool' && f.type !== 'enum'" type="button"
                                        class="btn-null" title="기본값 따름(null)"
                                        :disabled="isFieldDisabled(f.k)"
                                        @click="form[f.k] = ''">기본값</button>
                                </div>
                            </div>

                            <!-- bool -->
                            <div v-if="f.type === 'bool'" class="fr-ctrl bool-ctrl">
                                <button type="button"
                                    :class="['toggle-btn', isOn(f.k) ? 'active' : 'inactive']"
                                    role="switch" :aria-checked="isOn(f.k)"
                                    :disabled="isFieldDisabled(f.k)"
                                    @click="toggleBool(f.k)">
                                    <span class="toggle-knob"></span>
                                </button>
                                <span class="bool-text">{{ isOn(f.k) ? '사용' : '미사용' }}</span>
                            </div>

                            <!-- enum -->
                            <div v-else-if="f.type === 'enum'" class="fr-ctrl enum-ctrl">
                                <label v-for="o in f.options" :key="o.v"
                                    :class="['radio-chip', { on: form[f.k] === o.v }]">
                                    <input type="radio" :name="f.k" :value="o.v"
                                        v-model="form[f.k]" :disabled="isFieldDisabled(f.k)" />
                                    {{ o.label }}
                                </label>
                            </div>

                            <!-- stepper -->
                            <div v-else-if="f.ui === 'stepper'" class="fr-ctrl stepper-ctrl">
                                <button type="button" class="st-btn" :disabled="isFieldDisabled(f.k)"
                                    @click="bump(f, -1)">−</button>
                                <input :id="f.k" type="number" class="st-input"
                                    :value="form[f.k]" @input="onNumInput(f, $event)"
                                    :min="f.min" :max="f.max" :step="f.step"
                                    :placeholder="String(defDisplay(f))"
                                    :disabled="isFieldDisabled(f.k)" inputmode="numeric" />
                                <button type="button" class="st-btn" :disabled="isFieldDisabled(f.k)"
                                    @click="bump(f, 1)">+</button>
                                <span class="st-unit">{{ f.unit }}</span>
                            </div>

                            <!-- slider + number -->
                            <div v-else class="fr-ctrl slider-ctrl">
                                <input type="range" class="sl-range"
                                    :value="sliderVal(f)" @input="onNumInput(f, $event)"
                                    :min="f.min" :max="f.max" :step="f.step"
                                    :disabled="isFieldDisabled(f.k)" />
                                <div class="sl-num">
                                    <input :id="f.k" type="number"
                                        :value="form[f.k]" @input="onNumInput(f, $event)"
                                        :min="f.min" :max="f.max" :step="f.step"
                                        :placeholder="String(defDisplay(f))"
                                        :disabled="isFieldDisabled(f.k)" inputmode="decimal" />
                                    <span class="sl-unit">{{ f.unit }}</span>
                                </div>
                            </div>

                            <span v-if="errors[f.k]" class="field-error">{{ errors[f.k] }}</span>
                        </div>
                    </div>
                </section>

                <!-- ════════ 저장 바 ════════ -->
                <div class="save-bar">
                    <span class="dirty-note" v-if="isDirty">변경된 항목 {{ dirtyCount }}건</span>
                    <span class="dirty-note clean" v-else>변경 사항 없음</span>
                    <button type="button" class="btn-reset" @click="resetForm"
                        :disabled="!isDirty || isSaving">되돌리기</button>
                    <button type="submit" class="btn-save" :disabled="!isDirty || isSaving || hasError">
                        {{ isSaving ? '저장 중…' : '저장' }}
                    </button>
                </div>
            </form>
            </template>

            <!-- ══════════ M2 : 준비중 ══════════ -->
            <section v-else class="mode-empty">
                <span class="me-code">{{ activeMode }}</span>
                <h3>{{ currentModeName }}</h3>
                <p>이 모드의 매수조건 설정은 아직 준비중입니다.</p>
            </section>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';
import mariaToast from '@scripts/mariaToast.js';
import { assUserSession } from '@/scripts/stores/user-stores';

const title = ref('매수 설정');
const userSession = assUserSession();

/* ═══════════════════════════════════════════════════════════
 * 운용 모드 탭 (M1 만 현행 설정, M2 는 준비중)
 * ═══════════════════════════════════════════════════════════ */
const MODE_TABS = [
    { code: 'M1', name: '추천매수' },
    { code: 'M2', name: 'ETF 교대' },
];
const activeMode = ref('M1');
const currentModeName = computed(
    () => MODE_TABS.find(m => m.code === activeMode.value)?.name ?? ''
);

/* ═══════════════════════════════════════════════════════════
 * 권한
 *  - 서버(router_strategy)가 ADMIN_USER_ID 로 최종 판정하고 403 을 낸다.
 *    화면은 그 판정(_meta.is_admin)을 신뢰하되, 세션 role 도 함께 본다.
 *    둘 다 true 여야 편집 UI 를 연다(요구사항: user_id + isAdmin).
 *  - 화면 잠금은 UX 일 뿐 보안 경계가 아니다. 실제 차단은 서버가 한다.
 * ═══════════════════════════════════════════════════════════ */
const isAdminRole = computed(() => {
    const roles = userSession.getRole ?? [];
    return roles.some(r => String(r).toUpperCase() === 'ADMIN' || r === '시스템 관리자');
});
const serverIsAdmin = ref(false);
const canEditStrategy = computed(() => serverIsAdmin.value && isAdminRole.value);

/* ═══════════════════════════════════════════════════════════
 * 1. 매수 후보 정렬 (s1_buy_order)
 *
 * 저장 형식: "필드:방향,필드:방향" — 앞 키가 동점일 때만 다음 키로 넘어간다.
 * 허용 필드는 백엔드 _BUY_ORDER_FIELDS / worker _ORDER_FIELDS 와 일치해야 한다.
 * 항목 추가 시 여기 + 백엔드 두 곳만 고치면 된다.
 * ═══════════════════════════════════════════════════════════ */
const ORDER_FIELD_META = {
    score:             { label: '추천 점수',   descLabel: '높은 순', ascLabel: '낮은 순' },
    volume:            { label: '거래량',      descLabel: '많은 순', ascLabel: '적은 순' },
    rate:              { label: '등락률',      descLabel: '높은 순', ascLabel: '낮은 순' },
    rank_no:           { label: '추천 순번',   descLabel: '큰 순',   ascLabel: '작은 순' },
    close:             { label: '종가',        descLabel: '높은 순', ascLabel: '낮은 순' },
    shape_proba:       { label: '급등패턴 확률', descLabel: '높은 순', ascLabel: '낮은 순' },
    composite_rank_no: { label: '종합 순위',   descLabel: '큰 순',   ascLabel: '작은 순' },
};
const ORDER_FIELDS = Object.keys(ORDER_FIELD_META);
// worker 기본 정렬(stock_shared.strategy.buy_order.DEFAULT_BUY_ORDER)과 동일하게 맞춘다
// (둘이 다르면 "미리보기"가 실제 매수 순서와 어긋난다). 2026-09 세션 후속 리서치로
// top10→모멘텀 재정렬(composite_rank_no) 방식이 재현성 있게 우수함을 확인해 1순위로 승격.
const DEFAULT_ORDER_SPEC = 'composite_rank_no:asc,score:desc,rank_no:asc';

/* orderRows: 화면 순서 = 우선순위. on=false 면 정렬에 쓰지 않음 */
const orderRows = ref([]);
let originalOrderSpec = '';

const blankOrderRows = () =>
    ORDER_FIELDS.map(f => ({ field: f, dir: f === 'rank_no' ? 'asc' : 'desc', on: false }));

/** "score:desc,volume" → orderRows (미지정 필드는 뒤에 off 로 붙임) */
const specToRows = (spec) => {
    const rows = [];
    const seen = new Set();
    for (const token of String(spec || '').split(',')) {
        const t = token.trim();
        if (!t) continue;
        const [rawField, rawDir] = t.split(':');
        const field = (rawField || '').trim();
        if (!ORDER_FIELD_META[field] || seen.has(field)) continue;
        seen.add(field);
        rows.push({
            field,
            dir: (rawDir || '').trim() === 'asc' ? 'asc' : (rawDir || '').trim() === 'desc' ? 'desc'
                : (field === 'rank_no' ? 'asc' : 'desc'),
            on: true,
        });
    }
    // 선택되지 않은 필드는 off 상태로 뒤에 붙여 언제든 켤 수 있게 둔다
    ORDER_FIELDS.filter(f => !seen.has(f))
        .forEach(f => rows.push({ field: f, dir: f === 'rank_no' ? 'asc' : 'desc', on: false }));
    return rows;
};

const orderSpec = computed(() =>
    orderRows.value.filter(r => r.on).map(r => `${r.field}:${r.dir}`).join(','));

const activeRank = (idx) =>
    orderRows.value.slice(0, idx + 1).filter(r => r.on).length;

const orderError = computed(() =>
    orderRows.value.some(r => r.on) ? '' : '정렬 기준을 최소 1개 이상 선택해야 합니다.');

const toggleOrderRow = (row) => { row.on = !row.on; };

const move = (idx, dir) => {
    const next = idx + dir;
    if (next < 0 || next >= orderRows.value.length) return;
    const arr = orderRows.value;
    [arr[idx], arr[next]] = [arr[next], arr[idx]];
};

/* 드래그 재정렬 — 모바일 대비로 ↑↓ 버튼도 함께 제공한다 */
const dragIndex = ref(null);
const onDragStart = (idx) => { dragIndex.value = idx; };
const onDragOver = (idx) => {
    if (dragIndex.value === null || dragIndex.value === idx) return;
    const arr = orderRows.value;
    const [moved] = arr.splice(dragIndex.value, 1);
    arr.splice(idx, 0, moved);
    dragIndex.value = idx;
};

const resetOrderToDefault = () => { orderRows.value = specToRows(DEFAULT_ORDER_SPEC); };

/* ═══════════════════════════════════════════════════════════
 * 2. 후보 선정 조건 (관리자 전용) — KospiStrategy0.get_action_in_watch
 * ═══════════════════════════════════════════════════════════ */
const SIGNAL_MODE_OPTIONS = [
    { v: 'golden', label: '골든크로스' },
    { v: 'slope', label: '기울기 상승' },
    { v: 'off', label: '사용 안 함' },
];

/* MA20은 자기 자신과의 골든크로스 개념이 없어 off/slope 2가지만 존재 */
const MA20_SIGNAL_MODE_OPTIONS = [
    { v: 'slope', label: '기울기 상승 요구' },
    { v: 'off', label: '사용 안 함' },
];

const STRATEGY_GROUPS = [
    {
        id: 'S', title: '진입 신호 (core)',
        fields: [
            {
                k: 's1_macd_signal_mode', label: 'MACD 신호', type: 'enum', def: 'slope',
                options: SIGNAL_MODE_OPTIONS,
            },
            {
                k: 's1_obv_signal_mode', label: 'OBV 신호', type: 'enum', def: 'golden',
                options: SIGNAL_MODE_OPTIONS,
            },
            {
                k: 's1_ma20_signal_mode', label: 'MA20 기울기', type: 'enum', def: 'off',
                options: MA20_SIGNAL_MODE_OPTIONS,
            },
        ],
    },
    {
        id: 'F', title: '매수 필터 on/off',
        fields: [
            {
                k: 's1_enable_macd_filter', label: 'MACD 조건', type: 'bool', def: 1,
            },
            {
                k: 's1_enable_rsi_filter', label: '과매수 진입 차단', type: 'bool', def: 1,
            },
            {
                k: 's1_enable_bb_upper_filter', label: '볼린저 상단 추격 금지', type: 'bool', def: 1,
            },
            {
                k: 's1_enable_vol_avg_filter', label: '평균 거래량 하한', type: 'bool', def: 1,
            },
            {
                k: 's1_enable_regime_gate', label: '추세국면 게이트', type: 'bool', def: 1,
            },
        ],
    },
    {
        id: 'T', title: '임계값',
        fields: [
            {
                k: 's1_rsi_overbought', label: '과매수 기준 RSI', unit: '', type: 'int', def: 70,
                min: 50, max: 90, step: 1,
            },
            {
                k: 's1_rsi_ideal_low', label: 'RSI 신뢰구간 하한', unit: '', type: 'int', def: 40,
                min: 0, max: 100, step: 1, ui: 'stepper',
            },
            {
                k: 's1_rsi_ideal_high', label: 'RSI 신뢰구간 상한', unit: '', type: 'int', def: 65,
                min: 0, max: 100, step: 1, ui: 'stepper',
            },
            {
                k: 's1_vol_ma_window', label: '평균 거래량 산정 기간', unit: '일', type: 'int', def: 20,
                min: 5, max: 60, step: 1,
            },
            {
                k: 's1_vol_ma_mult', label: '평균 거래량 하한 배수', unit: '배', type: 'float', def: 0.5,
                min: 0.1, max: 3, step: 0.1,
            },
        ],
    },
    {
        id: 'R', title: '추세국면 게이트',
        fields: [
            {
                k: 's1_regime_window', label: '국면 분류 기간', unit: '봉', type: 'int', def: 90,
                min: 20, max: 250, step: 5,
            },
            {
                k: 's1_regime_threshold', label: '하락국면 판정 비율', unit: '%', type: 'pct', def: 0.70,
                min: 10, max: 100, step: 5,
            },
            {
                k: 's1_strict_need_macd_up', label: '[하락국면] MACD 모멘텀 요구', type: 'bool', def: 1,
            },
            {
                k: 's1_downtrend_surge_bypass', label: '[하락국면] 거래량 급증 우회', type: 'bool', def: 1,
            },
            {
                k: 's1_surge_bypass_mult', label: '[하락국면] 우회 급증 배수', unit: '배', type: 'float', def: 2.0,
                min: 1, max: 5, step: 0.1,
            },
            {
                k: 's1_loose_need_vol_surge', label: '[상승국면] 거래량 급증 요구', type: 'bool', def: 1,
            },
            {
                k: 's1_surge_relax_mult', label: '[상승국면] 완화 급증 배수', unit: '배', type: 'float', def: 2.0,
                min: 1, max: 5, step: 0.1,
            },
        ],
    },
];

const ALL_FIELDS = STRATEGY_GROUPS.flatMap(g => g.fields);
const FIELD_MAP = Object.fromEntries(ALL_FIELDS.map(f => [f.k, f]));

/* 조건부 비활성화 — 상위 스위치가 꺼지면 하위 임계값은 의미가 없다 */
const DISABLE_RULES = {
    s1_rsi_overbought: 's1_enable_rsi_filter',
    s1_vol_ma_window: 's1_enable_vol_avg_filter',
    s1_vol_ma_mult: 's1_enable_vol_avg_filter',
    s1_regime_window: 's1_enable_regime_gate',
    s1_regime_threshold: 's1_enable_regime_gate',
    s1_strict_need_macd_up: 's1_enable_regime_gate',
    s1_downtrend_surge_bypass: 's1_enable_regime_gate',
    s1_loose_need_vol_surge: 's1_enable_regime_gate',
    s1_surge_bypass_mult: () => !isOn('s1_enable_regime_gate') || !isOn('s1_downtrend_surge_bypass'),
    s1_surge_relax_mult: () => !isOn('s1_enable_regime_gate') || !isOn('s1_loose_need_vol_surge'),
};

/* ═══════════════ 폼 상태 ═══════════════ */
const form = reactive({});
let original = {};
const isLoading = ref(true);
const isSaving = ref(false);

const blankForm = () => {
    const o = {};
    ALL_FIELDS.forEach(f => {
        o[f.k] = (f.type === 'bool' || f.type === 'enum') ? f.def : '';
    });
    return o;
};

const defDisplay = (f) => {
    if (f.type === 'enum') return f.options.find(o => o.v === f.def)?.label ?? f.def;
    return f.type === 'pct' ? +(f.def * 100).toFixed(4) : f.def;
};
const defNum = (f) => (f.type === 'pct' ? +(f.def * 100).toFixed(4) : f.def);

const toDisplay = (f, raw) => {
    if (raw === null || raw === undefined || raw === '') {
        return (f.type === 'bool' || f.type === 'enum') ? f.def : '';
    }
    if (f.type === 'pct') return +(Number(raw) * 100).toFixed(4);
    if (f.type === 'bool') return Number(raw) ? 1 : 0;
    if (f.type === 'enum') return String(raw);
    return Number(raw);
};
const toApi = (f, disp) => {
    if (f.type === 'enum') return disp === '' || disp === null ? null : String(disp);
    if (f.type === 'bool') return Number(disp) ? 1 : 0;
    if (disp === '' || disp === null || disp === undefined) return null;
    if (f.type === 'pct') return +(Number(disp) / 100).toFixed(6);
    if (f.type === 'int') return parseInt(disp, 10);
    return Number(disp);
};

/* ═══════════════ 조회 ═══════════════ */
const fetchOptions = async () => {
    isLoading.value = true;
    Object.assign(form, blankForm());
    try {
        const { data } = await aibeesApi.get('/api/v1/strategy/options');
        const d = data.data ?? {};
        serverIsAdmin.value = !!d._meta?.is_admin;
        ALL_FIELDS.forEach(f => {
            if (d[f.k] !== undefined) form[f.k] = toDisplay(f, d[f.k]);
        });
        orderRows.value = specToRows(d.s1_buy_order || DEFAULT_ORDER_SPEC);
    } catch (e) {
        console.error('[BuySetting] 조회 실패', e);
        orderRows.value = specToRows(DEFAULT_ORDER_SPEC);
    } finally {
        original = JSON.parse(JSON.stringify(form));
        originalOrderSpec = orderSpec.value;
        isLoading.value = false;
    }
};
const reloadAll = () => {
    fetchOptions();
};

onMounted(reloadAll);

/* ═══════════════ 컨트롤 헬퍼 ═══════════════ */
const isOn = (k) => Number(form[k]) === 1;
const toggleBool = (k) => {
    if (isFieldDisabled(k)) return;
    form[k] = isOn(k) ? 0 : 1;
};
const isBlank = (k) => form[k] === '' || form[k] === null || form[k] === undefined;

/** 관리자가 아니면 전략 필드는 전부 잠근다(표시는 하되 편집 불가) */
const isFieldDisabled = (k) => {
    if (!canEditStrategy.value) return true;
    const dep = DISABLE_RULES[k];
    if (!dep) return false;
    return typeof dep === 'function' ? dep() : !isOn(dep);
};

const clamp = (f, v) => Math.min(f.max, Math.max(f.min, v));

const onNumInput = (f, ev) => {
    const raw = ev.target.value;
    if (raw === '') { form[f.k] = ''; return; }
    const n = Number(raw);
    if (Number.isNaN(n)) return;
    form[f.k] = f.type === 'int' ? Math.round(n) : n;
};

const bump = (f, dir) => {
    if (isFieldDisabled(f.k)) return;
    const cur = isBlank(f.k) ? defNum(f) : Number(form[f.k]);
    form[f.k] = clamp(f, +(cur + dir * f.step).toFixed(4));
};

const sliderVal = (f) => (isBlank(f.k) ? defNum(f) : Number(form[f.k]));

/* ═══════════════ 검증 ═══════════════ */
const errors = computed(() => {
    const e = {};
    ALL_FIELDS.forEach(f => {
        if (f.type === 'bool' || f.type === 'enum') return;
        const v = form[f.k];
        if (v === '' || v === null) return;
        if (Number(v) < f.min || Number(v) > f.max) {
            e[f.k] = `허용 범위: ${f.min} ~ ${f.max}${f.unit === '%' ? '%' : ''}`;
        }
    });

    const lo = isBlank('s1_rsi_ideal_low') ? FIELD_MAP.s1_rsi_ideal_low.def : Number(form.s1_rsi_ideal_low);
    const hi = isBlank('s1_rsi_ideal_high') ? FIELD_MAP.s1_rsi_ideal_high.def : Number(form.s1_rsi_ideal_high);
    if (hi < lo) e.s1_rsi_ideal_high = `상한(${hi})은 하한(${lo}) 이상이어야 합니다.`;

    return e;
});
const hasError = computed(() => Object.keys(errors.value).length > 0 || !!orderError.value);

/* ═══════════════ diff / 저장 ═══════════════ */
const buildDiff = () => {
    const diff = {};
    // 전략 파라미터는 관리자만 전송한다(비관리자는 서버가 403 을 낼 값이라 아예 담지 않음)
    if (canEditStrategy.value) {
        ALL_FIELDS.forEach(f => {
            if (String(form[f.k]) !== String(original[f.k])) diff[f.k] = toApi(f, form[f.k]);
        });
    }
    if (orderSpec.value !== originalOrderSpec) diff.s1_buy_order = orderSpec.value || null;
    return diff;
};
const isDirty = computed(() => Object.keys(buildDiff()).length > 0);
const dirtyCount = computed(() => Object.keys(buildDiff()).length);

const resetForm = () => {
    Object.assign(form, JSON.parse(JSON.stringify(original)));
    orderRows.value = specToRows(originalOrderSpec);
};

const save = async () => {
    if (hasError.value) {
        mariaToast.error(orderError.value || '입력값을 확인해 주세요.');
        return;
    }
    const payload = buildDiff();
    if (Object.keys(payload).length === 0) {
        mariaToast.info('변경된 항목이 없습니다.');
        return;
    }
    isSaving.value = true;
    try {
        await aibeesApi.patch('/api/v1/strategy/options', payload);
        original = JSON.parse(JSON.stringify(form));
        originalOrderSpec = orderSpec.value;
        mariaToast.success(
            's1_buy_order' in payload
                ? '저장되었습니다. 정렬은 다음 매수 라운드부터 적용됩니다.'
                : '저장되었습니다. 다음 매수타겟 생성부터 반영됩니다.');
    } catch (e) {
        console.error('[BuySetting] 저장 실패', e);
    } finally {
        isSaving.value = false;
    }
};
</script>

<style scoped>
#buy-param-setting {
    min-height: 100vh;
    background: #FFFBEA;
}

.contents {
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 14px 96px;
    box-sizing: border-box;
}

/* ── 모드 탭 ── */
.mode-tab-nav {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid #EFE2BC;
    margin: 0 0 16px;
    overflow-x: auto;
}

.mode-tab-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 8px 14px;
    border: none;
    background: none;
    color: #9A8C7E;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color .12s, border-color .12s;
}

.mode-tab-btn .mt-code {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: .04em;
}

.mode-tab-btn .mt-name {
    font-size: 0.82rem;
    font-weight: 600;
}

.mode-tab-btn:hover { color: #4A3628; }

.mode-tab-btn.active {
    color: #2B1D14;
    border-bottom-color: #2B1D14;
}

/* ── 준비중 영역 ── */
.mode-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 320px;
    background: #fff;
    border: 1px dashed #EFE2BC;
    border-radius: 10px;
    color: #9A8C7E;
}

.mode-empty .me-code {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: .06em;
    padding: 3px 9px;
    border-radius: 10px;
    background: #F3EAD2;
    color: #6B5B4E;
}

.mode-empty h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: #4A3628;
}

.mode-empty p {
    margin: 0;
    font-size: 0.85rem;
}

/* ── 상단 ── */
.head-desc {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 4px 16px;
}

.head-desc h2 {
    margin: 0;
    text-align: start;
    font-size: 1.25rem;
    font-weight: 700;
    color: #2B1D14;
}

.head-desc .sub-text {
    margin: 6px 0 0;
    font-size: 0.85rem;
    color: #6B5B4E;
    line-height: 1.45;
}

.btn-refresh {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    background: #fff;
    color: #4A3628;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.btn-refresh:hover:not(:disabled) {
    border-color: #2B1D14;
    color: #2B1D14;
}

/* ── 스켈레톤 ── */
.loader-rows { display: flex; flex-direction: column; gap: 10px; }

.skeleton-row {
    height: 74px;
    border-radius: 10px;
    background: linear-gradient(90deg, #F3EAD2 25%, #FFFBEA 37%, #F3EAD2 63%);
    background-size: 400% 100%;
    animation: sk 1.2s ease infinite;
}

@keyframes sk {
    0%   { background-position: 100% 50%; }
    100% { background-position: 0 50%; }
}

/* ── 카드 ── */
.setting-card {
    background: #fff;
    border: 1px solid #F3EAD2;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 14px;
}

.setting-card.locked { background: #FFFBEA; }

.card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.ch-left { display: flex; align-items: center; gap: 9px; }

.ch-left h3 {
    margin: 0;
    font-size: 0.98rem;
    font-weight: 700;
    color: #2B1D14;
}

.lock-badge {
    font-size: 0.7rem;
    font-weight: 700;
    color: #2B1D14;
    background: #FFFBEA;
    border: 1px solid #E3D3A8;
    border-radius: 10px;
    padding: 3px 10px;
    white-space: nowrap;
}

/* ── 관리자 안내 ── */
.admin-notice {
    display: flex;
    gap: 12px;
    background: #FFFBEA;
    border: 1px solid #E3D3A8;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 14px;
}

.admin-notice .an-icon { font-size: 1.1rem; line-height: 1.3; }
.admin-notice b { font-size: 0.85rem; color: #2B1D14; }

.admin-notice p {
    margin: 6px 0 0;
    font-size: 0.78rem;
    color: #2B1D14;
    line-height: 1.55;
}

/* ══════ 정렬 리스트 ══════ */
.order-list {
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.order-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border: 1px solid #F3EAD2;
    border-radius: 10px;
    background: #fff;
    transition: opacity .15s, border-color .15s, background .15s;
}

.order-row.off { opacity: .5; background: #FFFBEA; }
.order-row.dragging { border-color: #74462A; background: #FFFBEA; }

.or-handle {
    cursor: grab;
    color: #9A8C7E;
    font-size: 0.95rem;
    user-select: none;
    flex: none;
}

.or-rank {
    flex: none;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background: #74462A;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
}

.order-row.off .or-rank { background: #E3D3A8; }

.or-main { flex: 1; min-width: 0; }

.or-label {
    display: block;
    font-size: 1rem;
    font-weight: 600;
    color: #2B1D14;
    text-align: left;
}

.or-dir { display: flex; gap: 4px; flex: none; }

.dir-chip {
    padding: 4px 9px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    background: #fff;
    color: #6B5B4E;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.dir-chip.on {
    border-color: #2B1D14;
    background: #F3EAD2;
    color: #2B1D14;
}

.dir-chip:disabled { cursor: not-allowed; opacity: .6; }

.or-move { display: flex; flex-direction: column; gap: 2px; flex: none; }

.mv-btn {
    width: 20px;
    height: 16px;
    line-height: 1;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    background: #fff;
    color: #4A3628;
    font-size: 0.62rem;
    cursor: pointer;
    padding: 0;
}

.mv-btn:disabled { opacity: .35; cursor: not-allowed; }

.order-spec {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
    padding: 10px 12px;
    background: #FFFBEA;
    border-radius: 10px;
    flex-wrap: wrap;
}

/* ══════ 일반 필드 ══════ */
.field-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 8px;
}

.field-row {
    padding: 12px 0;
    border-top: 1px solid #F3EAD2;
}

.field-row:first-child { border-top: none; }
.field-row.disabled { opacity: .45; }

.fr-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 8px;
}

.fr-head label {
    font-size: 0.83rem;
    font-weight: 600;
    color: #2B1D14;
}

.fr-unit { color: #9A8C7E; font-weight: 500; }

.fr-right { display: flex; align-items: center; gap: 8px; }

.fr-def {
    font-size: 0.71rem;
    color: #9A8C7E;
    white-space: nowrap;
}

.btn-null {
    padding: 3px 8px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    background: #fff;
    color: #6B5B4E;
    font-size: 0.68rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.btn-null:hover:not(:disabled) { border-color: #2B1D14; color: #2B1D14; }
.btn-null:disabled { opacity: .4; cursor: not-allowed; }

.fr-ctrl { display: flex; align-items: center; gap: 10px; }

/* toggle */
.toggle-btn {
    position: relative;
    width: 42px;
    height: 24px;
    border: none;
    border-radius: 10px;
    background: #E3D3A8;
    cursor: pointer;
    padding: 0;
    flex: none;
    transition: background .18s;
}

.toggle-btn.active { background: #74462A; }
.toggle-btn:disabled { opacity: .45; cursor: not-allowed; }

.toggle-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 18px;
    height: 18px;
    border-radius: 10px;
    background: #fff;
    transition: transform .18s;
}

.toggle-btn.active .toggle-knob { transform: translateX(18px); }

.bool-text { font-size: 0.78rem; color: #4A3628; }

/* enum */
.enum-ctrl { flex-wrap: wrap; gap: 6px; }

.radio-chip {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    font-size: 0.76rem;
    font-weight: 600;
    color: #6B5B4E;
    cursor: pointer;
    background: #fff;
}

.radio-chip.on { border-color: #74462A; background: #F3EAD2; color: #74462A; }
.radio-chip input { display: none; }

/* stepper */
.stepper-ctrl { gap: 6px; }

.st-btn {
    width: 30px;
    height: 30px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    background: #fff;
    color: #4A3628;
    font-size: 0.95rem;
    cursor: pointer;
    padding: 0;
}

.st-btn:disabled { opacity: .4; cursor: not-allowed; }

.st-input {
    width: 64px;
    height: 30px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    text-align: center;
    font-size: 0.8rem;
    color: #2B1D14;
}

.st-unit { font-size: 0.74rem; color: #6B5B4E; }

/* slider */
.slider-ctrl { gap: 12px; }

.sl-range { flex: 1; accent-color: #2B1D14; min-width: 0; }

.sl-num { display: flex; align-items: center; gap: 4px; flex: none; }

.sl-num input {
    width: 68px;
    height: 30px;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    text-align: right;
    padding: 0 8px;
    font-size: 1rem;
    color: #2B1D14;
    box-sizing: border-box;
}

.sl-unit { font-size: 0.74rem; color: #6B5B4E; }

.field-error {
    display: block;
    margin-top: 5px;
    font-size: 1rem;
    color: #2B1D14;
    font-weight: 600;
}

.field-error.block { margin-top: 10px; }

/* ── 저장 바 ── */
.save-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 0;
    background: linear-gradient(180deg, rgba(244, 246, 249, 0) 0%, #FFFBEA 34%);
}

.dirty-note {
    flex: 1;
    font-size: 0.75rem;
    font-weight: 600;
    color: #2B1D14;
}

.dirty-note.clean { color: #9A8C7E; font-weight: 500; }

.btn-reset,
.btn-save {
    height: 40px;
    padding: 0 20px;
    border-radius: 10px;
    font-size: 0.83rem;
    font-weight: 700;
    cursor: pointer;
    border: 1px solid #EFE2BC;
    background: #fff;
    color: #4A3628;
}

.btn-save { border: none; background: #74462A; color: #fff; }
.btn-save:disabled { background: #E3D3A8; cursor: not-allowed; }
.btn-reset:disabled { opacity: .45; cursor: not-allowed; }

@media (max-width: 560px) {    .order-row { gap: 7px; padding: 9px 10px; }
    .or-dir { flex-direction: column; }
}

/* 안쪽 제목을 걷어내고 버튼만 남았으므로 오른쪽 끝에 둔다(헤더에 이미 제목이 있다) */
.head-desc .head-right { margin-left: auto; }
</style>
