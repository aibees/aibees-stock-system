<template>
    <div id="auto-trade-limit">
        <BrandHeader :title="'매도 수기 등록'" back="/trade" />

        <div class="contents">
            <section class="card">
                <p v-if="loadingHoldings" class="empty-msg">불러오는 중...</p>
                <p v-else-if="holdings.length === 0" class="empty-msg">계좌에 보유 중인 종목이 없습니다.</p>

                <ul v-else class="holding-list">
                    <li v-for="h in holdings" :key="h.stock_code" class="holding-row">
                        <div class="holding-main" @click="toggleExpand(h.stock_code)">
                            <div class="holding-id">
                                <span class="code-chip">{{ h.stock_code }}</span>
                                <span class="name">{{ h.stock_name }}</span>
                            </div>
                            <div class="holding-meta">
                                <span class="qty">{{ formatNumber(h.qty) }}주</span>
                                <span v-if="tiersOf(h.stock_code).armed.length" class="allocated"
                                      :class="{ over: allocatedPct(h.stock_code) > 100 }">
                                    {{ allocatedPct(h.stock_code) }}%
                                </span>
                            </div>
                            <span class="chevron" :class="{ open: expanded === h.stock_code }">▾</span>
                        </div>

                        <div class="holding-expand" v-if="expanded === h.stock_code">
                            <!-- 기준 가격: 지정가 %는 매입가(평단) 대비로 표시한다 -->
                            <p class="base-line">
                                매입가 {{ formatNumber(h.avg_price) }}원
                                <template v-if="Number(h.cur_price) > 0">
                                    · 현재가 {{ formatNumber(h.cur_price) }}원
                                    <span class="pct" :class="pctClass(pctVs(h.cur_price, h.avg_price))">
                                        ({{ formatPct(pctVs(h.cur_price, h.avg_price)) }})
                                    </span>
                                </template>
                            </p>

                            <!-- 이미 등록된 티어들 -->
                            <ul class="tier-list" v-if="tiersOf(h.stock_code).all.length">
                                <li v-for="t in tiersOf(h.stock_code).all" :key="t.id"
                                    class="tier-row" :class="tierStateClass(t)">
                                    <span class="tier-dir" :class="triggerOf(t).toLowerCase()"
                                          :title="TRIGGER_DESC[triggerOf(t)]">{{ TRIGGER_LABEL[triggerOf(t)] }}</span>
                                    <span class="tier-price">{{ formatNumber(t.sell_price) }}원</span>
                                    <span v-if="formatPct(pctVs(t.sell_price, h.avg_price))" class="pct"
                                          :class="pctClass(pctVs(t.sell_price, h.avg_price))">
                                        {{ formatPct(pctVs(t.sell_price, h.avg_price)) }}
                                    </span>
                                    <span class="tier-ratio">{{ pctOf(t.qty_ratio) }}%</span>
                                    <span class="tier-state" :class="tierStateClass(t)">{{ stateLabel(t) }}</span>
                                    <span class="tier-memo" v-if="t.memo">{{ t.memo }}</span>
                                    <span class="tier-fill" v-if="t.state === 'DONE'">
                                        {{ formatNumber(t.filled_price) }} · {{ formatDateTime(t.filled_at) }}
                                    </span>
                                    <button v-if="t.state === 'ARMED'" class="btn-tier-cancel"
                                            :disabled="busyId === t.id" @click.stop="onCancelTier(t)">취소</button>
                                </li>
                            </ul>

                            <!-- 신규 티어 추가 폼 -->
                            <div class="tier-form">
                                <div class="tier-form-row full">
                                    <label>방향</label>
                                    <div class="dir-toggle" role="group" aria-label="지정가 방향">
                                        <button type="button" :class="['dir-btn', 'up', { active: form.trigger_type === 'UP' }]"
                                                @click="pickTrigger('UP')">
                                            익절 <small>이상이면 매도</small>
                                        </button>
                                        <button type="button" :class="['dir-btn', 'down', { active: form.trigger_type === 'DOWN' }]"
                                                @click="pickTrigger('DOWN')">
                                            손절 <small>이하이면 매도</small>
                                        </button>
                                    </div>
                                </div>
                                <div class="tier-form-row full">
                                    <label>지정 매도가</label>
                                    <div class="input-with-hint">
                                        <input type="number" inputmode="decimal" v-model.number="form.sell_price" placeholder="0" />
                                        <span v-if="formPct" class="pct hint" :class="pctClass(formPctRaw)"
                                              title="매입가 대비">{{ formPct }}</span>
                                    </div>
                                </div>
                                <div class="tier-form-row full" v-if="formDesc.sentence">
                                    <p class="form-sentence">{{ formDesc.sentence }}</p>
                                    <p v-for="w in formDesc.warnings" :key="w" class="form-warning">{{ w }}</p>
                                </div>
                                <div class="tier-form-row">
                                    <label>비율(%)</label>
                                    <input type="number" v-model.number="form.qty_ratio_pct" min="1" max="100" placeholder="100" />
                                </div>
                                <div class="tier-form-row full">
                                    <label>메모</label>
                                    <input type="text" v-model="form.memo" maxlength="255" placeholder="선택 입력" />
                                </div>
                                <div class="tier-form-row switch-row">
                                    <label>감시 사용</label>
                                    <button :class="['toggle-btn', form.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                            @click="form.enabled_flag = form.enabled_flag === 'Y' ? 'N' : 'Y'">
                                        <span class="toggle-knob"></span>
                                    </button>
                                </div>
                                <button class="btn-add-tier" :disabled="isBusy" @click="onAdd(h)">
                                    + 지정가 추가
                                </button>
                            </div>
                        </div>
                    </li>
                </ul>
            </section>
        </div>
    </div>
</template>

<script setup>
import {
    fetchHoldings, fetchManualSells, addManualSell, cancelManualSell,
    MANUAL_SELL_STATE_LABEL, formatNumber, formatDateTime,
} from '@scripts/useAutoTrade.js';
import {
    TRIGGER_LABEL, TRIGGER_DESC, triggerOf, pctVs, formatPct, pctClass,
    suggestTrigger, describeTier, firesImmediately,
} from '@scripts/sellPrice.js';

const holdings = ref([]);
const manualSells = ref([]);   // 유저의 수기등록 전체(모든 종목·모든 상태)
const loadingHoldings = ref(false);
const isBusy = ref(false);
const busyId = ref(null);
const expanded = ref(null);

const defaultForm = () => ({ sell_price: null, trigger_type: 'UP', qty_ratio_pct: 100, memo: '', enabled_flag: 'Y' });
const form = reactive(defaultForm());

// 사용자가 방향 버튼을 직접 눌렀는가. 누르기 전에는 가격을 입력하는 대로 방향을 제안한다
// (현재가보다 낮으면 손절, 높으면 익절 — sellPrice.suggestTrigger). 직접 고른 뒤에는 건드리지 않는다.
const triggerTouched = ref(false);
const pickTrigger = (t) => { form.trigger_type = t; triggerTouched.value = true; };

const expandedHolding = computed(() => holdings.value.find(h => h.stock_code === expanded.value) ?? null);

// 입력 중인 가격의 매입가 대비 %(옆 칩) / 한 줄 설명·경고
const formPctRaw = computed(() => pctVs(form.sell_price, expandedHolding.value?.avg_price));
const formPct = computed(() => formatPct(formPctRaw.value));
const formDesc = computed(() => describeTier({
    trigger: form.trigger_type,
    price: form.sell_price,
    avg: expandedHolding.value?.avg_price,
    cur: expandedHolding.value?.cur_price,
}));

watch(() => form.sell_price, (price) => {
    if (triggerTouched.value) return;
    const h = expandedHolding.value;
    if (!h) return;
    form.trigger_type = suggestTrigger(price, h.cur_price, h.avg_price);
});

const load = async () => {
    loadingHoldings.value = true;
    try {
        const [h, m] = await Promise.all([fetchHoldings(), fetchManualSells()]);
        holdings.value = h ?? [];
        manualSells.value = m ?? [];
    } finally {
        loadingHoldings.value = false;
    }
};
onMounted(load);

// 종목코드별 티어 그룹 — 화면 전체 목록에서 매번 필터링하지 않도록 캐시.
const tiersByCode = computed(() => {
    const map = {};
    for (const t of manualSells.value) {
        (map[t.stock_code] ??= []).push(t);
    }
    for (const list of Object.values(map)) {
        list.sort((a, b) => Number(a.sell_price) - Number(b.sell_price));
    }
    return map;
});

const tiersOf = (code) => {
    const all = tiersByCode.value[code] ?? [];
    return { all, armed: all.filter(t => t.state === 'ARMED') };
};

const pctOf = (ratio) => Math.round(Number(ratio) * 100);

const allocatedPct = (code) => {
    const armed = tiersOf(code).armed;
    return armed.reduce((sum, t) => sum + pctOf(t.qty_ratio), 0);
};

const stateLabel = (t) => MANUAL_SELL_STATE_LABEL[t.state] ?? t.state;
const tierStateClass = (t) => ({
    armed: t.state === 'ARMED', done: t.state === 'DONE', cancelled: t.state === 'CANCELLED',
});

const toggleExpand = (code) => {
    expanded.value = expanded.value === code ? null : code;
    Object.assign(form, defaultForm());
    triggerTouched.value = false;
};

const onAdd = async (holding) => {
    if (!form.sell_price || Number(form.sell_price) <= 0) { alert('지정 매도가를 입력해 주세요.'); return; }
    const pct = (form.qty_ratio_pct === null || form.qty_ratio_pct === '') ? 100 : Number(form.qty_ratio_pct);
    if (pct <= 0 || pct > 100) { alert('비율은 1~100 사이여야 합니다.'); return; }

    const already = allocatedPct(holding.stock_code);
    if (already + pct > 100 &&
        !confirm(`이 종목에 이미 ${already}% 등록돼 있습니다. 이번 ${pct}%를 더하면 ${already + pct}%로 100%를 넘습니다. 계속할까요?`)) {
        return;
    }

    // 등록 즉시 체결되는 설정(현재가가 이미 조건을 만족)은 의도한 것인지 한 번 더 확인한다.
    if (form.enabled_flag === 'Y'
        && firesImmediately(form.trigger_type, form.sell_price, holding.cur_price)
        && !confirm(`현재가(${formatNumber(holding.cur_price)}원)가 이미 `
            + `${formatNumber(form.sell_price)}원 ${TRIGGER_DESC[form.trigger_type]} 조건을 만족해 `
            + `등록 즉시 매도됩니다. 계속할까요?`)) {
        return;
    }

    isBusy.value = true;
    try {
        await addManualSell({
            stock_code: holding.stock_code,
            stock_name: holding.stock_name,
            sell_price: Number(form.sell_price),
            trigger_type: form.trigger_type,
            qty_ratio: pct / 100,
            enabled_flag: form.enabled_flag,
            memo: form.memo,
        });
        Object.assign(form, defaultForm());
        triggerTouched.value = false;
        await load();
    } finally {
        isBusy.value = false;
    }
};

const onCancelTier = async (tier) => {
    if (!confirm(`${formatNumber(tier.sell_price)}원 지정가 등록을 취소할까요?`)) return;
    busyId.value = tier.id;
    try {
        await cancelManualSell(tier.id);
        await load();
    } finally {
        busyId.value = null;
    }
};
</script>

<style scoped lang="scss">
// 무채색 팔레트(/trade 대시보드와 통일). 변수명은 유지, 값만 회색조로 교체.
$white: #ffffff;
$gray-50: #FFFBEA;
$gray-100: #F3EAD2;
$gray-200: #EFE2BC;
$gray-300: #E3D3A8;
$gray-400: #9A8C7E;
$gray-500: #6B5B4E;
$gray-700: #4A3628;
$gray-900: #2B1D14;
$blue: #1F5BD1;
$navy: #74462A;
$red: #C8282A;
$green: #1F7A3E;

#auto-trade-limit {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;

    * {
        box-sizing: border-box;
    }
}

.contents {
    max-width: 900px;
    margin: 0 auto;
    padding: 20px 16px 100px;
    overflow-x: hidden;

    @media (max-width: 480px) {
        padding: 14px 10px 90px;
    }
}

.page-sub {
    margin: 0 0 14px;
    font-size: .82rem;
    color: $gray-500;
    line-height: 1.5;
}

.card {
    border-radius: 12px;
    background: $white;
    border: 1px solid $gray-200;
    padding: 10px 14px;

    @media (max-width: 480px) {
        padding: 6px 10px;
    }
}

.empty-msg {
    text-align: center;
    color: $gray-500;
    font-size: .84rem;
    padding: 16px 0;
}

.holding-list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.holding-row {
    border-bottom: 1px solid $gray-100;

    &:last-child {
        border-bottom: 0;
    }
}

.holding-main {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px 10px;
    padding: 12px 4px;
    cursor: pointer;

    &:hover {
        background: $gray-50;
    }
}

.holding-id {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex: 1 1 140px;

    .code-chip {
        flex: 0 0 auto;
        font-family: monospace;
        background: $gray-100;
        padding: 2px 6px;
        font-size: .72rem;
    }

    .name {
        font-weight: 600;
        font-size: .86rem;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
}

.holding-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 0 0 auto;
    font-size: .8rem;
    color: $gray-500;
    white-space: nowrap;

    .allocated {
        color: $gray-700;
        font-weight: 600;

        &.over {
            color: $gray-900;
            font-weight: 800;
        }
    }
}

.chevron {
    flex: 0 0 auto;
    color: $gray-400;
    transition: transform .15s;

    &.open {
        transform: rotate(180deg);
    }
}

.holding-expand {
    padding: 0 4px 14px;
}

.base-line {
    margin: 0 0 10px;
    font-size: .8rem;
    color: $gray-500;
}

// 지정가 %(매입가 대비). 한국 시장 관례: 상승 적색 / 하락 청색
.pct {
    font-weight: 700;
    font-size: .76rem;
    white-space: nowrap;

    &.up { color: $red; }
    &.down { color: $blue; }
    &.flat { color: $gray-500; }
}

.tier-list {
    list-style: none;
    margin: 0 0 10px;
    padding: 0;
}

.tier-row {
    border-radius: 12px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px 10px;
    padding: 8px 10px;
    font-size: .8rem;
    background: $gray-50;
    border: 1px solid $gray-100;
    margin-bottom: 6px;

    &.done {
        opacity: .7;
    }

    &.cancelled {
        opacity: .45;
        text-decoration: line-through;
    }

    .tier-dir {
        flex: 0 0 auto;
        font-size: .72rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 12px;
        border: 1px solid;

        &.up { color: $red; border-color: $red; }
        &.down { color: $blue; border-color: $blue; }
    }

    .tier-price {
        font-weight: 700;
    }

    .tier-ratio {
        color: $gray-500;
    }

    .tier-state {
        font-size: .72rem;
        padding: 2px 8px;
        background: $gray-200;
        color: $gray-900;

        &.armed {
            border-radius: 12px;
            background: $gray-100;
            color: $gray-900;
            border: 1px solid $gray-300;
        }

        &.done {
            background: #74462A;
            color: $white;
        }

        &.cancelled {
            background: $gray-50;
            color: $gray-400;
        }
    }

    .tier-memo {
        color: $gray-500;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1 1 80px;
    }

    .tier-fill {
        color: $gray-500;
        font-size: .74rem;
        flex: 0 0 auto;
    }
}

.btn-tier-cancel {
    border-radius: 12px;
    margin-left: auto;
    flex: 0 0 auto;
    border: 1px solid $gray-300;
    background: transparent;
    color: $gray-700;
    padding: 4px 10px;
    font-size: .76rem;
    cursor: pointer;

    &:disabled {
        opacity: .5;
        cursor: not-allowed;
    }
}

.tier-form {
    border-radius: 12px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    background: $gray-50;
    border: 1px dashed $gray-300;
    padding: 12px;

    @media (max-width: 480px) {
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        padding: 10px;
    }
}

.tier-form-row {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-width: 0;

    &.full {
        grid-column: 1 / -1;
    }

    &.switch-row {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        grid-column: 1 / -1;
    }

    label {
        font-size: .76rem;
        font-weight: 600;
        color: $gray-500;
    }

    input {
        border-radius: 12px;
        width: 100%;
        height: 36px;
        border: 1px solid $gray-200;
        padding: 0 10px;
        font-size: .84rem;
        background: $white;
    }
}

.dir-toggle {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.dir-btn {
    border-radius: 12px;
    height: 40px;
    border: 1px solid $gray-300;
    background: $white;
    color: $gray-700;
    font-size: .84rem;
    font-weight: 700;
    cursor: pointer;

    small {
        font-size: .68rem;
        font-weight: 500;
        margin-left: 4px;
        opacity: .8;
    }

    &.up.active { background: $red; border-color: $red; color: $white; }
    &.down.active { background: $blue; border-color: $blue; color: $white; }
}

.input-with-hint {
    display: flex;
    align-items: center;
    gap: 10px;

    input { flex: 1 1 auto; min-width: 0; }

    .pct.hint {
        flex: 0 0 auto;
        font-size: .86rem;
        min-width: 56px;
        text-align: right;
    }
}

.form-sentence {
    margin: 0;
    font-size: .8rem;
    font-weight: 600;
    color: $gray-700;
}

.form-warning {
    margin: 2px 0 0;
    font-size: .76rem;
    color: $red;
    line-height: 1.4;
}

.toggle-btn {
    border-radius: 12px;
    width: 44px;
    height: 24px;
    border: 1px solid $gray-300;
    position: relative;
    cursor: pointer;
    flex: 0 0 auto;
    background: $white;

    &.active {
        background: #74462A;
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
        transform: translateX(19px);
        background: $white;
    }
}

.btn-add-tier {
    grid-column: 1 / -1;
    height: 40px;
    border: 0;
    background: $navy;
    color: #fff;
    font-size: .84rem;
    font-weight: 700;
    cursor: pointer;

    &:disabled {
        opacity: .5;
        cursor: not-allowed;
    }
}
</style>
