<template>
    <button type="button" class="watch-star" :class="{ on: saved }" :aria-pressed="saved ? 'true' : 'false'"
        :aria-label="`${name} 관심 종목 ${saved ? '빼기' : '담기'}`" @click.stop="toggle">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6L12 16.7 6.6 19.6l1.1-6-4.5-4.2 6.1-.8z"></path></svg>
    </button>
</template>

<script setup>
import { useWatchlistStore } from '@scripts/stores/watchlist-store.js';

const props = defineProps({
    code: { type: String, required: true },
    name: { type: String, required: true },
    close: { type: [Number, String], default: null },
    rate: { type: [Number, String], default: null },
});
const emit = defineEmits(['added', 'removed']);
const watch = useWatchlistStore();
const saved = computed(() => watch.has(props.code));
const toggle = () => emit(watch.toggle(props) ? 'added' : 'removed', props.code);
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.watch-star {
    width: 34px;
    height: 34px;
    padding: 0;
    border: 0;
    background: transparent;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    svg { width: 21px; height: 21px; fill: none; stroke: $sub-2; stroke-width: 1.8; stroke-linejoin: round; }
    &.on svg { fill: $honey-500; stroke: $amber-700; }
}
</style>
