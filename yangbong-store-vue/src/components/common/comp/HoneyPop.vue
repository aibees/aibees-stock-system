<template>
    <!-- 꿀을 받는 순간: 꿀단지가 톡 튀어나오고 위에 '꿀 +30'. 움직임 줄이기 설정이면 알림만. App.vue 에 한 번 둔다 -->
    <div v-if="shown" class="honey-pop" aria-live="polite">
        <p class="hp-toast"><img src="/img/emoji/honey.png" alt="" />꿀 +{{ shown.amount }}</p>
        <div v-if="!reduce" :key="shown.key" class="hp-jar" aria-hidden="true"><img src="/img/emoji/honey.png" alt="" /></div>
    </div>
</template>

<script setup>
import { useHoneyStore } from '@scripts/stores/honey-store.js';

const honey = useHoneyStore();
const shown = ref(null);
let timer = null;
const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

watch(() => honey.pop, (p) => {
    if (!p) return;
    shown.value = p;
    clearTimeout(timer);
    timer = setTimeout(() => { shown.value = null; }, 1700);
});
onBeforeUnmount(() => clearTimeout(timer));
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.honey-pop { position: fixed; inset: 0; z-index: 2000; pointer-events: none; }
.hp-toast {
    position: absolute; left: 50%; top: calc(70px + env(safe-area-inset-top, 0px)); transform: translateX(-50%);
    margin: 0; padding: 10px 16px 10px 12px; border-radius: 22px; background: #fff; box-shadow: 0 10px 26px rgba(0, 0, 0, .16);
    display: flex; align-items: center; gap: 6px; font-family: $font-body; font-size: 15px; font-weight: 800; color: $honey-ink;
    animation: hp-drop .3s ease-out;
    img { width: 22px; height: 22px; }
}
.hp-jar {
    position: absolute; left: 50%; top: 38%; width: 120px; height: 120px; margin: -60px 0 0 -60px;
    border-radius: 50%; background: #FFF3C4; box-shadow: 0 0 0 14px rgba(255, 227, 156, .55);
    display: flex; align-items: center; justify-content: center;
    animation: hp-jar 1.1s cubic-bezier(.2, .8, .3, 1) forwards;
    img { width: 84px; height: 84px; }
}
@keyframes hp-drop { from { opacity: 0; transform: translate(-50%, -8px); } to { opacity: 1; transform: translate(-50%, 0); } }
@keyframes hp-jar {
    0% { opacity: 0; transform: scale(.4); }
    30% { opacity: 1; transform: scale(1.08); }
    55% { transform: scale(1); }
    80% { opacity: 1; transform: translateY(0) scale(1); }
    100% { opacity: 0; transform: translateY(-40vh) scale(.3); }
}
</style>
