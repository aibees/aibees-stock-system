<template>
    <div id="stock-strategy">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- 상단 바: 전략설정 버튼 -->
            <div class="top-bar">
                <button class="strategy-btn" @click="openStrategyPopup">
                    <span class="gear">⚙</span> 전략설정
                </button>
            </div>

            <!-- 테스트 입력 카드 -->
            <section class="setup-card">
                <div class="field">
                    <label class="field-label">종목</label>
                    <SAutoInput
                        id="strategy-search"
                        v-model:name="inputName"
                        v-model:code="inputCode"
                        @search="onSelectStock"
                        width="100%" />
                    <span v-if="inputCode" class="picked">선택됨: {{ inputName }} ({{ inputCode }})</span>
                </div>

                <div class="date-row">
                    <div class="field">
                        <label class="field-label">시작일</label>
                        <input type="date" v-model="startDate" :min="minDate" :max="endDate || maxDate" />
                    </div>
                    <div class="field">
                        <label class="field-label">종료일</label>
                        <input type="date" v-model="endDate" :min="startDate || minDate" :max="maxDate" />
                    </div>
                </div>

                <button class="run-btn" :disabled="!canRun || isRunning" @click="runBacktest">
                    {{ isRunning ? '백테스트 실행 중…' : '백테스트 실행' }}
                </button>
            </section>

            <!-- 결과 -->
            <transition name="fade-slide">
                <section v-if="result" class="result-wrap">

                    <!-- 요약 헤더 -->
                    <div class="summary-head" :class="result.total_return >= 0 ? 'up' : 'down'">
                        <div class="sh-label">총 수익률</div>
                        <div class="sh-amount">{{ fmtPct(result.total_return) }}</div>
                        <div class="sh-pct">
                            <span class="sh-cap">매매 {{ result.trades }}건 · 승률 {{ result.win_rate }}%</span>
                        </div>
                    </div>

                    <!-- 핵심 지표 그리드 -->
                    <div class="stat-grid">
                        <div class="stat"><span class="st-k">총 수익률</span><span class="st-v" :class="cls(result.total_return)">{{ fmtPct(result.total_return) }}</span></div>
                        <div class="stat"><span class="st-k">승률</span><span class="st-v">{{ result.win_rate }}%</span></div>
                        <div class="stat"><span class="st-k">매매 횟수</span><span class="st-v">{{ result.trades }}건</span></div>
                        <div class="stat"><span class="st-k">MDD</span><span class="st-v down-c">{{ fmtPct(result.mdd) }}</span></div>
                        <div class="stat"><span class="st-k">Profit Factor</span><span class="st-v">{{ result.profit_factor }}</span></div>
                        <div class="stat"><span class="st-k">평균 보유봉</span><span class="st-v">{{ result.avg_bars }}봉</span></div>
                        <div class="stat"><span class="st-k">평균 수익률</span><span class="st-v" :class="cls(result.avg_ret)">{{ fmtPct(result.avg_ret) }}</span></div>
                        <div class="stat"><span class="st-k">평균 수익</span><span class="st-v up-c">{{ fmtPct(result.avg_win) }}</span></div>
                        <div class="stat"><span class="st-k">평균 손실</span><span class="st-v down-c">{{ fmtPct(result.avg_loss) }}</span></div>
                    </div>

                    <!-- 청산 사유 -->
                    <div class="exit-breakdown" v-if="result.exit_breakdown">
                        <span v-for="(v, k) in result.exit_breakdown" :key="k" class="exit-chip">
                            {{ exitLabel(k) }} {{ v }}
                        </span>
                    </div>

                    <!-- 매매 목록 -->
                    <div class="trades-head">매매 내역 {{ result.trade_list.length }}건</div>
                    <ul class="trade-list">
                        <li v-for="(t, i) in result.trade_list" :key="i" class="trade-item" :class="t.ret_net >= 0 ? 'win' : 'loss'">
                            <div class="ti-top">
                                <span class="ti-badge" :class="t.entry_action === 'BUY_SURGE' ? 'surge' : ''">{{ entryLabel(t.entry_action) }}</span>
                                <span class="ti-ret" :class="cls(t.ret_net)">{{ fmtPct(t.ret_net * 100) }}</span>
                            </div>
                            <div class="ti-line">
                                <span class="ti-d">{{ shortDate(t.entry_dt) }}</span>
                                <span class="ti-arrow">→</span>
                                <span class="ti-d">{{ shortDate(t.exit_dt) }}</span>
                                <span class="ti-bars">{{ t.bars_held }}봉</span>
                            </div>
                            <div class="ti-line sub">
                                <span>매수 {{ fmt(t.entry_price) }}</span>
                                <span>매도 {{ fmt(t.exit_price) }}</span>
                            </div>
                            <div class="ti-foot">
                                <span class="ti-exit">{{ exitLabel(t.exit_reason) }}</span>
                            </div>
                        </li>
                    </ul>
                </section>
            </transition>
        </div>

        <!-- ════════ 전략설정 레이어드 팝업 ════════ -->
        <transition name="fade">
            <div v-if="popupOpen" class="popup-overlay">
                <div class="popup-panel">
                    <header class="popup-head">
                        <h3>전략 설정 (S1)</h3>
                        <button class="popup-x" @click="closeStrategyPopup" aria-label="닫기">✕</button>
                    </header>

                    <div class="popup-body">
                        <div v-if="optLoading" class="opt-loading">불러오는 중…</div>

                        <template v-else>
                            <div v-for="g in S1_GROUPS" :key="g.title" class="opt-group">
                                <div class="opt-group-title">{{ g.title }}</div>
                                <div class="opt-fields">
                                    <div v-for="f in g.fields" :key="f.k" class="opt-field">
                                        <label class="opt-label">
                                            {{ f.label }}
                                            <span class="opt-def">기본 {{ f.def }}</span>
                                        </label>

                                        <!-- boolean → toggle -->
                                        <button v-if="f.type === 'bool'" type="button"
                                            :class="['mini-toggle', Number(s1Form[f.k]) === 1 ? 'on' : 'off']"
                                            @click="s1Form[f.k] = Number(s1Form[f.k]) === 1 ? 0 : 1">
                                            <span class="mini-knob"></span>
                                        </button>

                                        <!-- select -->
                                        <select v-else-if="f.type === 'select'" v-model="s1Form[f.k]">
                                            <option v-for="o in f.options" :key="o" :value="o">{{ o }}</option>
                                        </select>

                                        <!-- number -->
                                        <input v-else type="number"
                                            v-model="s1Form[f.k]"
                                            :step="f.type === 'decimal' ? 'any' : '1'"
                                            inputmode="decimal"
                                            :placeholder="String(f.def)" />
                                    </div>
                                </div>
                            </div>
                        </template>
                    </div>

                    <footer class="popup-foot">
                        <button class="pf-cancel" @click="closeStrategyPopup" :disabled="optSaving">취소</button>
                        <button class="pf-save" @click="saveStrategy" :disabled="optSaving || optLoading">
                            {{ optSaving ? '저장 중…' : '저장' }}
                        </button>
                    </footer>
                </div>
            </div>
        </transition>
    </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('매매전략 셋업 및 테스트');

/* ── 종목 / 기간 ── */
const inputName = ref('');
const inputCode = ref('');

const toYmd = (d) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
};
// 영업일(주말 제외) 기준 n일 전 날짜
const subtractBusinessDays = (from, n) => {
    const d = new Date(from);
    let remaining = n;
    while (remaining > 0) {
        d.setDate(d.getDate() - 1);
        const day = d.getDay();
        if (day !== 0 && day !== 6) remaining--;   // 일(0)·토(6) 제외
    }
    return d;
};

const today = new Date();
const past200 = subtractBusinessDays(today, 200);  // 영업일 기준 200일 전

const maxDate = toYmd(today);     // 종료일 최대 = 오늘
const minDate = toYmd(past200);   // 시작일 최소 = 영업일 200일 전
const startDate = ref(minDate);
const endDate = ref(maxDate);

const canRun = computed(() => !!inputCode.value && !!startDate.value && !!endDate.value);

const onSelectStock = (code) => {
    if (code) inputCode.value = code;
};

/* ── 백테스트 실행 ── */
const isRunning = ref(false);
const result = ref(null);

const runBacktest = async () => {
    if (!canRun.value) return;
    isRunning.value = true;
    result.value = null;
    try {
        const { data } = await aibeesApi.post('/api/v1/strategy/backtest', {
            stock_code: inputCode.value,
            start_date: startDate.value,
            end_date: endDate.value,
        });
        result.value = data.data;
    } catch (e) {
        console.error(e);
    } finally {
        isRunning.value = false;
    }
};

/* ── 전략설정 팝업 (user_options.s1_*) ── */
const popupOpen = ref(false);
const optLoading = ref(false);
const optSaving = ref(false);

const S1_GROUPS = [
    { title: '손절 / 익절 / 보유', fields: [
        { k: 's1_stop_loss_pct', label: '손절 비율', type: 'decimal', def: 0.05 },
        { k: 's1_take_profit_pct', label: '익절 비율', type: 'decimal', def: 0.30 },
        { k: 's1_max_hold_bars', label: '최대 보유 봉수', type: 'int', def: 12 },
    ]},
    { title: 'RSI', fields: [
        { k: 's1_rsi_overbought', label: 'RSI 과매수 기준', type: 'int', def: 70 },
        { k: 's1_rsi_ideal_low', label: 'RSI 신뢰구간 하한', type: 'int', def: 40 },
        { k: 's1_rsi_ideal_high', label: 'RSI 신뢰구간 상한', type: 'int', def: 65 },
    ]},
    { title: '거래량', fields: [
        { k: 's1_vol_ma_window', label: '평균 거래량 산정 기간', type: 'int', def: 20 },
        { k: 's1_vol_ma_mult', label: '진입 최소 거래량 배수', type: 'decimal', def: 0.5 },
    ]},
    { title: '국면 판정', fields: [
        { k: 's1_regime_window', label: '국면 분류 봉 길이', type: 'int', def: 90 },
        { k: 's1_regime_threshold', label: '하락국면 판정 임계값', type: 'decimal', def: 0.70 },
        { k: 's1_strict_need_macd_up', label: '하락국면: MACD≥Signal 요구', type: 'bool', def: 1 },
        { k: 's1_loose_need_vol_surge', label: '상승국면: 거래량 급증 요구', type: 'bool', def: 1 },
        { k: 's1_surge_relax_mult', label: '완화 급증 배수(전봉 대비)', type: 'decimal', def: 2.0 },
        { k: 's1_downtrend_surge_bypass', label: '하락국면 거래량급증 우회', type: 'bool', def: 1 },
        { k: 's1_surge_bypass_mult', label: '우회 급증 판정 배수', type: 'decimal', def: 2.0 },
    ]},
    { title: '트레일링 스탑', fields: [
        { k: 's1_use_trailing', label: '트레일링 스탑 사용', type: 'bool', def: 1 },
        { k: 's1_trail_basis', label: '트레일링 기준', type: 'select', options: ['close', 'high'], def: 'close' },
        { k: 's1_trail_activate_pct', label: '트레일링 활성화 수익 기준', type: 'decimal', def: 0.08 },
        { k: 's1_k_trail_atr', label: '샹들리에 ATR 배수', type: 'decimal', def: 3.0 },
        { k: 's1_trail_floor_pct', label: 'ATR 미산출시 대체 하락폭', type: 'decimal', def: 0.10 },
    ]},
    { title: '타임스탑', fields: [
        { k: 's1_time_stop_extend', label: '타임스탑 연장 허용', type: 'bool', def: 1 },
        { k: 's1_time_stop_band', label: '정체 판정 수익밴드', type: 'decimal', def: 0.02 },
        { k: 's1_time_stop_grace', label: '신고가 갱신 허용 봉수', type: 'int', def: 3 },
        { k: 's1_max_hold_bars_hard', label: '절대 보유 한도', type: 'int', def: 20 },
    ]},
    { title: 'OBV', fields: [
        { k: 's1_obv_dead_min_bars', label: 'OBV 데드크로스 무시 봉수', type: 'int', def: 5 },
    ]},
];

const ALL_KEYS = S1_GROUPS.flatMap(g => g.fields.map(f => f.k));
const s1Form = reactive({});
let s1Original = {};

const blankS1 = () => {
    const o = {};
    S1_GROUPS.forEach(g => g.fields.forEach(f => { o[f.k] = f.def; }));
    return o;
};

const openStrategyPopup = async () => {
    popupOpen.value = true;
    optLoading.value = true;
    Object.assign(s1Form, blankS1());
    try {
        const { data } = await aibeesApi.get('/api/v1/strategy/options');
        const d = data.data ?? {};
        ALL_KEYS.forEach(k => {
            if (d[k] !== undefined && d[k] !== null) s1Form[k] = d[k];
        });
        s1Original = JSON.parse(JSON.stringify(s1Form));
    } catch (e) {
        console.error(e);
        s1Original = JSON.parse(JSON.stringify(s1Form));
    } finally {
        optLoading.value = false;
    }
};

const closeStrategyPopup = () => { popupOpen.value = false; };

const fieldType = (k) => {
    for (const g of S1_GROUPS) for (const f of g.fields) if (f.k === k) return f.type;
    return 'decimal';
};

const saveStrategy = async () => {
    // 변경된 컬럼만 diff
    const diff = {};
    ALL_KEYS.forEach(k => {
        if (String(s1Form[k]) !== String(s1Original[k])) {
            const t = fieldType(k);
            const v = s1Form[k];
            if (t === 'select') diff[k] = v;
            else if (v === '' || v === null) diff[k] = null;
            else diff[k] = Number(v);
        }
    });
    if (Object.keys(diff).length === 0) {
        alert('변경된 항목이 없습니다.');
        return;
    }
    optSaving.value = true;
    try {
        await aibeesApi.patch('/api/v1/strategy/options', diff);
        s1Original = JSON.parse(JSON.stringify(s1Form));
        alert('저장되었습니다.');
        popupOpen.value = false;
    } catch (e) {
        console.error(e);
    } finally {
        optSaving.value = false;
    }
};

/* ── 포맷 헬퍼 ── */
const fmt = (v) => Number(v ?? 0).toLocaleString();
const fmtPct = (v) => (v > 0 ? '+' : '') + Number(v ?? 0).toFixed(2) + '%';
const cls = (v) => (v > 0 ? 'up-c' : v < 0 ? 'down-c' : '');
const shortDate = (s) => (s ? String(s).slice(0, 10) : '');
const entryLabel = (t) => (t === 'BUY_SURGE' ? '급등매수' : '매수');
const exitLabel = (t) => ({
    SELL_PROFIT: '익절',
    SELL_STOP_LOSS: '손절',
    SELL_TRAIL: '트레일링',
    SELL_TIME_STOP: '타임스탑',
    SELL_MAX_HOLD: '보유만료',
    EOD: '기간종료',
}[t] || t);
</script>

<style scoped lang="scss">
$white:    #ffffff;
$gray-50:  #f8f9fa;
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-400: #909090;
$gray-500: #6b6b6b;
$gray-700: #333333;
$gray-900: #111111;
$blue:     #1971c2;
$navy:     #1c3d6e;
$red:      #c92a2a;
$green:    #2db400;
$amber-on: #b8860b;

#stock-strategy {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 600px;
    margin: 0 auto;
    padding: 14px 14px 100px;
    box-sizing: border-box;
}

.guide-text {
    margin: 0 0 10px;
    font-size: 0.72rem;
    color: $gray-400;
    text-align: left;
}

/* 상단 바 */
.top-bar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 10px;
}
.strategy-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 8px 14px;
    border: 1px solid $navy;
    border-radius: 0.6rem;
    background: $white;
    color: $navy;
    font-size: 0.82rem;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    transition: background .12s;
    .gear { font-size: 0.9rem; }
    &:hover { background: #eef3fb; }
    &:active { transform: scale(0.97); }
}

/* 입력 카드 */
.setup-card {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.85rem;
    padding: 16px 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 0.78rem; font-weight: 700; color: $gray-500; text-align: left; }
.picked { font-size: 0.74rem; color: $blue; font-weight: 600; text-align: left; }

.date-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.date-row input[type="date"] {
    width: 100%;
    box-sizing: border-box;
    height: 42px;
    padding: 0 10px;
    border: 1px solid $gray-200;
    border-radius: 0.55rem;
    font-size: 0.9rem;
    color: $gray-900;
    background: $white;
    font-family: inherit;
    &:focus { outline: none; border-color: $blue; }
}

.run-btn {
    height: 46px;
    border: none;
    border-radius: 0.6rem;
    background: $navy;
    color: $white;
    font-size: 0.95rem;
    font-weight: 800;
    font-family: inherit;
    cursor: pointer;
    transition: background .12s;
    &:hover:not(:disabled) { background: $blue; }
    &:active:not(:disabled) { transform: scale(0.98); }
    &:disabled { background: #aab4c4; cursor: default; }
}

/* SAutoInput 라이트 테마 오버라이드 */
.field :deep(.auto-complete-container) { margin: 0; width: 100%; }
.field :deep(.search-bar) {
    width: 100% !important;
    box-sizing: border-box;
    margin: 0 !important;
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.55rem;
    padding: 4px 4px 4px 12px;
    box-shadow: none;
}
.field :deep(.search-bar input) { color: $gray-900; font-size: 0.92rem; &::placeholder { color: $gray-400; } }
.field :deep(.search-bar .search-btn) {
    background: $navy; color: $white; border-radius: 0.45rem;
    padding: 9px 14px; font-size: 0.82rem; font-weight: 700;
}
.field :deep(.suggestion-div) { background: $white; border: 1px solid $gray-200; border-radius: 0.55rem; box-shadow: 0 8px 24px rgba(0,0,0,.12); }
.field :deep(.suggestion-header) { background: $gray-50; .item { color: $gray-500; } }
.field :deep(.list-item) { .s_code, .s_type { color: $gray-400; } .s_name { color: $gray-900; } &:hover { background: $gray-50; } }

/* ── 결과 ── */
.result-wrap { margin-top: 16px; display: flex; flex-direction: column; gap: 14px; }

.summary-head {
    border-radius: 0.85rem;
    padding: 16px;
    color: $white;
    text-align: left;
    &.up { background: linear-gradient(135deg, #c92a2a, #e03131); }
    &.down { background: linear-gradient(135deg, #1c3d6e, #1971c2); }
    .sh-label { font-size: 0.74rem; opacity: .9; }
    .sh-amount { font-size: 1.5rem; font-weight: 800; margin-top: 2px; }
    .sh-pct { font-size: 0.9rem; font-weight: 700; margin-top: 4px; display: flex; flex-direction: column; gap: 2px;
        .sh-cap { font-size: 0.72rem; font-weight: 500; opacity: .85; } }
}

.stat-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.85rem;
    padding: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
    .stat { display: flex; justify-content: space-between; align-items: center; padding: 6px 8px; background: $gray-50; border-radius: 0.45rem; }
    .st-k { font-size: 0.74rem; color: $gray-500; }
    .st-v { font-size: 0.88rem; font-weight: 700; color: $gray-900; font-variant-numeric: tabular-nums; }
}

.up-c { color: $red; }
.down-c { color: $navy; }

.exit-breakdown { display: flex; flex-wrap: wrap; gap: 6px; }
.exit-chip {
    font-size: 0.74rem; font-weight: 600; color: $gray-500;
    background: $white; border: 1px solid $gray-200; border-radius: 999px; padding: 4px 10px;
}

.trades-head { font-size: 0.85rem; font-weight: 700; color: $gray-700; text-align: left; margin-top: 2px; }

.trade-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.trade-item {
    background: $white;
    border: 1px solid $gray-200;
    border-left-width: 4px;
    border-radius: 0.6rem;
    padding: 10px 12px;
    text-align: left;
    &.win { border-left-color: $red; }
    &.loss { border-left-color: $navy; }
}
.ti-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.ti-badge {
    font-size: 0.7rem; font-weight: 700; color: $gray-500;
    background: $gray-100; border-radius: 0.3rem; padding: 2px 7px;
    &.surge { color: $amber-on; background: #fff3bf; }
}
.ti-ret { font-size: 0.95rem; font-weight: 800; }
.ti-line { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: $gray-700; font-variant-numeric: tabular-nums;
    &.sub { color: $gray-500; font-size: 0.74rem; margin-top: 3px; justify-content: space-between; }
    .ti-arrow { color: $gray-400; }
    .ti-bars { margin-left: auto; font-size: 0.72rem; color: $gray-400; }
}
.ti-foot { display: flex; align-items: center; gap: 8px; margin-top: 6px; padding-top: 6px; border-top: 1px dashed $gray-100; font-size: 0.74rem;
    .ti-exit { font-weight: 600; color: $gray-500; }
    .ti-pnl { font-weight: 700; }
    .ti-bal { margin-left: auto; color: $gray-400; }
}

/* ── 팝업 ── */
.popup-overlay {
    position: fixed; inset: 0; z-index: 1000;
    background: rgba(0,0,0,.45);
    display: flex; align-items: flex-end; justify-content: center;
    @media (min-width: 600px) { align-items: center; }
}
.popup-panel {
    background: $white;
    width: 100%;
    max-width: 600px;
    max-height: 88vh;
    border-radius: 1rem 1rem 0 0;
    display: flex; flex-direction: column;
    @media (min-width: 600px) { border-radius: 1rem; max-height: 84vh; }
}
.popup-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 16px; border-bottom: 1px solid $gray-100;
    h3 { margin: 0; font-size: 1rem; font-weight: 800; color: $navy; }
    .popup-x { border: none; background: none; font-size: 1.1rem; color: $gray-400; cursor: pointer; }
}
.popup-body { overflow-y: auto; padding: 14px 16px; flex: 1; }
.opt-loading { text-align: center; color: $gray-400; padding: 40px 0; font-size: 0.9rem; }

.opt-group { margin-bottom: 16px; }
.opt-group-title { font-size: 0.8rem; font-weight: 800; color: $gray-700; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid $gray-100; text-align: left; }
.opt-fields { display: flex; flex-direction: column; gap: 10px; }
.opt-field { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.opt-label { font-size: 0.82rem; color: $gray-700; text-align: left; display: flex; flex-direction: column; gap: 2px; flex: 1;
    .opt-def { font-size: 0.66rem; color: $gray-400; }
}
.opt-field input[type="number"], .opt-field select {
    width: 110px; box-sizing: border-box; height: 38px;
    padding: 0 10px; border: 1px solid $gray-200; border-radius: 0.5rem;
    font-size: 0.88rem; color: $gray-900; background: $white; font-family: inherit; text-align: right;
    &:focus { outline: none; border-color: $blue; }
}
.opt-field select { text-align: left; }

.mini-toggle {
    flex: 0 0 auto; width: 44px; height: 25px; border-radius: 999px; border: 0;
    position: relative; cursor: pointer; transition: background .18s; background: #cfd6de;
    &.on { background: $green; }
    .mini-knob { position: absolute; top: 3px; left: 3px; width: 19px; height: 19px; background: #fff; border-radius: 50%; transition: transform .18s; box-shadow: 0 1px 2px rgba(0,0,0,.2); }
    &.on .mini-knob { transform: translateX(19px); }
}

.popup-foot {
    display: flex; gap: 10px; padding: 12px 16px;
    border-top: 1px solid $gray-100;
    background: rgba(255,255,255,.95);
    button { flex: 1; height: 44px; border-radius: 0.6rem; font-size: 0.92rem; font-weight: 700; font-family: inherit; cursor: pointer; }
    .pf-cancel { background: $white; border: 1px solid $gray-200; color: $gray-500; }
    .pf-save { background: $navy; border: none; color: $white; &:disabled { background: #aab4c4; cursor: default; } }
}

/* 전환 */
.fade-slide-enter-active, .fade-slide-leave-active { transition: opacity .3s ease, transform .3s ease; }
.fade-slide-enter-from { opacity: 0; transform: translateY(16px); }
.fade-slide-leave-to { opacity: 0; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
