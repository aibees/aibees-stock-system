<template>
    <div id="auto-trade-limit">
        <Headers :prop_title="'지정가 예약'" />

        <div class="contents">

            <section class="head-desc">
                <div>
                    <h2>지정가 예약</h2>
                    <p class="sub-text">종목 1개에 매수가·매도가를 지정하면 worker 가 감시하다가 도달 시 자동 체결합니다.</p>
                </div>
                <span v-if="!isModeActive" class="mode-warn">
                    현재 운용 방식이 <b>지정가 감시</b>가 아닙니다. 등록해도 감시되지 않습니다.
                </span>
            </section>

            <!-- ── 진행 상태 스텝 ── -->
            <section class="steps" v-if="form.stock_code">
                <div v-for="s in STEPS" :key="s.key" :class="['step', { done: stepIndex > s.idx, on: stepIndex === s.idx }]">
                    <span class="dot"></span>
                    <span class="label">{{ s.label }}</span>
                </div>
            </section>

            <!-- ── 입력 폼 ── -->
            <section class="card">
                <div class="form-grid">

                    <div class="form-field full">
                        <label>감시 종목 <span class="req">*</span></label>
                        <div class="stock-picker">
                            <input readonly :value="stockDisplay" placeholder="종목을 선택하세요" />
                            <button class="btn-pick" @click="picker = true" :disabled="isStockLocked">종목 선택</button>
                        </div>
                        <p v-if="isStockLocked" class="lock-hint">매수 체결 상태에서는 종목·매수가를 변경할 수 없습니다.</p>
                    </div>

                    <div class="form-field">
                        <label>지정 매수가 <span class="req">*</span></label>
                        <input type="number" v-model.number="form.buy_price" :disabled="isStockLocked" placeholder="0" />
                    </div>

                    <div class="form-field">
                        <label>지정 매도가 <span class="req">*</span></label>
                        <input type="number" v-model.number="form.sell_price" placeholder="0" />
                    </div>

                    <div class="form-field">
                        <label>매수 수량</label>
                        <input type="number" v-model.number="form.qty" :disabled="isStockLocked"
                            placeholder="비우면 예수금 전량" />
                    </div>

                    <div class="form-field">
                        <label>목표 수익률</label>
                        <div class="readonly-box" :class="{ minus: expectedRate < 0 }">
                            {{ expectedRateText }}
                        </div>
                    </div>

                    <div class="form-field">
                        <label>손절 병행</label>
                        <div class="inline">
                            <button :class="['toggle-btn', form.use_stop_loss === 'Y' ? 'active' : 'inactive']"
                                @click="form.use_stop_loss = form.use_stop_loss === 'Y' ? 'N' : 'Y'">
                                <span class="toggle-knob"></span>
                            </button>
                            <input type="number" v-model.number="form.stop_price" :disabled="form.use_stop_loss !== 'Y'"
                                placeholder="손절가" />
                        </div>
                    </div>

                    <div class="form-field">
                        <label>매도 후 반복 감시</label>
                        <div class="inline">
                            <button :class="['toggle-btn', form.loop_flag === 'Y' ? 'active' : 'inactive']"
                                @click="form.loop_flag = form.loop_flag === 'Y' ? 'N' : 'Y'">
                                <span class="toggle-knob"></span>
                            </button>
                            <span class="inline-text">
                                {{ form.loop_flag === 'Y' ? '매도 완료 후 다시 매수가를 감시합니다' : '1회 체결 후 종료' }}
                            </span>
                        </div>
                    </div>

                    <div class="form-field full">
                        <label>메모</label>
                        <input type="text" v-model="form.memo" maxlength="255" placeholder="선택 입력" />
                    </div>
                </div>
            </section>

            <!-- ── 체결 기록 ── -->
            <section class="card" v-if="record.order_state && record.order_state !== 'WAIT_BUY'">
                <h4>체결 기록</h4>
                <ul class="record-list">
                    <li><span>상태</span><b>{{ orderStateLabel }}</b></li>
                    <li><span>매수 체결</span><b>{{ formatNumber(record.filled_buy_price) }} · {{
                        formatDateTime(record.filled_buy_at) }}</b></li>
                    <li><span>매도 체결</span><b>{{ formatNumber(record.filled_sell_price) }} · {{
                        formatDateTime(record.filled_sell_at) }}</b></li>
                    <li><span>반복 횟수</span><b>{{ record.loop_count ?? 0 }}회</b></li>
                </ul>
            </section>

            <div class="action-bar">
                <button class="btn-delete" @click="onDelete" :disabled="isBusy || !hasSaved">삭제</button>
                <button class="btn-save" @click="onSave" :disabled="isBusy">저장</button>
            </div>
        </div>

        <StockPickerModal :visible="picker" title="감시 종목 선택" @pick="onPick" @close="picker = false" />
    </div>
</template>

<script setup>
import StockPickerModal from './StockPickerModal.vue';
import {
    fetchLimitOrder, saveLimitOrder, removeLimitOrder, fetchState,
    ORDER_STATE_LABEL, formatNumber, formatDateTime,
} from '@scripts/useAutoTrade.js';

const STEPS = [
    { key: 'WAIT_BUY', idx: 0, label: '매수가 감시' },
    { key: 'BOUGHT', idx: 1, label: '매수 체결' },
    { key: 'DONE', idx: 2, label: '매도 완료' },
];

const isBusy = ref(false);
const hasSaved = ref(false);
const picker = ref(false);
const isModeActive = ref(true);

const defaultForm = () => ({
    stock_code: '', stock_name: '',
    buy_price: null, sell_price: null, qty: null,
    use_stop_loss: 'N', stop_price: null,
    loop_flag: 'N', enabled_flag: 'Y', memo: '',
});
const form = reactive(defaultForm());
const record = reactive({ order_state: 'WAIT_BUY', filled_buy_price: null, filled_buy_at: null, filled_sell_price: null, filled_sell_at: null, loop_count: 0 });

const load = async () => {
    const [row, st] = await Promise.all([fetchLimitOrder(), fetchState()]);
    isModeActive.value = (st?.active_mode === 'M3');
    if (row) {
        hasSaved.value = true;
        Object.assign(form, { ...defaultForm(), ...row });
        Object.assign(record, {
            order_state: row.order_state ?? 'WAIT_BUY',
            filled_buy_price: row.filled_buy_price,
            filled_buy_at: row.filled_buy_at,
            filled_sell_price: row.filled_sell_price,
            filled_sell_at: row.filled_sell_at,
            loop_count: row.loop_count ?? 0,
        });
    }
};
onMounted(load);

const stockDisplay = computed(() =>
    form.stock_code ? `${form.stock_name} (${form.stock_code})` : ''
);
const isStockLocked = computed(() => record.order_state === 'BOUGHT');
const orderStateLabel = computed(() => ORDER_STATE_LABEL[record.order_state] ?? record.order_state);
const stepIndex = computed(() => ({ WAIT_BUY: 0, BOUGHT: 1, DONE: 2, STOPPED: 2 })[record.order_state] ?? 0);

const expectedRate = computed(() => {
    const b = Number(form.buy_price), s = Number(form.sell_price);
    if (!b || !s) return 0;
    return ((s - b) / b) * 100;
});
const expectedRateText = computed(() =>
    (!form.buy_price || !form.sell_price) ? '-' : `${expectedRate.value >= 0 ? '+' : ''}${expectedRate.value.toFixed(2)}%`
);

const onPick = ({ stock_code, stock_name }) => {
    form.stock_code = stock_code;
    form.stock_name = stock_name;
    picker.value = false;
};

const validate = () => {
    if (!form.stock_code) return '종목을 선택해 주세요.';
    if (!form.buy_price || Number(form.buy_price) <= 0) return '지정 매수가를 입력해 주세요.';
    if (!form.sell_price || Number(form.sell_price) <= 0) return '지정 매도가를 입력해 주세요.';
    if (Number(form.buy_price) >= Number(form.sell_price)) return '매도가는 매수가보다 커야 합니다.';
    if (form.use_stop_loss === 'Y') {
        if (!form.stop_price || Number(form.stop_price) <= 0) return '손절가를 입력해 주세요.';
        if (Number(form.stop_price) >= Number(form.buy_price)) return '손절가는 매수가보다 낮아야 합니다.';
    }
    if (form.qty !== null && form.qty !== '' && Number(form.qty) <= 0) return '수량은 1 이상이어야 합니다.';
    return null;
};

const onSave = async () => {
    const err = validate();
    if (err) { alert(err); return; }
    isBusy.value = true;
    try {
        await saveLimitOrder({
            stock_code: form.stock_code,
            stock_name: form.stock_name,
            buy_price: Number(form.buy_price),
            sell_price: Number(form.sell_price),
            qty: (form.qty === null || form.qty === '') ? null : Number(form.qty),
            use_stop_loss: form.use_stop_loss,
            stop_price: form.use_stop_loss === 'Y' ? Number(form.stop_price) : null,
            loop_flag: form.loop_flag,
            enabled_flag: form.enabled_flag,
            memo: form.memo,
        });
        alert('저장되었습니다.');
        await load();
    } finally {
        isBusy.value = false;
    }
};

const onDelete = async () => {
    if (record.order_state === 'BOUGHT') {
        alert('매수 체결 상태에서는 삭제할 수 없습니다. 매도 완료 후 삭제해 주세요.');
        return;
    }
    if (!confirm('지정가 예약을 삭제할까요?')) return;
    isBusy.value = true;
    try {
        await removeLimitOrder();
        Object.assign(form, defaultForm());
        Object.assign(record, { order_state: 'WAIT_BUY', filled_buy_price: null, filled_buy_at: null, filled_sell_price: null, filled_sell_at: null, loop_count: 0 });
        hasSaved.value = false;
    } finally {
        isBusy.value = false;
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
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 12px;
    margin-bottom: 18px;

    h2 {
        margin: 0;
        font-size: 1.3rem;
        font-weight: 700;
    }

    .sub-text {
        margin: 4px 0 0;
        font-size: .82rem;
        color: $gray-500;
    }

    .mode-warn {
        font-size: .76rem;
        color: $amber;
        background: #fff8e1;
        border: 1px solid #ffe08a;
        border-radius: 8px;
        padding: 7px 10px;
    }

    @media (max-width: 700px) {
        flex-direction: column;
        align-items: flex-start;
    }
}

/* ── 스텝 ── */
.steps {
    display: flex;
    align-items: center;
    gap: 26px;
    background: $white;
    border: 1px solid $gray-100;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 14px;

    .step {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: .8rem;
        color: $gray-400;

        .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: $gray-200;
        }

        &.on {
            color: $blue;
            font-weight: 700;

            .dot {
                background: $blue;
                box-shadow: 0 0 0 4px rgba(25, 113, 194, .15);
            }
        }

        &.done {
            color: $green;

            .dot {
                background: $green;
            }
        }
    }
}

.card {
    background: $white;
    border: 1px solid $gray-100;
    border-radius: 12px;
    padding: 18px;
    margin-bottom: 14px;

    h4 {
        margin: 0 0 12px;
        font-size: .9rem;
        font-weight: 700;
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
        color: $red;
    }

    input {
        height: 38px;
        border: 1px solid $gray-200;
        border-radius: 8px;
        padding: 0 10px;
        font-size: .85rem;
        background: $white;

        &:disabled {
            background: $gray-50;
            color: $gray-400;
        }
    }

    .lock-hint {
        margin: 0;
        font-size: .74rem;
        color: $amber;
    }

    .readonly-box {
        height: 38px;
        display: flex;
        align-items: center;
        padding: 0 10px;
        border: 1px dashed $gray-200;
        border-radius: 8px;
        font-size: .88rem;
        font-weight: 700;
        color: $red;
        background: $gray-50;

        &.minus {
            color: $blue;
        }
    }

    .inline {
        display: flex;
        align-items: center;
        gap: 10px;

        input {
            flex: 1;
        }
    }

    .inline-text {
        font-size: .78rem;
        color: $gray-500;
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
        border: 1px solid $blue;
        color: $blue;
        background: transparent;
        border-radius: 8px;
        font-size: .8rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;

        &:disabled {
            opacity: .45;
            cursor: not-allowed;
        }
    }
}

.toggle-btn {
    width: 46px;
    height: 26px;
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
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #fff;
        transition: transform .18s;
    }

    &.active .toggle-knob {
        transform: translateX(20px);
    }
}

.record-list {
    list-style: none;
    margin: 0;
    padding: 0;

    li {
        display: flex;
        justify-content: space-between;
        padding: 9px 0;
        border-bottom: 1px dashed $gray-100;
        font-size: .82rem;

        &:last-child {
            border-bottom: 0;
        }

        span {
            color: $gray-500;
        }
    }
}

.action-bar {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 8px;
}

.btn-save,
.btn-delete {
    height: 42px;
    padding: 0 24px;
    border-radius: 10px;
    font-size: .88rem;
    font-weight: 700;
    cursor: pointer;

    &:disabled {
        opacity: .5;
        cursor: not-allowed;
    }
}

.btn-save {
    border: 0;
    background: $navy;
    color: #fff;
}

.btn-delete {
    border: 1px solid $red;
    background: transparent;
    color: $red;
}
</style>
