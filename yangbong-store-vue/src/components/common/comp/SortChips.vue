<template>
    <div ref="rowRef" class="sort-chips" role="tablist" :aria-label="label">
        <button v-for="o in options" :key="o.key" type="button" role="tab" class="chip"
            :class="{ on: o.key === modelValue }" :aria-selected="o.key === modelValue ? 'true' : 'false'"
            :data-key="o.key" @click="select(o.key)">
            {{ o.label }}
        </button>
    </div>
</template>

<script setup>
/**
 * 가로로 넘기는 칩 선택(정렬 기준 등). 사용자 요청으로 쓰는 pill 형태 — 다른 곳에 임의로 쓰지 않는다.
 * v-model: 선택된 key. 선택이 바뀌면 'change'(key) 도 보낸다(정렬 방향 초기화 같은 후처리용).
 * 선택된 칩이 화면 밖에 있으면 보이는 곳까지 가로로 스크롤한다.
 */
const props = defineProps({
    options: { type: Array, required: true },   // [{ key, label }]
    modelValue: { type: String, default: '' },
    label: { type: String, default: '정렬 기준' },
});
const emit = defineEmits(['update:modelValue', 'change']);

const rowRef = ref(null);

const scrollToActive = (smooth = true) => {
    const el = rowRef.value?.querySelector(`[data-key="${props.modelValue}"]`);
    el?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'nearest', inline: 'nearest' });
};

const select = (key) => {
    if (key === props.modelValue) return;
    emit('update:modelValue', key);
    emit('change', key);
};

watch(() => props.modelValue, () => nextTick(() => scrollToActive(true)));
onMounted(() => scrollToActive(false));
</script>

<style scoped lang="scss">
// 2026-11-17 화이트 톤 개편: 선택된 칩만 연회색 알약, 나머지는 바탕 없는 회색 글자(2단계 필터)
.sort-chips {
    display: flex;
    gap: 4px;
    // 본문 좌우 여백까지 끝까지 넘겨 보이게
    margin: 0 -16px 14px;
    padding: 2px 16px;
    overflow-x: auto;
    scroll-padding: 0 16px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    &::-webkit-scrollbar { display: none; }
}

.chip {
    flex-shrink: 0;
    min-height: 36px;
    padding: 0 12px;
    border: 0;
    border-radius: 999px;
    background: transparent;
    color: #8B95A1;
    font-size: 14px;
    font-weight: 500;
    font-family: inherit;
    white-space: nowrap;
    cursor: pointer;
    transition: background .15s, color .15s;

    &.on { background: #F2F4F6; color: #191F28; font-weight: 600; }
    &:focus-visible { outline: 2px solid #191F28; outline-offset: 2px; }
}
</style>
