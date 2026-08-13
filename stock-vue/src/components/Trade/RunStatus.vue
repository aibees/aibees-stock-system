<template>
    <div id="auto-trade-status">
        <Headers :prop_title="'운용 현황'" />

        <div class="contents">

            <!-- ── 요약 ── -->
            <section class="summary">
                <div class="sum-item">
                    <span class="sum-label">운용 방식</span>
                    <span class="sum-value">{{ state.active_mode ?? '-' }}</span>
                </div>
                <div class="sum-item">
                    <span class="sum-label">상태</span>
                    <span class="sum-value" :class="`st-${(state.run_state ?? '').toLowerCase()}`">{{ runStateLabel
                        }}</span>
                </div>
                <div class="sum-item">
                    <span class="sum-label">전환 예약</span>
                    <span class="sum-value">{{ state.pending_mode ?? '없음' }}</span>
                </div>
                <div class="sum-item">
                    <span class="sum-label">최근 체크</span>
                    <span class="sum-value small">{{ formatDateTime(state.last_tick_at) }}</span>
                </div>
            </section>

            <!-- ── 현재 포지션 ── -->
            <section class="card">
                <h4>현재 포지션</h4>
                <div v-if="!state.position" class="empty">보유 중인 종목이 없습니다.</div>
                <div v-else class="position">
                    <div class="pos-head">
                        <span class="code-chip">{{ state.position.stock_code }}</span>
                        <b>{{ state.position.stock_name }}</b>
                        <span class="pos-rate" :class="rateClass">{{ state.position.profit_pct ?? '-' }}</span>
                    </div>
                    <ul class="pos-grid">
                        <li><span>진입가</span><b>{{ formatNumber(state.position.entry_price) }}</b></li>
                        <li><span>보유수량</span><b>{{ formatNumber(state.position.qty) }}</b></li>
                        <li><span>손절가</span><b>{{ formatNumber(state.position.stop_price) }}</b></li>
                        <li><span>익절가</span><b>{{ formatNumber(state.position.target_price) }}</b></li>
                        <li><span>트레일링</span><b>{{ formatNumber(state.position.trail_line) }}</b></li>
                        <li><span>보유봉수</span><b>{{ state.position.bars_held ?? '-' }}</b></li>
                    </ul>
                    <p class="pos-note" v-if="state.position.sell_reason">{{ state.position.sell_reason }}</p>
                </div>
            </section>

            <!-- ── [MOCK] 데모 조작 ── -->
            <section class="card mock-card" v-if="USE_MOCK">
                <h4>MOCK 시뮬레이터</h4>
                <p class="mock-desc">
                    실제 worker 없이 흐름을 확인하는 버튼입니다. '매도 체결'을 누르면 포지션이 청산되고,
                    전환 예약이 걸려 있으면 그 모드로 자동 승계됩니다.
                </p>
                <div class="mock-actions">
                    <button class="btn-mock" @click="onSimulateSell" :disabled="isBusy || !state.position">
                        매도 체결 시뮬레이션
                    </button>
                    <button class="btn-mock ghost" @click="onResetPosition" :disabled="isBusy || !!state.position">
                        보유 상태로 되돌리기
                    </button>
                </div>
            </section>

            <!-- ── worker 메시지 ── -->
            <section class="card">
                <h4>worker 최근 판단</h4>
                <p class="worker-msg">{{ state.last_message || '기록 없음' }}</p>
            </section>

            <!-- ── 변경 이력 ── -->
            <section class="card">
                <h4>모드 변경 이력</h4>
                <ul class="timeline">
                    <li v-for="h in history" :key="h.log_id">
                        <span class="tl-dot" :class="`act-${(h.action_type || '').toLowerCase()}`"></span>
                        <div class="tl-body">
                            <div class="tl-top">
                                <b>{{ ACTION_LABEL[h.action_type] ?? h.action_type }}</b>
                                <span class="tl-time">{{ formatDateTime(h.created_at) }}</span>
                            </div>
                            <p class="tl-desc">
                                {{ h.from_mode ?? '-' }} → {{ h.to_mode ?? '-' }}
                                <span v-if="h.reason"> · {{ h.reason }}</span>
                                <span class="actor">[{{ h.actor }}]</span>
                            </p>
                        </div>
                    </li>
                    <li v-if="history.length === 0" class="empty">이력이 없습니다.</li>
                </ul>
            </section>
        </div>
    </div>
</template>

<script setup>
import {
    fetchState, fetchHistory, simulateSell, resetPosition,
    USE_MOCK, RUN_STATE_LABEL, formatNumber, formatDateTime,
} from '@scripts/useAutoTrade.js';

const ACTION_LABEL = {
    START: '운용 시작',
    STOP: '운용 정지',
    APPLY_NOW: '즉시 적용',
    RESERVED: '전환 예약',
    RESERVE_CANCEL: '예약 취소',
    COMMIT: '예약 전환 완료',
};

const state = reactive({
    active_mode: null, run_state: 'IDLE', pending_mode: null,
    last_tick_at: null, last_message: '', position: null,
});
const history = ref([]);
const isBusy = ref(false);

const load = async () => {
    const [st, hs] = await Promise.all([fetchState(), fetchHistory(30)]);
    if (st) Object.assign(state, st);
    history.value = hs;
};
onMounted(load);

/* ── [MOCK] 데모 조작 ── */
const onSimulateSell = async () => {
    isBusy.value = true;
    try {
        const res = await simulateSell();
        await load();
        if (res?.message) alert(res.message);
    } finally {
        isBusy.value = false;
    }
};

const onResetPosition = async () => {
    isBusy.value = true;
    try {
        await resetPosition();
        await load();
    } finally {
        isBusy.value = false;
    }
};

const runStateLabel = computed(() => RUN_STATE_LABEL[state.run_state] ?? state.run_state);
const rateClass = computed(() => {
    const v = parseFloat(String(state.position?.profit_pct ?? '0').replace('%', ''));
    return v > 0 ? 'up' : v < 0 ? 'down' : '';
});
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

#auto-trade-status {
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

.summary {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 14px;

    @media (max-width: 700px) {
        grid-template-columns: repeat(2, 1fr);
    }
}

.sum-item {
    background: $white;
    border: 1px solid $gray-100;
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;

    .sum-label {
        font-size: .74rem;
        color: $gray-500;
    }

    .sum-value {
        font-size: 1rem;
        font-weight: 700;

        &.small {
            font-size: .82rem;
            font-weight: 600;
        }

        &.st-holding {
            color: $green;
        }

        &.st-armed {
            color: $blue;
        }

        &.st-switch_pending {
            color: $amber;
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

.empty {
    font-size: .82rem;
    color: $gray-400;
    text-align: center;
    padding: 18px 0;
}

.position {
    .pos-head {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;

        b {
            font-size: .95rem;
        }
    }

    .code-chip {
        font-family: monospace;
        background: $gray-100;
        border-radius: 6px;
        padding: 2px 7px;
        font-size: .76rem;
    }

    .pos-rate {
        margin-left: auto;
        font-size: 1rem;
        font-weight: 800;

        &.up {
            color: $red;
        }

        &.down {
            color: $blue;
        }
    }

    .pos-grid {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;

        @media (max-width: 700px) {
            grid-template-columns: repeat(2, 1fr);
        }

        li {
            background: $gray-50;
            border-radius: 8px;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 4px;

            span {
                font-size: .72rem;
                color: $gray-500;
            }

            b {
                font-size: .88rem;
            }
        }
    }

    .pos-note {
        margin: 12px 0 0;
        font-size: .78rem;
        color: $gray-500;
    }
}

/* ── [MOCK] 시뮬레이터 ── */
.mock-card {
    border-color: #ffe08a;
    background: #fffdf5;

    .mock-desc {
        margin: 0 0 12px;
        font-size: .78rem;
        color: $gray-500;
        line-height: 1.5;
    }

    .mock-actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }

    .btn-mock {
        height: 36px;
        padding: 0 16px;
        border: 0;
        border-radius: 8px;
        background: $amber;
        color: #fff;
        font-size: .8rem;
        font-weight: 700;
        cursor: pointer;

        &.ghost {
            background: transparent;
            border: 1px solid $amber;
            color: $amber;
        }

        &:disabled {
            opacity: .45;
            cursor: not-allowed;
        }
    }
}

.worker-msg {
    margin: 0;
    font-size: .84rem;
    color: $gray-900;
    background: $gray-50;
    border-radius: 8px;
    padding: 12px;
    line-height: 1.5;
}

.timeline {
    list-style: none;
    margin: 0;
    padding: 0;

    li {
        display: flex;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px dashed $gray-100;

        &:last-child {
            border-bottom: 0;
        }
    }

    .tl-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: $gray-200;
        margin-top: 6px;
        flex: 0 0 auto;

        &.act-commit {
            background: $green;
        }

        &.act-reserved {
            background: $amber;
        }

        &.act-apply_now {
            background: $blue;
        }

        &.act-stop {
            background: $red;
        }
    }

    .tl-body {
        flex: 1;
    }

    .tl-top {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        font-size: .84rem;
    }

    .tl-time {
        font-size: .74rem;
        color: $gray-400;
    }

    .tl-desc {
        margin: 3px 0 0;
        font-size: .78rem;
        color: $gray-500;

        .actor {
            margin-left: 6px;
            color: $gray-400;
        }
    }
}
</style>
