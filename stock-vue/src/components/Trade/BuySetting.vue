<template>
    <div id="buy-param-setting">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>매수조건 개인화 설정</h2>
                    <p class="sub-text">
                        자동매수 후보를 <b>어떤 순서로 살지</b>, 후보를 <b>어떤 조건으로 뽑을지</b>를 설정합니다.
                    </p>
                </div>
                <div class="head-right">
                    <button class="btn-refresh" @click="fetchOptions" :disabled="isLoading">
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

            <!-- ── 범위 안내 ── -->
            <section class="scope-bar">
                <div class="scope-row">
                    <span class="scope-badge personal">개인</span>
                    <div class="scope-text">
                        <b>매수 후보 우선순위</b> — 개인서버에만 적용합니다. 다른 사용자와 무관하게 자유롭게 바꿀 수 있습니다.
                    </div>
                </div>
                <div class="scope-row">
                    <span class="scope-badge admin">공용</span>
                    <div class="scope-text">
                        <b>후보 선정 조건</b> — 매수타겟 배치가 <b>전 사용자 공용 추천 테이블</b>을 만들 때 쓰는 값입니다.
                    </div>
                </div>
            </section>

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
                            <span class="prio-badge personal">개인</span>
                            <h3>매수 후보 우선순위</h3>
                        </div>
                    </header>
                    <span class="card-desc">
                        같은 날 추천된 후보들 중 <b>무엇을 먼저 살지</b> 정합니다.
                        위에 있는 기준이 우선이고, 값이 <b>동점일 때만</b> 아래 기준으로 넘어갑니다.
                    </span>

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
                                <span class="or-hint">{{ ORDER_FIELD_META[row.field].hint }}</span>
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

                    <!-- 정렬 미리보기 -->
                    <div class="order-preview">
                        <div class="op-head">
                            <span class="op-title">정렬 예시</span>
                            <span class="op-note">예시 후보 5종목에 현재 설정을 적용한 결과입니다. <b>맨 위 종목부터 매수됩니다.</b></span>
                        </div>
                        <table class="op-table">
                            <thead>
                                <tr>
                                    <th class="tc">순위</th>
                                    <th>종목</th>
                                    <th class="tr">score</th>
                                    <th class="tr">거래량</th>
                                    <th class="tr">등락률</th>
                                    <th class="tc">rank</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(r, i) in sortedSample" :key="r.stock_code"
                                    :class="{ top: i === 0 }">
                                    <td class="tc rank-cell">{{ i + 1 }}</td>
                                    <td>{{ r.stock_name }}</td>
                                    <td class="tr num">{{ r.score ?? '–' }}</td>
                                    <td class="tr num">{{ r.volume === null ? '–' : r.volume.toLocaleString() }}</td>
                                    <td class="tr num" :class="pctClass(r.rate)">{{ r.rate ?? '–' }}</td>
                                    <td class="tc num">{{ r.rank_no ?? '–' }}</td>
                                </tr>
                            </tbody>
                        </table>
                        <p class="op-legend">값이 없는(–) 종목은 정렬 방향과 무관하게 항상 뒤로 밀립니다.</p>
                    </div>
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
                            <span class="prio-badge admin">공용</span>
                            <h3>{{ g.title }}</h3>
                        </div>
                        <span v-if="!canEditStrategy" class="lock-badge">관리자 전용</span>
                    </header>
                    <span class="card-desc" v-html="g.desc"></span>

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

                            <span v-if="f.hint" class="field-hint">{{ f.hint }}</span>
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
    score: {
        label: '추천 점수 (score)', descLabel: '높은 순', ascLabel: '낮은 순',
        hint: '배치가 매긴 종합 점수. 기본 1순위 기준입니다.',
    },
    volume: {
        label: '거래량', descLabel: '많은 순', ascLabel: '적은 순',
        hint: '전일 거래량. 유동성이 큰 종목을 먼저 잡고 싶을 때 씁니다.',
    },
    rate: {
        label: '등락률 (rate)', descLabel: '높은 순', ascLabel: '낮은 순',
        hint: '전일 대비 등락률. 음수도 정상 처리됩니다.',
    },
    rank_no: {
        label: '추천 순번 (rank)', descLabel: '큰 순', ascLabel: '작은 순',
        hint: '배치가 부여한 순번. 작을수록 상위 추천입니다.',
    },
    close: {
        label: '종가', descLabel: '높은 순', ascLabel: '낮은 순',
        hint: '전일 종가. 저가주/고가주 선호를 반영할 때 씁니다.',
    },
};
const ORDER_FIELDS = Object.keys(ORDER_FIELD_META);
const DEFAULT_ORDER_SPEC = 'score:desc,rank_no:asc';

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

/* ── 정렬 미리보기 ──
 * worker(repository.make_buy_order_key)와 동일한 규칙을 화면에서 재현한다:
 *   · NULL 은 방향과 무관하게 항상 뒤
 *   · desc 는 부호를 뒤집어 오름차순 비교
 *   · 전 키 동점이면 stock_code 로 최종 결정
 */
const SAMPLE_ROWS = [
    { stock_code: '005070', stock_name: '코스모신소재', score: 90, volume: 512000, rate: '12.5%', rank_no: 1 },
    { stock_code: '066430', stock_name: '와이오엠', score: 90, volume: 9120000, rate: '-3.2%', rank_no: 2 },
    { stock_code: '015760', stock_name: '한국전력', score: 80, volume: 1030000, rate: '5.0%', rank_no: 3 },
    { stock_code: '109070', stock_name: '컨버즈', score: null, volume: 24500000, rate: '29.9%', rank_no: null },
    { stock_code: '048910', stock_name: '대원미디어', score: 80, volume: null, rate: null, rank_no: 4 },
];

const numOf = (v) => {
    if (v === null || v === undefined) return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
};
const pctOf = (v) => {
    if (v === null || v === undefined) return null;
    const n = Number(String(v).replace('%', '').replace(/,/g, '').trim());
    return Number.isNaN(n) ? null : n;
};
const FIELD_VALUE = {
    score: r => numOf(r.score),
    volume: r => numOf(r.volume),
    rate: r => pctOf(r.rate),
    rank_no: r => numOf(r.rank_no),
    close: r => numOf(r.close),
};

const sortedSample = computed(() => {
    const steps = orderRows.value.filter(r => r.on);
    const active = steps.length ? steps : specToRows(DEFAULT_ORDER_SPEC).filter(r => r.on);
    return [...SAMPLE_ROWS].sort((a, b) => {
        for (const s of active) {
            const va = FIELD_VALUE[s.field](a);
            const vb = FIELD_VALUE[s.field](b);
            // null 은 항상 뒤 (방향 무관)
            if (va === null && vb === null) continue;
            if (va === null) return 1;
            if (vb === null) return -1;
            if (va !== vb) return s.dir === 'desc' ? vb - va : va - vb;
        }
        return String(a.stock_code).localeCompare(String(b.stock_code));
    });
});

const pctClass = (rate) => {
    const n = pctOf(rate);
    if (n === null) return '';
    return n > 0 ? 'up-c' : n < 0 ? 'down-c' : '';
};

/* ═══════════════════════════════════════════════════════════
 * 2. 후보 선정 조건 (관리자 전용) — KospiStrategy1.get_action_in_watch
 * ═══════════════════════════════════════════════════════════ */
const SIGNAL_MODE_OPTIONS = [
    { v: 'golden', label: '골든크로스' },
    { v: 'slope', label: '기울기 상승' },
    { v: 'off', label: '사용 안 함' },
];

const STRATEGY_GROUPS = [
    {
        id: 'S', title: '진입 신호 (core)',
        desc: 'MACD·OBV 두 신호를 <b>모두 만족</b>해야 후보가 됩니다. 둘 다 "사용 안 함"이면 아래 필터만으로 판정합니다.',
        fields: [
            {
                k: 's1_macd_signal_mode', label: 'MACD 신호', type: 'enum', def: 'slope',
                options: SIGNAL_MODE_OPTIONS,
                hint: '골든크로스=신호선 상향 돌파 시점만. 기울기 상승=전봉 대비 MACD가 오르는 중이면 통과(더 느슨).',
            },
            {
                k: 's1_obv_signal_mode', label: 'OBV 신호', type: 'enum', def: 'golden',
                options: SIGNAL_MODE_OPTIONS,
                hint: '거래량 누적 지표. 골든크로스가 기본이며 세력 유입 확인용입니다.',
            },
        ],
    },
    {
        id: 'F', title: '매수 필터 on/off',
        desc: '진입 신호를 통과한 종목에 순서대로 적용되는 게이트입니다. 끄면 해당 조건을 건너뜁니다.',
        fields: [
            {
                k: 's1_enable_macd_filter', label: 'MACD 조건', type: 'bool', def: 1,
                hint: '0선 위 · 음권이지만 빠르게 상승 · 크로스 임박(갭 축소) 중 하나를 요구합니다.',
            },
            {
                k: 's1_enable_rsi_filter', label: '과매수 진입 차단', type: 'bool', def: 1,
                hint: 'RSI가 과매수 기준 이상이면 진입하지 않습니다.',
            },
            {
                k: 's1_enable_bb_upper_filter', label: '볼린저 상단 추격 금지', type: 'bool', def: 1,
                hint: '종가가 BB 상단을 넘은 종목은 제외합니다.',
            },
            {
                k: 's1_enable_vol_avg_filter', label: '평균 거래량 하한', type: 'bool', def: 1,
                hint: '거래가 죽은 종목을 거릅니다. 하한선은 아래 임계값에서 조정합니다.',
            },
            {
                k: 's1_enable_regime_gate', label: '추세국면 게이트', type: 'bool', def: 1,
                hint: '하락국면이면 엄격, 상승국면이면 느슨하게 판정합니다. 끄면 국면 구분 없이 통과합니다.',
            },
        ],
    },
    {
        id: 'T', title: '임계값',
        desc: '위 필터들이 실제로 사용하는 숫자 기준입니다.',
        fields: [
            {
                k: 's1_rsi_overbought', label: '과매수 기준 RSI', unit: '', type: 'int', def: 70,
                min: 50, max: 90, step: 1,
                hint: 'RSI가 이 값 이상이면 진입을 차단합니다. 낮출수록 보수적입니다.',
            },
            {
                k: 's1_rsi_ideal_low', label: 'RSI 신뢰구간 하한', unit: '', type: 'int', def: 40,
                min: 0, max: 100, step: 1, ui: 'stepper',
                hint: '지표 표시용 구간입니다. 진입을 직접 막지는 않습니다.',
            },
            {
                k: 's1_rsi_ideal_high', label: 'RSI 신뢰구간 상한', unit: '', type: 'int', def: 65,
                min: 0, max: 100, step: 1, ui: 'stepper',
                hint: '하한보다 크거나 같아야 합니다.',
            },
            {
                k: 's1_vol_ma_window', label: '평균 거래량 산정 기간', unit: '일', type: 'int', def: 20,
                min: 5, max: 60, step: 1,
                hint: '이 기간의 평균 거래량을 기준값으로 씁니다.',
            },
            {
                k: 's1_vol_ma_mult', label: '평균 거래량 하한 배수', unit: '배', type: 'float', def: 0.5,
                min: 0.1, max: 3, step: 0.1,
                hint: '평균 × 이 배수 이상이어야 통과. 1.0=평균 이상, 0.5=죽은 거래량만 제거.',
            },
        ],
    },
    {
        id: 'R', title: '추세국면 게이트',
        desc: '최근 N봉 중 종가가 60일선 아래였던 <b>비율</b>로 국면을 먼저 분류한 뒤, 국면별로 다른 강도의 조건을 적용합니다.',
        fields: [
            {
                k: 's1_regime_window', label: '국면 분류 기간', unit: '봉', type: 'int', def: 90,
                min: 20, max: 250, step: 5,
                hint: '이 기간의 봉을 보고 하락/상승 국면을 판정합니다.',
            },
            {
                k: 's1_regime_threshold', label: '하락국면 판정 비율', unit: '%', type: 'pct', def: 0.70,
                min: 10, max: 100, step: 5,
                hint: '기간 중 이 비율 이상 60일선 아래였으면 하락국면 → 엄격 조건 적용.',
            },
            {
                k: 's1_strict_need_macd_up', label: '[하락국면] MACD 모멘텀 요구', type: 'bool', def: 1,
                hint: '하락국면에서 macd ≥ signal 을 추가로 요구합니다.',
            },
            {
                k: 's1_downtrend_surge_bypass', label: '[하락국면] 거래량 급증 우회', type: 'bool', def: 1,
                hint: '급반등 초입을 놓치지 않도록, 급증 + 20일선 위면 배열 요건을 면제합니다.',
            },
            {
                k: 's1_surge_bypass_mult', label: '[하락국면] 우회 급증 배수', unit: '배', type: 'float', def: 2.0,
                min: 1, max: 5, step: 0.1,
                hint: '전봉 거래량 대비 이 배수 이상이어야 우회를 허용합니다.',
            },
            {
                k: 's1_loose_need_vol_surge', label: '[상승국면] 거래량 급증 요구', type: 'bool', def: 1,
                hint: '상승국면에서도 급증을 동반한 진입만 허용합니다. 끄면 20일선 위이기만 하면 통과.',
            },
            {
                k: 's1_surge_relax_mult', label: '[상승국면] 완화 급증 배수', unit: '배', type: 'float', def: 2.0,
                min: 1, max: 5, step: 0.1,
                hint: '3배 기준을 못 넘는 2배대 돌파도 잡기 위한 보조 기준입니다.',
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
onMounted(fetchOptions);

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
    background: #f4f6f9;
}

.contents {
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 14px 96px;
    box-sizing: border-box;
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
    color: #1f2329;
}

.head-desc .sub-text {
    margin: 6px 0 0;
    font-size: 0.85rem;
    color: #6b7280;
    line-height: 1.45;
}

.btn-refresh {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    border: 1px solid #d6dbe1;
    border-radius: 999px;
    background: #fff;
    color: #4b5563;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.btn-refresh:hover:not(:disabled) {
    border-color: #2db400;
    color: #2db400;
}

/* ── 범위 안내 ── */
.scope-bar {
    background: #fff;
    border: 1px solid #e5e9ef;
    border-radius: 14px;
    padding: 12px 14px;
    margin-bottom: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.scope-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
}

.scope-text {
    font-size: 0.8rem;
    color: #4b5563;
    line-height: 1.5;
}

.scope-badge {
    flex: none;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 700;
    margin-top: 1px;
}

.scope-badge.personal { background: #e7f0fd; color: #1971c2; }
.scope-badge.admin    { background: #fff0b3; color: #a06800; }

/* ── 스켈레톤 ── */
.loader-rows { display: flex; flex-direction: column; gap: 10px; }

.skeleton-row {
    height: 74px;
    border-radius: 14px;
    background: linear-gradient(90deg, #eceff3 25%, #f5f7fa 37%, #eceff3 63%);
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
    border: 1px solid #e5e9ef;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 14px;
}

.setting-card.locked { background: #fafbfc; }

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
    color: #1f2329;
}

.prio-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 34px;
    height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 700;
}

.prio-badge.personal { background: #e7f0fd; color: #1971c2; }
.prio-badge.admin    { background: #fff0b3; color: #a06800; }

.lock-badge {
    font-size: 0.7rem;
    font-weight: 700;
    color: #a06800;
    background: #fff8e1;
    border: 1px solid #ffe08a;
    border-radius: 999px;
    padding: 3px 10px;
    white-space: nowrap;
}

.card-desc {
    display: block;
    margin: 8px 0 4px;
    font-size: 0.79rem;
    color: #6b7280;
    line-height: 1.55;
}

/* ── 관리자 안내 ── */
.admin-notice {
    display: flex;
    gap: 12px;
    background: #fff8e1;
    border: 1px solid #ffe08a;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 14px;
}

.admin-notice .an-icon { font-size: 1.1rem; line-height: 1.3; }
.admin-notice b { font-size: 0.85rem; color: #7a4f00; }

.admin-notice p {
    margin: 6px 0 0;
    font-size: 0.78rem;
    color: #8a6100;
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
    border: 1px solid #e5e9ef;
    border-radius: 12px;
    background: #fff;
    transition: opacity .15s, border-color .15s, background .15s;
}

.order-row.off { opacity: .5; background: #fafbfc; }
.order-row.dragging { border-color: #1971c2; background: #f1f7ff; }

.or-handle {
    cursor: grab;
    color: #adb5bd;
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
    border-radius: 50%;
    background: #1971c2;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
}

.order-row.off .or-rank { background: #ced4da; }

.or-main { flex: 1; min-width: 0; }

.or-label {
    display: block;
    font-size: 1rem;
    font-weight: 600;
    color: #1f2329;
    text-align: left;
}

.or-hint {
    display: block;
    margin-top: 2px;
    font-size: 1rem;
    color: #868e96;
    line-height: 1.4;
    text-align: left;
}

.or-dir { display: flex; gap: 4px; flex: none; }

.dir-chip {
    padding: 4px 9px;
    border: 1px solid #dee2e6;
    border-radius: 999px;
    background: #fff;
    color: #868e96;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.dir-chip.on {
    border-color: #1971c2;
    background: #e7f0fd;
    color: #1971c2;
}

.dir-chip:disabled { cursor: not-allowed; opacity: .6; }

.or-move { display: flex; flex-direction: column; gap: 2px; flex: none; }

.mv-btn {
    width: 20px;
    height: 16px;
    line-height: 1;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    background: #fff;
    color: #495057;
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
    background: #f8f9fb;
    border-radius: 10px;
    flex-wrap: wrap;
}

/* ── 정렬 미리보기 ── */
.order-preview {
    margin-top: 14px;
    border: 1px solid #e5e9ef;
    border-radius: 12px;
    overflow: hidden;
    font-size: 1.2rem;
}

.op-head { padding: 10px 12px; background: #f8f9fb; text-align: left; }

.op-title {
    display: block;
    font-size: 1rem;
    font-weight: 700;
    color: #1f2329;
}

.op-note {
    display: block;
    margin-top: 3px;
    font-size: 0.8rem;
    color: #868e96;
    line-height: 1.45;
}

.op-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }

.op-table th {
    padding: 7px 8px;
    background: #fff;
    border-bottom: 1px solid #e5e9ef;
    color: #868e96;
    font-weight: 600;
    font-size: 0.9rem;
    text-align: center;
    white-space: nowrap;
}

.op-table td {
    padding: 8px;
    font-size: 0.9rem;
    border-bottom: 1px solid #f1f3f5;
    color: #343a40;
    white-space: nowrap;
}

.op-table tr.top td { background: #f1f7ff; font-weight: 600; }

.op-table tr.top .rank-cell { color: #1971c2; font-weight: 700; }

.op-table .tr { text-align: right; }
.op-table .tc { text-align: center; }
.op-table .num { font-variant-numeric: tabular-nums; }
.op-table .up-c { color: #e03131; }
.op-table .down-c { color: #1971c2; }

.op-legend {
    margin: 0;
    padding: 8px 12px;
    font-size: 0.7rem;
    color: #868e96;
    background: #fff;
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
    border-top: 1px solid #f1f3f5;
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
    color: #1f2329;
}

.fr-unit { color: #adb5bd; font-weight: 500; }

.fr-right { display: flex; align-items: center; gap: 8px; }

.fr-def {
    font-size: 0.71rem;
    color: #adb5bd;
    white-space: nowrap;
}

.btn-null {
    padding: 3px 8px;
    border: 1px solid #dee2e6;
    border-radius: 999px;
    background: #fff;
    color: #868e96;
    font-size: 0.68rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.btn-null:hover:not(:disabled) { border-color: #1971c2; color: #1971c2; }
.btn-null:disabled { opacity: .4; cursor: not-allowed; }

.fr-ctrl { display: flex; align-items: center; gap: 10px; }

/* toggle */
.toggle-btn {
    position: relative;
    width: 42px;
    height: 24px;
    border: none;
    border-radius: 999px;
    background: #ced4da;
    cursor: pointer;
    padding: 0;
    flex: none;
    transition: background .18s;
}

.toggle-btn.active { background: #1971c2; }
.toggle-btn:disabled { opacity: .45; cursor: not-allowed; }

.toggle-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
    transition: transform .18s;
}

.toggle-btn.active .toggle-knob { transform: translateX(18px); }

.bool-text { font-size: 0.78rem; color: #495057; }

/* enum */
.enum-ctrl { flex-wrap: wrap; gap: 6px; }

.radio-chip {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border: 1px solid #dee2e6;
    border-radius: 999px;
    font-size: 0.76rem;
    font-weight: 600;
    color: #868e96;
    cursor: pointer;
    background: #fff;
}

.radio-chip.on { border-color: #1971c2; background: #e7f0fd; color: #1971c2; }
.radio-chip input { display: none; }

/* stepper */
.stepper-ctrl { gap: 6px; }

.st-btn {
    width: 30px;
    height: 30px;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    background: #fff;
    color: #495057;
    font-size: 0.95rem;
    cursor: pointer;
    padding: 0;
}

.st-btn:disabled { opacity: .4; cursor: not-allowed; }

.st-input {
    width: 64px;
    height: 30px;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    text-align: center;
    font-size: 0.8rem;
    color: #1f2329;
}

.st-unit { font-size: 0.74rem; color: #868e96; }

/* slider */
.slider-ctrl { gap: 12px; }

.sl-range { flex: 1; accent-color: #1971c2; min-width: 0; }

.sl-num { display: flex; align-items: center; gap: 4px; flex: none; }

.sl-num input {
    width: 68px;
    height: 30px;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    text-align: right;
    padding: 0 8px;
    font-size: 1rem;
    color: #1f2329;
    box-sizing: border-box;
}

.sl-unit { font-size: 0.74rem; color: #868e96; }

.field-hint {
    display: block;
    margin-top: 7px;
    font-size: 1rem;
    color: #868e96;
    line-height: 1.5;
}

.field-error {
    display: block;
    margin-top: 5px;
    font-size: 1rem;
    color: #e03131;
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
    background: linear-gradient(180deg, rgba(244, 246, 249, 0) 0%, #f4f6f9 34%);
}

.dirty-note {
    flex: 1;
    font-size: 0.75rem;
    font-weight: 600;
    color: #1971c2;
}

.dirty-note.clean { color: #adb5bd; font-weight: 500; }

.btn-reset,
.btn-save {
    height: 40px;
    padding: 0 20px;
    border-radius: 10px;
    font-size: 0.83rem;
    font-weight: 700;
    cursor: pointer;
    border: 1px solid #dee2e6;
    background: #fff;
    color: #495057;
}

.btn-save { border: none; background: #1971c2; color: #fff; }
.btn-save:disabled { background: #ced4da; cursor: not-allowed; }
.btn-reset:disabled { opacity: .45; cursor: not-allowed; }

@media (max-width: 560px) {
    .or-hint { display: none; }
    .order-row { gap: 7px; padding: 9px 10px; }
    .or-dir { flex-direction: column; }
}
</style>
