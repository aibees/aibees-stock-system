<template>
    <div v-if="active" class="ad-bottom">
        <AdSlot placement="mobileBottom" />
    </div>
</template>

<script setup>
import AdSlot from './AdSlot.vue';
import { MOBILE_MAX_WIDTH } from '@scripts/adConfig.js';
import { useShowAds, useMediaQuery } from '@scripts/useAds.js';

/**
 * 모바일 하단 탭바(Lnb) 아래 고정 배너.
 * 배너가 떠 있는 동안 <html> 에 has-bottom-ad 클래스를 달아, App.vue 의 전역 CSS 가
 * 탭바를 배너 높이만큼 위로 올리고 화면 하단 여백(--lnb-total)을 늘리게 한다.
 * (홈 인디케이터 영역은 이제 배너가 차지하므로 탭바는 safe-area 패딩을 버린다.)
 */
const showAds = useShowAds();
const narrow  = useMediaQuery(`(max-width: ${MOBILE_MAX_WIDTH}px)`);
const active  = computed(() => showAds.value && narrow.value);

watch(active, (v) => document.documentElement.classList.toggle('has-bottom-ad', v), { immediate: true });
onBeforeUnmount(() => document.documentElement.classList.remove('has-bottom-ad'));
</script>

<style scoped lang="scss">
.ad-bottom {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: var(--ad-bottom-total);
    box-sizing: border-box;
    padding-bottom: env(safe-area-inset-bottom, 0px);
    display: flex;
    justify-content: center;
    align-items: center;
    background: #fff;
    border-top: 1px solid #dcdcdc;
    z-index: 1001;
}
</style>
