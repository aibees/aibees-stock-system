<template>
    <Teleport to="body">
        <Transition name="fade">
            <div v-if="visible" class="picker-overlay" @click.self="close">
                <div class="picker-panel" v-draggable>
                    <div class="picker-header">
                        <h3>{{ title }}</h3>
                        <button class="btn-close" @click="close">✕</button>
                    </div>

                    <div class="picker-search">
                        <input ref="inputRef" v-model="keyword" type="text" placeholder="종목명 또는 코드 입력"
                            @keyup.enter="runSearch" />
                        <button class="btn-search" @click="runSearch" :disabled="loading">
                            {{ loading ? '검색중' : '검색' }}
                        </button>
                    </div>

                    <ul class="picker-list">
                        <li v-for="s in list" :key="s.stock_code" @click="pick(s)">
                            <span class="code-chip">{{ s.stock_code }}</span>
                            <span class="name">{{ s.stock_name }}</span>
                            <span class="type">{{ s.type }}</span>
                        </li>
                        <li v-if="searched && list.length === 0" class="empty">검색 결과가 없습니다.</li>
                        <li v-if="!searched" class="empty">검색어를 입력해 주세요.</li>
                    </ul>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<script setup>
import { searchStocks } from '@scripts/useAutoTrade.js';

const props = defineProps({
    visible: { type: Boolean, default: false },
    title: { type: String, default: '종목 선택' },
});
const emit = defineEmits(['pick', 'close']);

const keyword = ref('');
const list = ref([]);
const loading = ref(false);
const searched = ref(false);
const inputRef = ref(null);

watch(() => props.visible, (v) => {
    if (v) {
        keyword.value = '';
        list.value = [];
        searched.value = false;
        nextTick(() => inputRef.value?.focus());
    }
});

const runSearch = async () => {
    const kw = keyword.value.trim();
    if (!kw) { alert('검색어를 입력해 주세요.'); return; }
    loading.value = true;
    try {
        list.value = await searchStocks(kw);
        searched.value = true;
    } finally {
        loading.value = false;
    }
};

const pick = (s) => emit('pick', { stock_code: s.stock_code, stock_name: s.stock_name });
const close = () => emit('close');
</script>

<style scoped lang="scss">
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-500: #6b6b6b;
$gray-900: #111111;
$blue: #1971c2;

.picker-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1200;
}

.picker-panel {
    width: min(460px, 92vw);
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 18px 48px rgba(0, 0, 0, .22);
}

.picker-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    border-bottom: 1px solid $gray-100;

    h3 {
        margin: 0;
        font-size: .98rem;
        font-weight: 700;
        color: $gray-900;
    }

    .btn-close {
        border: 0;
        background: none;
        font-size: 1rem;
        cursor: pointer;
        color: $gray-500;
    }
}

.picker-search {
    display: flex;
    gap: 8px;
    padding: 14px 16px;

    input {
        flex: 1;
        height: 36px;
        border: 1px solid $gray-200;
        border-radius: 8px;
        padding: 0 10px;
        font-size: .86rem;
    }

    .btn-search {
        height: 36px;
        padding: 0 16px;
        border: 0;
        border-radius: 8px;
        background: $blue;
        color: #fff;
        font-size: .84rem;
        font-weight: 600;
        cursor: pointer;
    }
}

.picker-list {
    list-style: none;
    margin: 0;
    padding: 0 8px 12px;
    max-height: 46vh;
    overflow-y: auto;

    li {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: 8px;
        cursor: pointer;
        font-size: .86rem;

        &:hover {
            background: #f1f5f9;
        }

        &.empty {
            justify-content: center;
            color: $gray-500;
            cursor: default;
            font-size: .82rem;

            &:hover {
                background: none;
            }
        }
    }

    .code-chip {
        font-family: monospace;
        background: $gray-100;
        border-radius: 6px;
        padding: 2px 6px;
        font-size: .78rem;
    }

    .name {
        flex: 1;
        font-weight: 600;
        color: $gray-900;
    }

    .type {
        font-size: .74rem;
        color: $gray-500;
    }
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity .15s;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>
