<template>
    <template v-if="visible">
        <aside class="ad-side left" :style="{ top: top + 'px' }"><AdSlot placement="side" /></aside>
        <aside class="ad-side right" :style="{ top: top + 'px' }"><AdSlot placement="side" /></aside>
    </template>
</template>

<script setup>
import AdSlot from './AdSlot.vue';
import { Capacitor } from '@capacitor/core';
import { SIDE_BANNER_MIN_WIDTH } from '@scripts/adConfig.js';
import { useShowAds, useMediaQuery } from '@scripts/useAds.js';

/**
 * 화면 양옆 광고(데스크톱). 비로그인 포함, AD_FREE 가 없을 때만, 콘텐츠와 겹치지 않을
 * 만큼 넓은 화면에서만 보인다. 앱은 제외(모바일 배너를 쓴다).
 */
const route   = useRoute();
const showAds = useShowAds();
const wide    = useMediaQuery(`(min-width: ${SIDE_BANNER_MIN_WIDTH}px)`);

const visible = computed(() => showAds.value && wide.value && !Capacitor.isNativePlatform());

/* ── 세로 위치: 헤더 아래에서 시작 ──
 * 상단 내비(#comm-lnb-web)는 sticky 로 항상 보이고, 그 아래 페이지 헤더(.header)는
 * 일반 흐름이라 스크롤하면 위로 사라진다. 고정 top 값으로는 헤더 높이가 바뀌거나 스크롤할 때
 * 헤더를 침범하거나 큰 틈이 생기므로, 상단 내비와 data-ad-anchor 요소의 실제 하단을 재서 그 아래(+여백)에 붙인다.
 * 스크롤로 페이지 헤더가 사라지면 배너도 내비 바로 아래까지 따라 올라온다. */
const GAP = 12;
const top = ref(111);   // 측정 전 기본값(내비 47 + 헤더 52 + 여백)
let raf = 0;

const measure = () => {
    raf = 0;
    const navBottom = document.querySelector('#comm-lnb-web')?.getBoundingClientRect().bottom ?? 0;
    // 배너가 침범하면 안 되는 요소는 data-ad-anchor 로 표시한다(페이지 헤더, 홈의 차양 등).
    // 요소 밖으로 그려지는 장식(차양의 물결 가장자리 등)은 data-ad-pad(px)로 더한다.
    const anchorBottom = [...document.querySelectorAll('.app-shell [data-ad-anchor]')]
        .reduce((m, e) => Math.max(m, e.getBoundingClientRect().bottom + Number(e.dataset.adPad || 0)), 0);
    // 헤더가 모두 스크롤로 사라진 뒤에도 배너는 화면 위쪽 여백(GAP)에서 멈춰 계속 보인다.
    top.value = Math.round(Math.max(navBottom, anchorBottom, 0) + GAP);
};
const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };

onMounted(() => {
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    schedule();
});
onBeforeUnmount(() => {
    window.removeEventListener('scroll', schedule);
    window.removeEventListener('resize', schedule);
    if (raf) cancelAnimationFrame(raf);
});
// 화면이 바뀌면 헤더 높이도 달라질 수 있다(렌더 직후 한 번 더 잰다).
watch(() => route.path, () => nextTick(schedule));
watch(visible, () => nextTick(schedule));
</script>

<style scoped lang="scss">
.ad-side {
    position: fixed;
    /* top 은 스크립트가 헤더 하단을 재서 인라인으로 준다(위 measure) */
    z-index: 5;
    &.left  { left: 12px; }
    &.right { right: 12px; }
}
</style>
