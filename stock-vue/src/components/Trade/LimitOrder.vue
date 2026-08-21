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
                    </p>
                </div>
            </section>

            <!-- ── 상태 ── -->
            <section class="steps" v-if="form.stock_code">
                <div class="step" :class="{ on: record.state === 'ARMED', done: record.state === 'DONE' }">
                    <span class="dot"></span>
                    <span class="label">{{ stateLabel }}</span>
                </div>
            </section>

            <!-- ── 입력 폼 ── -->
            <section class="card">
                <div class="form-grid">

                    <div class="form-field full">
                        <label>대상 종목 <span class="req">*</span></label>
                        <div class="stock-picker">
                            <input readonly :value="stockDisplay" placeholder="보유 중인 종목을 선택하세요" />
                            <button class="btn-pick" @click="picker = true" :disabled="isLocked">종목 선택</button>
                        </div>
                        <p class="lock-hint">worker 가 직접 매수해 보유 중인 종목에만 적용됩니다. 미보유 종목은 등록해도 감시되지 않습니다.</p>
                    </div>

                    <div class="form-field">
                        <label>지정 매도가 <span class="req">*</span></label>
                        <input type="number" v-model.number="form.sell_price" :disabled="isLocked" placeholder="0" />
                    </div>

                    <div class="form-field">
                        <label>매도 비율</label>
                        <div class="inline">
                            <input type="number" v-model.number="form.qty_ratio_pct" :disabled="isLocked" min="1" max="100" placeholder="100" />
                            <span class="inline-text">% (보유수량 기준, 비우면 전량)</span>
                        </div>
                    </div>

                    <div class="form-field">
                        <label>감시 사용</label>
                        <div class="inline">
                            <button :class="['toggle-btn', form.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                @click="form.enabled_flag = form.enabled_flag === 'Y' ? 'N' : 'Y'">
                                <span class="toggle-knob"></span>
                            </button>
                            <span class="inline-text">
                                {{ form.enabled_flag === 'Y' ? '감시 중' : '꺼짐 — 등록은 유지되지만 감시하지 않습니다' }}
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
            <section class="card" v-if="record.state && record.state !== 'ARMED'">
                <h4>체결 기록</h4>
                <ul class="record-list">
                    <li><span>상태</span><b>{{ stateLabel }}</b></li>
                    <li><span>매도 체결</span><b>{{ formatNumber(record.filled_price) }} · {{
                        formatDateTime(record.filled_at) }}</b></li>
                </ul>
            </section>

            <div class="action-bar">
                <button class="btn-delete" @click="onDelete" :disabled="isBusy || !hasSaved">취소</button>
                <button class="btn-save" @click="onSave" :disabled="isBusy">저장</button>
            </div>
        </div>

        <StockPickerModal :visible="picker" title="대상 종목 선택" @pick="onPick" @close="picker = false" />
    </div>
</template>

<script setup>
import StockPickerModal from './StockPickerModal.vue';
import {
    fetchManualSell, saveManualSell, removeManualSell,
    MANUAL_SELL_STATE_LABEL, formatNumber, formatDateTime,
} from '@scripts/useAutoTrade.js';

const isBusy = ref(false);
const hasSaved = ref(false);
const picker = ref(false);

const defaultForm = () => ({
    stock_code: '', stock_name: '',
    sell_price: null, qty_ratio_pct: 100,
    enabled_flag: 'Y', memo: '',
});
const form = reactive(defaultForm());
const record = reactive({ state: 'ARMED', filled_price: null, filled_at: null });

const load = async () => {
    const row = await fetchManualSell();
    if (row) {
        hasSaved.value = true;
        Object.assign(form, {
            ...defaultForm(),
            stock_code: row.stock_code, stock_name: row.stock_name,
            sell_price: row.sell_price,
            qty_ratio_pct: row.qty_ratio != null ? Math.round(Number(row.qty_ratio) * 100) : 100,
            enabled_flag: row.enabled_flag ?? 'Y',
            memo: row.memo ?? '',
        });
        Object.assign(record, {
            state: row.state ?? 'ARMED',
            filled_price: row.filled_price,
            filled_at: row.filled_at,
        });
    }
};
onMounted(load);

const stockDisplay = computed(() =>
    form.stock_code ? `${form.stock_name} (${form.stock_code})` : ''
);
// 이미 체결(DONE)됐거나 취소(CANCELLED)된 건은 그대로 새로 등록해야 하므로
// 종목 선택을 다시 열어준다 — 잠그는 건 감시(ARMED) 중일 때만.
const isLocked = computed(() => false);
const stateLabel = computed(() => MANUAL_SELL_STATE_LABEL[record.state] ?? record.state);

const onPick = ({ stock_code, stock_name }) => {
    form.stock_code = stock_code;
    form.stock_name = stock_name;
    picker.value = false;
};

const validate = () => {
    if (!form.stock_code) return '종목을 선택해 주세요.';
    if (!form.sell_price || Number(form.sell_price) <= 0) return '지정 매도가를 입력해 주세요.';
    const pct = form.qty_ratio_pct;
    if (pct !== null && pct !== '' && (Number(pct) <= 0 || Number(pct) > 100)) return '매도 비율은 1~100 사이여야 합니다.';
    return null;
};

const onSave = async () => {
    const err = validate();
    if (err) { alert(err); return; }
    isBusy.value = true;
    try {
        const pct = (form.qty_ratio_pct === null || form.qty_ratio_pct === '') ? 100 : Number(form.qty_ratio_pct);
        await saveManualSell({
            stock_code: form.stock_code,
            stock_name: form.stock_name,
            sell_price: Number(form.sell_price),
            qty_ratio: pct / 100,
            enabled_flag: form.enabled_flag,
            memo: form.memo,
        });
        alert('저장되었습니다. 지금 운용 방식과 무관하게 이 종목은 지정가로만 감시됩니다.');
        await load();
    } finally {
        isBusy.value = false;
    }
};

const onDelete = async () => {
    if (!confirm('매도 수기 등록을 취소할까요? 이후 이 종목은 다시 활성 운용 방식의 자동 매도 rule을 따릅니다.')) return;
    isBusy.value = true;
    try {
        await removeManualSell();
        Object.assign(form, defaultForm());
        Object.assign(record, { state: 'ARMED', filled_price: null, filled_at: null });
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
