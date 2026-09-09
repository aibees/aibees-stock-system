<template>
    <div id="auto-trade-mode">
        <Headers :prop_title="'자동매매'" />

        <div class="contents">

            <!-- ── 현재 운용 상태 배너 ── -->
            <section class="state-banner" :class="stateClass">
                <div class="state-left">
                    <span class="state-badge">{{ runStateLabel }}</span>
                    <div class="state-text">
                        <p class="state-mode">{{ activeModeName }}</p>
                        <p class="state-sub">{{ activeSummary }}</p>
                    </div>
                </div>
                <div class="state-right">
                    <span class="power-label">{{ state.enabled_flag === 'Y' ? '운용중' : '정지' }}</span>
                    <button :class="['toggle-btn', state.enabled_flag === 'Y' ? 'active' : 'inactive']"
                        @click="togglePower" :disabled="isBusy">
                        <span class="toggle-knob"></span>
                    </button>
                </div>
            </section>

            <!-- ── 전환 예약 배너 ── -->
            <section v-if="state.pending_mode" class="pending-banner">
                <div>
                    <strong>전환 예약됨</strong>
                    <p>보유 종목 매도 체결 시 <b>{{ modeName(state.pending_mode) }}</b> 로 자동 전환됩니다.</p>
                    <p class="pending-detail">{{ configSummary(state.pending_mode, state.pending_config) }}</p>
                </div>
                <button class="btn-cancel" @click="onCancelPending" :disabled="isBusy">예약 취소</button>
            </section>

            <!-- ── 잠금 안내 ── -->
            <p v-if="isLocked" class="lock-note">
                보유 중에는 방식·종목을 즉시 변경할 수 없습니다. 저장하면 <b>전환 예약</b>으로 등록되고, 현재 보유 종목이 매도되면 적용됩니다.
            </p>

            <!-- ── 모드 카드 ── -->
            <section class="mode-cards">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 4" :key="n" class="skeleton-row"></div>
                </div>

                <article v-for="m in modes" v-else :key="m.mode_code"
                    :class="['mode-card', { selected: form.mode_code === m.mode_code, current: state.active_mode === m.mode_code }]"
                    @click="selectMode(m)">
                    <div class="card-head">
                        <span class="radio" :class="{ on: form.mode_code === m.mode_code }"></span>
                        <h3>{{ m.mode_name }}</h3>
                        <span v-if="state.active_mode === m.mode_code" class="chip-current">현재</span>
                    </div>
                    <p class="card-desc" v-html="m.mode_desc"></p>
                </article>
            </section>

            <!-- ── 모드별 상세 설정 ── -->
            <section v-if="selectedMode" class="mode-config">
                <h4>{{ selectedMode.mode_name }} 설정</h4>

                <!-- M0 -->
                <p v-if="form.mode_code === 'M0'" class="config-none">
                    별도 설정이 없습니다. 매일 20시 추천 배치 결과의 1순위 종목을 익일 전량 매수합니다.
                </p>

                <!-- M1 : 단일 종목 고정 -->
                <div v-else-if="form.mode_code === 'M1'" class="form-grid">
                    <div class="form-field full">
                        <label>고정 종목 <span class="req">*</span></label>
                        <div class="stock-picker">
                            <input readonly :value="display(form.config.stock_code, form.config.stock_name)"
                                placeholder="종목을 선택하세요" />
                            <button class="btn-pick" @click="openPicker('stock')">종목 선택</button>
                        </div>
                    </div>
                    <div class="form-field">
                        <label>진입 규칙</label>
                        <select v-model="form.config.entry_rule">
                            <option value="SIGNAL">매수 신호 충족 시</option>
                            <option value="IMMEDIATE">장 시작 즉시 매수</option>
                        </select>
                    </div>
                    <div class="form-field">
                        <label>투입 비중 (예수금 대비)</label>
                        <div class="stepper">
                            <button @click="step('invest_ratio', -0.1, 0.1, 1)">−</button>
                            <span>{{ Math.round((form.config.invest_ratio ?? 1) * 100) }}%</span>
                            <button @click="step('invest_ratio', 0.1, 0.1, 1)">＋</button>
                        </div>
                    </div>
                </div>

                <!-- M2 : ETF 교대 -->
                <div v-else-if="form.mode_code === 'M2'" class="form-grid">
                    <div class="form-field">
                        <label>정방향 ETF <span class="req">*</span></label>
                        <div class="stock-picker">
                            <input readonly :value="display(form.config.long_code, form.config.long_name)"
                                placeholder="예: KODEX 200" />
                            <button class="btn-pick" @click="openPicker('long')">선택</button>
                        </div>
                    </div>
                    <div class="form-field">
                        <label>인버스 ETF <span class="req">*</span></label>
                        <div class="stock-picker">
                            <input readonly :value="display(form.config.short_code, form.config.short_name)"
                                placeholder="예: KODEX 인버스" />
                            <button class="btn-pick" @click="openPicker('short')">선택</button>
                        </div>
                    </div>
                    <div class="form-field">
                        <label>단기 이동평균</label>
                        <div class="stepper">
                            <button @click="step('ma_short', -1, 3, 20)">−</button>
                            <span>{{ form.config.ma_short }}일</span>
                            <button @click="step('ma_short', 1, 3, 20)">＋</button>
                        </div>
                    </div>
                    <div class="form-field">
                        <label>장기 이동평균</label>
                        <div class="stepper">
                            <button @click="step('ma_long', -5, 10, 120)">−</button>
                            <span>{{ form.config.ma_long }}일</span>
                            <button @click="step('ma_long', 5, 10, 120)">＋</button>
                        </div>
                    </div>
                    <div class="form-field">
                        <label>LONG 진입 점수</label>
                        <div class="stepper">
                            <button @click="step('threshold_long', -1, 1, 3)">−</button>
                            <span>{{ form.config.threshold_long }} / 3</span>
                            <button @click="step('threshold_long', 1, 1, 3)">＋</button>
                        </div>
                    </div>
                    <div class="form-field">
                        <label>SHORT 진입 점수</label>
                        <div class="stepper">
                            <button @click="step('threshold_short', -1, 1, 3)">−</button>
                            <span>{{ form.config.threshold_short }} / 3</span>
                            <button @click="step('threshold_short', 1, 1, 3)">＋</button>
                        </div>
                    </div>
                    <p class="hint full">
                        종가&gt;MA{{ form.config.ma_long }}, MA{{ form.config.ma_short }}&gt;MA{{ form.config.ma_long }},
                        MACD 히스토그램&gt;0 세 가지를 ±1점으로 합산해 방향을 정합니다. 점수 미달이면 현금 대기합니다.
                    </p>
                </div>

            </section>

            <!-- ── 매도 수기 등록 (모드 무관) ──
                 위에서 어떤 방식을 고르든, 보유 종목 하나에 지정가를 걸어두면
                 그 종목만은 이 방식의 자동 매도 판정 대신 지정가로 감시된다.
                 구 'M4/지정가 감시' 모드는 폐기되고 이 기능만 모드 무관으로 남았다. -->
            <section class="config-link">
                <p>보유 종목에 <b>지정 매도가</b>를 걸어두면, 선택한 방식과 무관하게 그 종목만 지정가로 매도됩니다.</p>
                <button class="btn-link" @click="goManualSell">매도 수기 등록 화면으로 이동</button>
            </section>

            <!-- ── 저장 ── -->
            <div class="action-bar">
                <button class="btn-save" @click="onSave" :disabled="isBusy || !form.mode_code">
                    {{ isLocked ? '전환 예약 저장' : '저장하고 적용' }}
                </button>
            </div>
        </div>

        <StockPickerModal :visible="picker.visible" :title="picker.title" @pick="onPick"
            @close="picker.visible = false" />
    </div>
</template>

<script setup>
import StockPickerModal from './StockPickerModal.vue';
import {
    fetchModes, fetchState, saveState, cancelPending, setPower,
    RUN_STATE_LABEL,
} from '@scripts/useAutoTrade.js';

const router = useRouter();

const isLoading = ref(true);
const isBusy = ref(false);
const modes = ref([]);
const state = reactive({
    enabled_flag: 'N',
    run_state: 'IDLE',
    active_mode: null,
    active_config: {},
    pending_mode: null,
    pending_config: null,
    position: null,
});

const DEFAULT_CONFIG = {
    M0: () => ({}),
    M1: () => ({ stock_code: '', stock_name: '', entry_rule: 'SIGNAL', invest_ratio: 1 }),
    M2: () => ({
        long_code: '', long_name: '', short_code: '', short_name: '',
        ma_short: 5, ma_long: 20, threshold_long: 2, threshold_short: 2, flip_cooldown_bars: 0,
    }),
    // 구 M3(지정가 감시)는 폐기 — 매도 수기 등록으로 대체(모드 무관, 위 config-link 참고).
};

const form = reactive({ mode_code: '', config: {} });

/* ── 조회 ── */
const load = async () => {
    isLoading.value = true;
    try {
        const [modeList, st] = await Promise.all([fetchModes(), fetchState()]);
        modes.value = modeList;
        if (st) Object.assign(state, st);

        // 편집 기준: 예약이 있으면 예약값, 없으면 현재값
        const baseMode = state.pending_mode ?? state.active_mode ?? 'M0';
        const baseConfig = state.pending_mode ? state.pending_config : state.active_config;
        form.mode_code = baseMode;
        form.config = { ...DEFAULT_CONFIG[baseMode]?.() ?? {}, ...(baseConfig ?? {}) };
    } finally {
        isLoading.value = false;
    }
};
onMounted(load);

/* ── 파생 ── */
const isLocked = computed(() => ['HOLDING', 'SWITCH_PENDING'].includes(state.run_state));
const runStateLabel = computed(() => RUN_STATE_LABEL[state.run_state] ?? state.run_state);
const stateClass = computed(() => `st-${(state.run_state ?? 'IDLE').toLowerCase()}`);
const selectedMode = computed(() => modes.value.find(m => m.mode_code === form.mode_code) ?? null);
const modeName = (code) => modes.value.find(m => m.mode_code === code)?.mode_name ?? code ?? '-';
const activeModeName = computed(() => state.active_mode ? modeName(state.active_mode) : '운용 방식 미설정');

const display = (code, name) => code ? `${name || ''} (${code})` : '';

const configSummary = (code, cfg) => {
    const c = cfg ?? {};
    if (code === 'M1') return `고정 종목 ${display(c.stock_code, c.stock_name) || '-'}`;
    if (code === 'M2') return `${c.long_name || c.long_code || '-'} ↔ ${c.short_name || c.short_code || '-'}`;
    return '추천 1순위 자동매매';
};

const activeSummary = computed(() => {
    if (state.position) {
        return `보유: ${state.position.stock_name} (${state.position.stock_code}) · ${state.position.profit_pct ?? '-'}`;
    }
    return configSummary(state.active_mode, state.active_config);
});

/* ── 입력 ── */
const selectMode = (m) => {
    if (form.mode_code === m.mode_code) return;
    form.mode_code = m.mode_code;
    form.config = DEFAULT_CONFIG[m.mode_code]?.() ?? {};
};

const step = (key, delta, min, max) => {
    const next = Number(((form.config[key] ?? min) + delta).toFixed(2));
    form.config[key] = Math.min(max, Math.max(min, next));
};

const picker = reactive({ visible: false, target: '', title: '' });
const openPicker = (target) => {
    picker.target = target;
    picker.title = target === 'long' ? '정방향 ETF 선택'
        : target === 'short' ? '인버스 ETF 선택' : '종목 선택';
    picker.visible = true;
};
const onPick = ({ stock_code, stock_name }) => {
    if (picker.target === 'stock') {
        form.config.stock_code = stock_code;
        form.config.stock_name = stock_name;
    } else {
        form.config[`${picker.target}_code`] = stock_code;
        form.config[`${picker.target}_name`] = stock_name;
    }
    picker.visible = false;
};

/* ── 검증 ── */
const validate = () => {
    const c = form.config;
    if (form.mode_code === 'M1' && !c.stock_code) return '고정 종목을 선택해 주세요.';
    if (form.mode_code === 'M2') {
        if (!c.long_code || !c.short_code) return '정방향/인버스 ETF를 모두 선택해 주세요.';
        if (c.long_code === c.short_code) return '정방향과 인버스 ETF는 서로 달라야 합니다.';
        if (Number(c.ma_short) >= Number(c.ma_long)) return '단기 이동평균은 장기보다 작아야 합니다.';
    }
    return null;
};

/* ── 저장 ── */
const onSave = async () => {
    const err = validate();
    if (err) { alert(err); return; }

    const confirmMsg = isLocked.value
        ? '보유 중이므로 전환 예약으로 저장됩니다. 계속할까요?'
        : `운용 방식을 '${modeName(form.mode_code)}' 로 즉시 적용합니다. 계속할까요?`;
    if (!confirm(confirmMsg)) return;

    isBusy.value = true;
    try {
        const res = await saveState(form.mode_code, form.config);
        alert(res.message ?? (res.applied === 'RESERVED' ? '전환 예약되었습니다.' : '적용되었습니다.'));
        await load();
    } finally {
        isBusy.value = false;
    }
};

const onCancelPending = async () => {
    if (!confirm('전환 예약을 취소할까요? 현재 운용 방식이 그대로 유지됩니다.')) return;
    isBusy.value = true;
    try {
        await cancelPending();
        await load();
    } finally {
        isBusy.value = false;
    }
};

const togglePower = async () => {
    const next = state.enabled_flag === 'Y' ? 'N' : 'Y';
    if (next === 'N' && state.run_state === 'HOLDING'
        && !confirm('보유 중입니다. 운용을 정지하면 신규 매수는 중단되지만 보유 종목 매도 감시는 계속됩니다. 계속할까요?')) return;

    isBusy.value = true;
    try {
        await setPower(next);
        await load();
    } finally {
        isBusy.value = false;
    }
};

const goManualSell = () => router.push({ path: '/auto-trade/limit-order' });
</script>

<style scoped lang="scss">
/* ── 무채색 팔레트 (/trade 대시보드와 동일) ── */
$white:    #ffffff;
$gray-50:  #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$black:    #000000;

#auto-trade-mode {
    min-height: 100vh;
    background: $white;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 1000px;
    margin: 0 auto;
    padding: 24px 16px 120px;
}

/* ── 상태 배너 ── */
.state-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    background: $white;
    border: 1px solid $gray-200;
    border-left: 4px solid $gray-300;
    padding: 16px 18px;
    margin-bottom: 14px;

    &.st-holding {
        border-left-color: $gray-900;
    }

    &.st-armed {
        border-left-color: $gray-500;
    }

    &.st-switch_pending {
        border-left-color: $gray-400;
    }

    .state-left {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .state-badge {
        font-size: .72rem;
        font-weight: 700;
        padding: 4px 10px;
        border: 1px solid $gray-300;
        color: $gray-900;
        white-space: nowrap;
        letter-spacing: .02em;
    }

    .state-mode {
        margin: 0;
        font-size: 1.02rem;
        font-weight: 700;
    }

    .state-sub {
        margin: 3px 0 0;
        font-size: .8rem;
        color: $gray-500;
    }

    .state-right {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .power-label {
        font-size: .8rem;
        color: $gray-500;
    }

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: flex-start;
    }
}

.toggle-btn {
    width: 44px;
    height: 24px;
    border: 1px solid $gray-300;
    position: relative;
    cursor: pointer;
    background: $white;
    transition: background .18s, border-color .18s;

    &.active {
        background: $gray-900;
        border-color: $gray-900;
    }

    &.inactive {
        background: $white;
    }

    .toggle-knob {
        position: absolute;
        top: 2px;
        left: 2px;
        width: 18px;
        height: 18px;
        background: $gray-300;
        transition: transform .18s, background .18s;
    }

    &.active .toggle-knob {
        transform: translateX(18px);
        background: $white;
    }
}

/* ── 예약 배너 ── */
.pending-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    background: $gray-50;
    border: 1px solid $gray-300;
    padding: 14px 18px;
    margin-bottom: 14px;

    strong {
        font-size: .86rem;
        color: $gray-900;
    }

    p {
        margin: 4px 0 0;
        font-size: .82rem;
        color: $gray-900;
    }

    .pending-detail {
        color: $gray-500;
        font-size: .78rem;
    }

    .btn-cancel {
        border: 1px solid $gray-300;
        background: $white;
        color: $gray-700;
        padding: 8px 14px;
        font-size: .8rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;

        &:hover { background: $gray-900; color: $white; border-color: $gray-900; }
    }
}

.lock-note {
    font-size: .8rem;
    color: $gray-500;
    background: $white;
    border: 1px dashed $gray-300;
    padding: 10px 14px;
    margin: 0 0 16px;
}

/* ── 모드 카드 ── */
.mode-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1px;
    background: $gray-200;
    border: 1px solid $gray-200;
    margin-bottom: 18px;

    @media (max-width: 700px) {
        grid-template-columns: 1fr;
    }
}

.mode-card {
    background: $white;
    padding: 16px 18px;
    cursor: pointer;
    transition: background .12s;

    &:hover {
        background: $gray-50;
    }

    &.selected {
        box-shadow: inset 0 0 0 1px $gray-900;
    }

    .card-head {
        display: flex;
        align-items: center;
        gap: 9px;

        h3 {
            margin: 0;
            font-size: .95rem;
            font-weight: 700;
            flex: 1;
        }
    }

    .radio {
        width: 14px;
        height: 14px;
        border: 1.5px solid $gray-300;
        flex: 0 0 auto;

        &.on {
            border-color: $gray-900;
            background: $gray-900;
            box-shadow: inset 0 0 0 2px $white;
        }
    }

    .chip-current {
        font-size: .66rem;
        font-weight: 700;
        color: $white;
        background: $gray-900;
        padding: 3px 8px;
    }

    .card-desc {
        margin: 10px 0 0;
        font-size: .8rem;
        line-height: 1.55;
        color: $gray-500;
    }
}

/* ── 상세 설정 ── */
.mode-config {
    background: $white;
    border: 1px solid $gray-200;
    padding: 18px;

    h4 {
        margin: 0 0 14px;
        font-size: .82rem;
        font-weight: 700;
        color: $gray-500;
        letter-spacing: .03em;
        text-transform: uppercase;
    }

    .config-none {
        margin: 0;
        font-size: .82rem;
        color: $gray-500;
    }
}

/* ── 매도 수기 등록 안내 (모드 무관, mode-config 밖의 독립 섹션) ── */
.config-link {
    background: $white;
    border: 1px solid $gray-200;
    padding: 16px 18px;
    margin-top: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;

    p {
        margin: 0;
        font-size: .82rem;
        color: $gray-500;
        line-height: 1.5;

        b { color: $gray-900; }
    }

    .btn-link {
        border: 1px solid $gray-300;
        color: $gray-700;
        background: $white;
        padding: 8px 14px;
        font-size: .82rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        flex: 0 0 auto;

        &:hover { background: $gray-900; color: $white; border-color: $gray-900; }
    }
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;

    @media (max-width: 700px) {
        grid-template-columns: 1fr;
    }

    .full {
        grid-column: 1 / -1;
    }
}

.form-field {
    display: flex;
    flex-direction: column;
    gap: 6px;

    label {
        font-size: .78rem;
        font-weight: 600;
        color: $gray-500;
    }

    .req {
        color: $gray-900;
        font-weight: 700;
    }

    input,
    select {
        height: 38px;
        border: 1px solid $gray-300;
        padding: 0 10px;
        font-size: .85rem;
        background: $white;
        color: $gray-900;
    }
}

.stock-picker {
    display: flex;
    gap: 8px;

    input {
        flex: 1;
        background: $gray-50;
    }

    .btn-pick {
        height: 38px;
        padding: 0 14px;
        border: 1px solid $gray-300;
        color: $gray-700;
        background: $white;
        font-size: .8rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;

        &:hover { background: $gray-900; color: $white; border-color: $gray-900; }

        &:disabled {
            opacity: .45;
            cursor: not-allowed;
        }
    }
}

.stepper {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 38px;
    border: 1px solid $gray-300;
    padding: 0 6px;

    button {
        width: 28px;
        height: 26px;
        border: 1px solid $gray-300;
        background: $white;
        font-size: .95rem;
        cursor: pointer;

        &:hover { background: $gray-900; color: $white; border-color: $gray-900; }
    }

    span {
        font-size: .85rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }
}

.hint {
    font-size: .76rem;
    color: $gray-400;
    line-height: 1.5;
    margin: 0;
}

/* ── 저장 ── */
.action-bar {
    display: flex;
    justify-content: flex-end;
    margin-top: 18px;
}

.btn-save {
    height: 42px;
    padding: 0 26px;
    border: 1px solid $gray-900;
    background: $gray-900;
    color: $white;
    font-size: .88rem;
    font-weight: 700;
    cursor: pointer;

    &:hover:not(:disabled) { background: $black; border-color: $black; }

    &:disabled {
        opacity: .4;
        cursor: not-allowed;
    }
}

/* ── 스켈레톤 ── */
.loader-rows {
    grid-column: 1 / -1;
}

.skeleton-row {
    height: 84px;
    background: $gray-100;
    animation: pulse 1.6s infinite ease-in-out;
    margin-bottom: 10px;
}

@keyframes pulse {
    0%, 100% { opacity: .55; }
    50%      { opacity: .9; }
}
</style>
