<template>
    <div id="manual-buy">
        <BrandHeader title="수동 매수" back="/trade" />

        <main class="contents">
            <section class="form">
                <button type="button" class="stock-row" @click="pickerOpen = true">
                    <span class="row-label">종목</span>
                    <span v-if="stock" class="stock-value">{{ stock.stock_name }} <em>{{ stock.stock_code }}</em></span>
                    <span v-else class="stock-empty">종목 선택</span>
                    <span class="chevron" aria-hidden="true">›</span>
                </button>

                <div class="field">
                    <span class="row-label">주문 방식</span>
                    <div class="segment" role="group" aria-label="주문 방식">
                        <button type="button" :class="['seg-btn', { on: orderType === 'MARKET' }]"
                            :aria-pressed="orderType === 'MARKET'" @click="orderType = 'MARKET'">시장가</button>
                        <button type="button" :class="['seg-btn', { on: orderType === 'LIMIT' }]"
                            :aria-pressed="orderType === 'LIMIT'" @click="orderType = 'LIMIT'">지정가</button>
                    </div>
                </div>

                <label v-if="orderType === 'LIMIT'" class="field">
                    <span class="row-label">지정가</span>
                    <span class="input-unit">
                        <input v-model.number="limitPrice" type="number" inputmode="numeric" min="1" :step="priceTick" placeholder="0" />
                        <span>원</span>
                    </span>
                </label>
                <p v-if="priceError" class="field-error">{{ priceError }}</p>

                <label class="field">
                    <span class="row-label">수량</span>
                    <span class="input-unit">
                        <input v-model.number="qty" type="number" inputmode="numeric" min="1" step="1" placeholder="0" />
                        <span>주</span>
                    </span>
                </label>

                <dl class="summary">
                    <div>
                        <dt>주문가능금액</dt>
                        <dd>{{ balance === null ? '-' : `${formatNumber(balance)}원` }}</dd>
                    </div>
                    <div v-if="orderType === 'LIMIT'">
                        <dt>주문금액</dt>
                        <dd :class="{ over: overBalance }">{{ orderAmount === null ? '-' : `${formatNumber(orderAmount)}원` }}</dd>
                    </div>
                </dl>

                <p class="note" v-if="orderType === 'MARKET'">시장가는 정규장(09:00~15:30)에만 주문할 수 있고, 체결 가격은 시장 상황에 따라 정해져요.</p>
                <p class="note" v-else>지정가는 당일에만 유효해요. 프리마켓·애프터마켓에서도 주문할 수 있어요.</p>
                <p class="note">매매정지 중에도 주문이 나가요. 체결된 종목은 운용모드의 손절·익절 규칙으로 자동 매도될 수 있어요.</p>

                <button type="button" class="btn-buy" :disabled="!canSubmit" @click="onSubmit">
                    {{ submitting ? '요청 중…' : '매수 주문' }}
                </button>
            </section>

            <section class="orders">
                <h2>주문 내역</h2>
                <p v-if="loadError" class="empty error">{{ loadError }}</p>
                <p v-else-if="loading" class="empty">불러오는 중...</p>
                <p v-else-if="orders.length === 0" class="empty">아직 주문 내역이 없어요.</p>
                <ul v-else>
                    <li v-for="o in orders" :key="o.id" class="order">
                        <div class="order-top">
                            <span class="order-name">{{ o.stock_name || o.stock_code }}</span>
                            <span :class="['order-state', stateClass(o)]">{{ stateLabel(o) }}</span>
                        </div>
                        <div class="order-meta">
                            {{ o.order_type === 'LIMIT' ? `지정가 ${formatNumber(o.limit_price)}원` : '시장가' }}
                            · {{ formatNumber(o.qty) }}주 · {{ formatDateTime(o.created_at) }}
                        </div>
                        <div v-if="Number(o.filled_qty) > 0" class="order-meta">
                            체결 {{ formatNumber(o.filled_qty) }}주<template v-if="o.avg_fill_price"> · 평균 {{ formatNumber(o.avg_fill_price) }}원</template>
                        </div>
                        <div v-if="o.reason" class="order-reason">{{ o.reason }}</div>
                        <button v-if="canCancel(o)" type="button" class="btn-cancel" :disabled="busyId === o.id"
                            @click="onCancel(o)">주문 취소</button>
                    </li>
                </ul>
            </section>
        </main>

        <StockPickerModal :visible="pickerOpen" title="매수할 종목 선택" @pick="onPick" @close="pickerOpen = false" />
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';
import {
    fetchManualBuys, placeManualBuy, cancelManualBuy, MANUAL_BUY_STATE_LABEL,
    formatNumber, formatDateTime, apiErrorMessage,
} from '@scripts/useAutoTrade.js';
import StockPickerModal from './StockPickerModal.vue';

const userSession = assUserSession();

/* ── 입력 ── */
const stock = ref(null);
const orderType = ref('MARKET');
const limitPrice = ref(null);
const qty = ref(null);
const pickerOpen = ref(false);
const balance = ref(null);

const onPick = (s) => {
    stock.value = s;
    pickerOpen.value = false;
};

// 2023.1 호가가격단위(서버 router_manual_buy._TICKS 와 같은 표). 최종 검증은 서버가 한다.
const TICKS = [[2000, 1], [5000, 5], [20000, 10], [50000, 50], [200000, 100], [500000, 500]];
const tickOf = (price) => (TICKS.find(([upper]) => price < upper) || [0, 1000])[1];
const priceTick = computed(() => tickOf(Number(limitPrice.value) || 0));

const priceError = computed(() => {
    if (orderType.value !== 'LIMIT' || !limitPrice.value) return '';
    return limitPrice.value % priceTick.value === 0 ? ''
        : `이 가격대의 호가 단위는 ${formatNumber(priceTick.value)}원이에요.`;
});
const qtyValid = computed(() => Number.isInteger(qty.value) && qty.value > 0);
const priceValid = computed(() => orderType.value === 'MARKET' || (limitPrice.value > 0 && !priceError.value));
const orderAmount = computed(() => (qtyValid.value && limitPrice.value > 0 ? qty.value * limitPrice.value : null));
const overBalance = computed(() => balance.value !== null && orderAmount.value !== null && orderAmount.value > balance.value);

const submitting = ref(false);
const canSubmit = computed(() => stock.value && qtyValid.value && priceValid.value && !submitting.value);

/* ── 주문 ──
 * 같은 입력을 다시 보내면(응답 유실 후 재시도) 같은 키를 쓴다 → 서버가 같은 주문을 돌려주고 주문은 1건만 나간다.
 * 입력이 바뀌면 새 주문이므로 키를 버린다. */
let clientKey = null;
watch([stock, orderType, limitPrice, qty], () => { clientKey = null; });
const newClientKey = () => globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const onSubmit = async () => {
    if (!canSubmit.value) return;
    const isLimit = orderType.value === 'LIMIT';
    const line = isLimit
        ? `지정가 ${formatNumber(limitPrice.value)}원 · ${formatNumber(qty.value)}주\n주문금액 ${formatNumber(orderAmount.value)}원`
        : `시장가 · ${formatNumber(qty.value)}주\n체결 가격은 시장 상황에 따라 정해져요.`;
    if (!confirm(`${stock.value.stock_name}을(를) 매수할까요?\n${line}`)) return;

    clientKey = clientKey ?? newClientKey();
    submitting.value = true;
    try {
        await placeManualBuy({
            client_key: clientKey,
            stock_code: stock.value.stock_code,
            order_type: orderType.value,
            qty: qty.value,
            limit_price: isLimit ? limitPrice.value : null,
        });
        qty.value = null;
        limitPrice.value = null;
        await loadOrders();
    } catch (e) {
        alert(apiErrorMessage(e, '매수 요청에 실패했어요. 잠시 후 다시 시도해 주세요.'));
    } finally {
        submitting.value = false;
    }
};

/* ── 주문 내역 ── */
const orders = ref([]);
const loading = ref(true);
const loadError = ref('');
const busyId = ref(null);

const ACTIVE_STATES = ['REQUESTED', 'ORDERING', 'OPEN'];
const canCancel = (o) => ['REQUESTED', 'OPEN'].includes(o.state) && o.cancel_requested !== 'Y';
const stateLabel = (o) => {
    if (o.state === 'OPEN' && o.cancel_requested === 'Y') return '취소 중';
    if (o.state === 'OPEN' && Number(o.filled_qty) > 0) return '부분 체결';
    return MANUAL_BUY_STATE_LABEL[o.state] ?? o.state;
};
const stateClass = (o) => {
    if (o.state === 'FILLED') return 'done';
    if (['REJECTED', 'UNKNOWN'].includes(o.state)) return 'bad';
    return ACTIVE_STATES.includes(o.state) ? 'active' : 'muted';
};

const loadBalance = async () => {
    try {
        const { data } = await aibeesApi.get(`/api/v1/users/${userSession.user?.loginInfo?.user_id}/account`);
        balance.value = data?.user_balance != null ? Number(data.user_balance) : null;
    } catch {
        balance.value = null;   // 표시용 값이다 — 실제 한도는 주문 직전 worker 가 확인한다
    }
};

const loadOrders = async () => {
    try {
        const before = orders.value.filter((o) => ACTIVE_STATES.includes(o.state)).length;
        orders.value = await fetchManualBuys();
        loadError.value = '';
        const after = orders.value.filter((o) => ACTIVE_STATES.includes(o.state)).length;
        if (after !== before) loadBalance();
    } catch (e) {
        loadError.value = apiErrorMessage(e, '주문 내역을 불러오지 못했어요.');
    } finally {
        loading.value = false;
    }
};

const onCancel = async (o) => {
    if (!confirm(`${o.stock_name || o.stock_code} 주문을 취소할까요?`)) return;
    busyId.value = o.id;
    try {
        await cancelManualBuy(o.id);
        await loadOrders();
    } catch (e) {
        alert(apiErrorMessage(e, '주문을 취소하지 못했어요.'));
    } finally {
        busyId.value = null;
    }
};

/* 진행 중 주문이 있을 때만 자주 확인한다. 화면을 떠나거나 백그라운드면 멈춘다. */
const POLL_ACTIVE_MS = 3000;
const POLL_IDLE_MS = 30000;
let timer = null;
let unmounted = false;
const schedule = () => {
    if (unmounted) return;
    const active = orders.value.some((o) => ACTIVE_STATES.includes(o.state));
    timer = setTimeout(async () => {
        if (document.visibilityState === 'visible') await loadOrders();
        schedule();
    }, active ? POLL_ACTIVE_MS : POLL_IDLE_MS);
};

onMounted(async () => {
    await Promise.allSettled([loadOrders(), loadBalance()]);
    schedule();
});
onBeforeUnmount(() => {
    unmounted = true;
    clearTimeout(timer);
});
</script>

<style scoped lang="scss">
$line:  #EFE2BC;
$ink:   #2B1D14;
$sub:   #6B5B4E;
$yellow:#F6C445;
$up:    #C8282A;
$down:  #1F5BD1;

#manual-buy {
    min-height: 100vh;
    background: #fff;
    color: $ink;
    text-align: left;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 720px;
    margin: 0 auto;
    padding: 8px 16px 40px;
}

.row-label { flex-shrink: 0; width: 76px; font-size: 14px; color: $sub; }

.stock-row {
    display: flex;
    align-items: center;
    width: 100%;
    min-height: 56px;
    padding: 0;
    border: 0;
    border-bottom: 1px solid $line;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;

    .stock-value { flex: 1; min-width: 0; font-size: 15px; font-weight: 700;
        em { margin-left: 4px; font-style: normal; font-size: 12px; font-weight: 400; color: $sub; } }
    .stock-empty { flex: 1; font-size: 15px; color: $sub; }
    .chevron { font-size: 20px; color: $sub; }
}

.field {
    display: flex;
    align-items: center;
    min-height: 56px;
    border-bottom: 1px solid $line;
}

.segment {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    background: #F3E8C6;
    border-radius: 12px;
    padding: 3px;

    .seg-btn {
        min-height: 38px;
        border: 0;
        border-radius: 9px;
        background: transparent;
        color: $sub;
        font: inherit;
        font-size: 14px;
        cursor: pointer;
        &.on { background: #fff; color: $ink; font-weight: 700; }
    }
}

.input-unit {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
    font-size: 15px;

    input {
        flex: 1;
        min-width: 0;
        height: 40px;
        border: 0;
        outline: none;
        background: transparent;
        color: $ink;
        font: inherit;
        font-weight: 700;
        text-align: right;
    }
}

.field-error { margin: 6px 0 0; font-size: 13px; color: $up; }

.summary {
    margin: 12px 0 0;
    div { display: flex; justify-content: space-between; padding: 4px 0; font-size: 14px; }
    dt { color: $sub; }
    dd { margin: 0; font-weight: 700; &.over { color: $up; } }
}

.note { margin: 8px 0 0; font-size: 13px; line-height: 1.5; color: $sub; }

.btn-buy {
    width: 100%;
    min-height: 48px;
    margin-top: 16px;
    border: 0;
    border-radius: 12px;
    background: $yellow;
    color: #3A200F;
    font: inherit;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    &:disabled { opacity: .45; cursor: default; }
}

.orders {
    margin-top: 32px;
    h2 { margin: 0; padding-bottom: 8px; font-size: 16px; font-weight: 700; border-bottom: 1px solid $line; }
    ul { list-style: none; margin: 0; padding: 0; }
}

.empty { padding: 32px 0; text-align: center; font-size: 14px; color: $sub; &.error { color: $up; } }

.order { padding: 12px 0; border-bottom: 1px solid $line; }
.order-top { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.order-name { min-width: 0; font-size: 15px; font-weight: 700; }
.order-state {
    flex-shrink: 0;
    font-size: 13px;
    font-weight: 700;
    &.done { color: $up; }
    &.active { color: $down; }
    &.bad { color: $up; }
    &.muted { color: $sub; font-weight: 500; }
}
.order-meta { margin-top: 4px; font-size: 13px; color: $sub; }
.order-reason { margin-top: 4px; font-size: 13px; line-height: 1.5; color: $ink; }
.btn-cancel {
    min-height: 36px;
    margin-top: 8px;
    padding: 0 12px;
    border: 1px solid $line;
    border-radius: 8px;
    background: #fff;
    color: $ink;
    font: inherit;
    font-size: 13px;
    cursor: pointer;
    &:disabled { opacity: .5; cursor: default; }
}
</style>
