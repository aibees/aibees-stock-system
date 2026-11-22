<template>
    <svg class="hex" :width="size" :height="Math.round(size * 14 / 13)" viewBox="0 0 13 14" aria-hidden="true">
        <path d="M6.5 0.6 12.2 3.85v6.3L6.5 13.4 0.8 10.15v-6.3Z" :fill="fill" />
    </svg>
</template>

<script setup>
/** 육각형 — 구조 요소로만 쓴다(진행 표시 13px · 섹션 마커 15px · 결과 마크 38px). 캐릭터·일러스트로 넓히지 않는다(명세 2장). */
defineProps({
    size: { type: Number, default: 13 },
    fill: { type: String, default: 'currentColor' },
});
</script>

<style scoped>
.hex { display: inline-block; flex: none; vertical-align: middle; }
</style>
