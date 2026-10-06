<template>
    <div v-if="active" class="ad-bottom">
        <!-- 네이티브 AdMob 이 켜져 있으면 광고는 WebView 위에 네이티브 뷰로 겹쳐 그려지므로 칸만 비워 둔다 -->
        <AdSlot v-if="!nativeAds" placement="mobileBottom" />
    </div>
</template>

<script setup>
import AdSlot from './AdSlot.vue';
import { MOBILE_MAX_WIDTH } from '@scripts/adConfig.js';
import { useShowAds, useMediaQuery } from '@scripts/useAds.js';
import { isNativeAdsEnabled, bannerState, showBottomBanner, hideBottomBanner } from '@scripts/useAdMob.js';

/**
 * 모바일 하단 탭바(Lnb) 아래 고정 배너.
 * 배너가 떠 있는 동안 <html> 에 has-bottom-ad 클래스를 달아, App.vue 의 전역 CSS 가
 * 탭바를 배너 높이만큼 위로 올리고 화면 하단 여백(--lnb-total)을 늘리게 한다.
 * (홈 인디케이터 영역은 이제 배너가 차지하므로 탭바는 safe-area 패딩을 버린다.)
 *
 * 앱(iOS/Android)에서는 같은 칸에 AdMob 네이티브 배너를 겹쳐 띄운다(useAdMob.js).
 * 노출 여부 판단(권한 AD_FREE·/login·좁은 화면)은 여기 active 하나만 쓴다.
 * 네이티브 광고를 못 받으면(failed) 빈 칸이 남지 않게 has-bottom-ad 를 거둔다.
 */
const showAds = useShowAds();
const narrow  = useMediaQuery(`(max-width: ${MOBILE_MAX_WIDTH}px)`);
const active  = computed(() => showAds.value && narrow.value);
const nativeAds = isNativeAdsEnabled();

// 칸을 예약해야 하는가: 노출 대상이고, (네이티브면) 광고 요청이 실패 상태가 아닐 때
const reserve = computed(() => active.value && !(nativeAds && bannerState.value === 'failed'));

watch(reserve, (v) => document.documentElement.classList.toggle('has-bottom-ad', v), { immediate: true });
if (nativeAds) {
    // 칸을 접은 동안에는 네이티브 배너도 숨긴다(SDK 가 나중에 재시도로 채우면 Loaded → 다시 예약).
    watch(active, (v) => { v ? showBottomBanner() : hideBottomBanner(); }, { immediate: true });
}
onBeforeUnmount(() => {
    document.documentElement.classList.remove('has-bottom-ad');
    if (nativeAds) hideBottomBanner();
});
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
