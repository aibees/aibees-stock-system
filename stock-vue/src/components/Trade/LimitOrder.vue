<template>
    <div id="auto-trade-limit">
        <Headers :prop_title="'매도 수기 등록'" />

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
                            <!-- 이미 등록된 티어들 -->
                            <ul class="tier-list" v-if="tiersOf(h.stock_code).all.length">
                                <li v-for="t in tiersOf(h.stock_code).all" :key="t.id"
                                    class="tier-row" :class="tierStateClass(t)">
                                    <span class="tier-price">{{ formatNumber(t.sell_price) }}원</span>
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
                                <div class="tier-form-row">
                                    <label>지정 매도가</label>
                                    <input type="number" v-model.number="form.sell_price" placeholder="0" />
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

const holdings = ref([]);
const manualSells = ref([]);   // 유저의 수기등록 전체(모든 종목·모든 상태)
const loadingHoldings = ref(false);
const isBusy = ref(false);
const busyId = ref(null);
const expanded = ref(null);

const defaultForm = () => ({ sell_price: null, qty_ratio_pct: 100, memo: '', enabled_flag: 'Y' });
const form = reactive(defaultForm());

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

    isBusy.value = true;
    try {
        await addManualSell({
            stock_code: holding.stock_code,
            stock_name: holding.stock_name,
            sell_price: Number(form.sell_price),
            qty_ratio: pct / 100,
            enabled_flag: form.enabled_flag,
            memo: form.memo,
        });
        Object.assign(form, defaultForm());
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
$gray-50: #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$blue: #141414;
$navy: #141414;
$red: #141414;
$green: #141414;

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

.tier-list {
    list-style: none;
    margin: 0 0 10px;
    padding: 0;
}

.tier-row {
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
            background: $gray-100;
            color: $gray-900;
            border: 1px solid $gray-300;
        }

        &.done {
            background: $gray-900;
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
        width: 100%;
        height: 36px;
        border: 1px solid $gray-200;
        padding: 0 10px;
        font-size: .84rem;
        background: $white;
    }
}

.toggle-btn {
    width: 44px;
    height: 24px;
    border: 1px solid $gray-300;
    position: relative;
    cursor: pointer;
    flex: 0 0 auto;
    background: $white;

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
