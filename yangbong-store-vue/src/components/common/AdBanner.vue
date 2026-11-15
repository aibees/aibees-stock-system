<template>
    <div v-if="visible" class="ad-inline">
        <AdSlot :placement="placement" />
    </div>
</template>

<script setup>
import AdSlot from './AdSlot.vue';
import { MOBILE_MAX_WIDTH } from '@scripts/adConfig.js';
import { useShowAds, useMediaQuery } from '@scripts/useAds.js';
import { isNativeAdsEnabled } from '@scripts/useAdMob.js';

/**
 * 화면 안에 끼우는 모바일 전용 배너. 데스크톱은 사이드 배너가 맡으므로 렌더하지 않는다.
 * 사용 예) <AdBanner />  (기본 placement = mobileInline)
 */
defineProps({
    placement: { type: String, default: 'mobileInline' }
});

const showAds = useShowAds();
const narrow  = useMediaQuery(`(max-width: ${MOBILE_MAX_WIDTH}px)`);
// 앱(AdMob)에서는 네이티브 광고가 화면 위에 겹쳐 그려져 스크롤되는 인라인 자리에 붙일 수 없다.
// 하단 고정 배너(AdBottomBanner)가 모바일 광고를 맡으므로, 앱에서는 "앱 광고 연동 예정" 자리표시를 그리지 않는다.
const visible = computed(() => showAds.value && narrow.value && !isNativeAdsEnabled());
</script>

<style scoped lang="scss">
.ad-inline {
    display: flex;
    justify-content: center;
    margin: 12px 0;
}
</style>
