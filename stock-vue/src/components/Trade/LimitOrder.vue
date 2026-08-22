<template>
    <div id="auto-trade-limit">
        <Headers :prop_title="'매도 수기 등록'" />

        <div class="contents">

            <section class="head-desc">
                <div>
                    <h2>매도 수기 등록</h2>
                    <p class="sub-text">
                        보유 종목에 지정 매도가를 등록하면, 지금 운용 방식이 무엇이든
                        <b>그 종목만은 자동 매도 판정(손절·익절·트레일링) 대신 이 가격 도달 여부로</b>
                        worker 가 대신 체결합니다. 매수는 관여하지 않습니다 — 매수는 항상 현재 운용 방식이 담당합니다.
                        <br />
                        종목당 지정가를 <b>여러 개</b>(예: 30%는 5만원, 30%는 5만5천원, 나머지는 6만원) 등록할 수 있고,
                        <b>여러 종목</b>을 동시에 등록할 수도 있습니다.
                    </p>
                </div>
            </section>

            <p class="holding-note">
                직접 매수한 종목(worker 자동매매)이 아니어도 <b>계좌에 보유 중(user_holdings)</b>이기만 하면
                등록할 수 있습니다. 다만 worker 가 아직 이 종목을 감시 대상으로 편입하기 전이라면, 계좌 동기화
                주기(기본 30초) 안에 감시가 시작됩니다 — 등록 직후 잠깐 "감시 대기"로 보일 수 있습니다.
            </p>

            <!-- ── 보유 종목 목록 ── -->
            <section class="card">
                <div class="card-head">
                    <h4>보유 종목</h4>
                    <input class="filter-input" v-model="holdingFilter" placeholder="종목명 또는 코드로 찾기" />
                </div>

                <p v-if="loadingHoldings" class="empty-msg">불러오는 중...</p>
                <p v-else-if="filteredHoldings.length === 0" class="empty-msg">
                    {{ holdings.length === 0 ? '계좌에 보유 중인 종목이 없습니다.' : '검색 결과가 없습니다.' }}
                </p>

                <ul v-else class="holding-list">
                    <li v-for="h in filteredHoldings" :key="h.stock_code" class="holding-row">
                        <div class="holding-main" @click="toggleExpand(h.stock_code)">
                            <div class="holding-id">
                                <span class="code-chip">{{ h.stock_code }}</span>
                                <span class="name">{{ h.stock_name }}</span>
                            </div>
                            <div class="holding-meta">
                                <span>보유 {{ formatNumber(h.qty) }}주</span>
                                <span>평단 {{ formatNumber(h.avg_price) }}</span>
                                <span v-if="tiersOf(h.stock_code).armed.length" class="allocated"
                                      :class="{ over: allocatedPct(h.stock_code) > 100 }">
                                    등록 {{ allocatedPct(h.stock_code) }}%
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
                                        체결 {{ formatNumber(t.filled_price) }} · {{ formatDateTime(t.filled_at) }}
                                    </span>
                                    <button v-if="t.state === 'ARMED'" class="btn-tier-cancel"
                                            :disabled="busyId === t.id" @click.stop="onCancelTier(t)">취소</button>
                                </li>
                            </ul>
                            <p v-else class="empty-msg small">등록된 지정가가 없습니다.</p>

                            <!-- 신규 티어 추가 폼 -->
                            <div class="tier-form">
                                <div class="tier-form-row">
                                    <label>지정 매도가</label>
                                    <input type="number" v-model.number="form.sell_price" placeholder="0" />
                                </div>
                                <div class="tier-form-row">
                                    <label>비율</label>
                                    <div class="inline">
                                        <input type="number" v-model.number="form.qty_ratio_pct" min="1" max="100" placeholder="100" />
                                        <span class="inline-text">% (지금 보유수량 {{ formatNumber(h.qty) }}주 기준)</span>
                                    </div>
                                </div>
                                <div class="tier-form-row">
                                    <label>메모</label>
                                    <input type="text" v-model="form.memo" maxlength="255" placeholder="선택 입력" />
                                </div>
                                <div class="tier-form-row">
                                    <label>감시 사용</label>
                                    <button :class="['toggle-btn', form.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                            @click="form.enabled_flag = form.enabled_flag === 'Y' ? 'N' : 'Y'">
                                        <span class="toggle-knob"></span>
                                    </button>
                                </div>
                                <button class="btn-add-tier" :disabled="isBusy" @click="onAdd(h)">
                                    + 이 종목에 지정가 추가
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
const holdingFilter = ref('');
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

const filteredHoldings = computed(() => {
    const kw = holdingFilter.value.trim().toLowerCase();
    if (!kw) return holdings.value;
    return holdings.value.filter(h =>
        (h.stock_name || '').toLowerCase().includes(kw) ||
        (h.stock_code || '').toLowerCase().includes(kw));
});

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
        alert('저장되었습니다. 지금 운용 방식과 무관하게 이 지정가로 감시됩니다.');
    } finally {
        isBusy.value = false;
    }
};

const onCancelTier = async (tier) => {
    if (!confirm(`${formatNumber(tier.sell_price)}원 지정가 등록을 취소할까요? 같은 종목의 다른 지정가는 그대로 유지됩니다.`)) return;
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
$white: #ffffff;
$gray-50: #f8f9fa;
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-400: #909090;
$gray-500: #6b6b6b;
$gray-900: #111111;
$blue: #1971c2;
$navy: #1c3d6e;
$red: #c92a2a;
$amber: #e67700;
$green: #2f9e44;

#auto-trade-limit {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 900px;
    margin: 0 auto;
    padding: 24px 16px 120px;
}

.head-desc {
    margin-bottom: 10px;

    h2 {
        margin: 0;
        font-size: 1.3rem;
        font-weight: 700;
    }

    .sub-text {
        margin: 4px 0 0;
        font-size: .82rem;
        color: $gray-500;
        line-height: 1.5;
    }
}

.holding-note {
    margin: 0 0 16px;
    font-size: .78rem;
    color: $amber;
    background: #fff8e1;
    border: 1px solid #ffe08a;
    border-radius: 8px;
    padding: 9px 12px;
    line-height: 1.5;
}

.card {
    background: $white;
    border: 1px solid $gray-100;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 14px;
}

.card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;

    h4 {
        margin: 0;
        font-size: .9rem;
        font-weight: 700;
        white-space: nowrap;
    }

    .filter-input {
        flex: 1;
        max-width: 260px;
        height: 34px;
        border: 1px solid $gray-200;
        border-radius: 8px;
        padding: 0 10px;
        font-size: .82rem;
    }
}

.empty-msg {
    text-align: center;
    color: $gray-500;
    font-size: .84rem;
    padding: 16px 0;

    &.small {
        padding: 8px 0;
        font-size: .78rem;
    }
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
    gap: 12px;
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
    min-width: 220px;

    .code-chip {
        font-family: monospace;
        background: $gray-100;
        border-radius: 6px;
        padding: 2px 6px;
        font-size: .76rem;
    }

    .name {
        font-weight: 600;
        font-size: .88rem;
    }
}

.holding-meta {
    display: flex;
    gap: 14px;
    flex: 1;
    font-size: .8rem;
    color: $gray-500;

    .allocated {
        color: $blue;
        font-weight: 600;

        &.over {
            color: $red;
        }
    }
}

.chevron {
    color: $gray-400;
    transition: transform .15s;

    &.open {
        transform: rotate(180deg);
    }
}

.holding-expand {
    padding: 4px 4px 16px 4px;
}

.tier-list {
    list-style: none;
    margin: 0 0 10px;
    padding: 0;
}

.tier-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: .82rem;
    background: $gray-50;
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
        min-width: 90px;
    }

    .tier-ratio {
        color: $gray-500;
        min-width: 48px;
    }

    .tier-state {
        font-size: .74rem;
        padding: 2px 8px;
        border-radius: 999px;
        background: $gray-200;
        color: $gray-900;

        &.armed {
            background: rgba(25, 113, 194, .15);
            color: $blue;
        }

        &.done {
            background: rgba(47, 158, 68, .15);
            color: $green;
        }

        &.cancelled {
            background: $gray-100;
            color: $gray-500;
        }
    }

    .tier-memo {
        color: $gray-500;
        flex: 1;
    }

    .tier-fill {
        color: $gray-500;
        font-size: .76rem;
    }
}

.btn-tier-cancel {
    margin-left: auto;
    border: 1px solid $red;
    background: transparent;
    color: $red;
    border-radius: 6px;
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
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    background: $gray-50;
    border: 1px dashed $gray-200;
    border-radius: 10px;
    padding: 14px;

    @media (max-width: 700px) {
        grid-template-columns: 1fr;
    }
}

.tier-form-row {
    display: flex;
    flex-direction: column;
    gap: 5px;

    label {
        font-size: .76rem;
        font-weight: 600;
        color: $gray-500;
    }

    input {
        height: 34px;
        border: 1px solid $gray-200;
        border-radius: 8px;
        padding: 0 10px;
        font-size: .84rem;
        background: $white;
    }

    .inline {
        display: flex;
        align-items: center;
        gap: 8px;

        input {
            flex: 1;
        }
    }

    .inline-text {
        font-size: .74rem;
        color: $gray-500;
        white-space: nowrap;
    }
}

.toggle-btn {
    width: 44px;
    height: 24px;
    border-radius: 999px;
    border: 0;
    position: relative;
    cursor: pointer;
    flex: 0 0 auto;

    &.active {
        background: $green;
    }

    &.inactive {
        background: $gray-200;
    }

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

    &.active .toggle-knob {
        transform: translateX(20px);
    }
}

.btn-add-tier {
    grid-column: 1 / -1;
    height: 40px;
    border: 0;
    border-radius: 8px;
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
