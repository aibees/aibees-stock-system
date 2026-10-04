<template>
    <div v-if="visible" class="ad-inline">
        <AdSlot :placement="placement" />
    </div>
</template>

<script setup>
import AdSlot from './AdSlot.vue';
import { MOBILE_MAX_WIDTH } from '@scripts/adConfig.js';
import { useShowAds, useMediaQuery } from '@scripts/useAds.js';

/**
 * 화면 안에 끼우는 모바일 전용 배너. 데스크톱은 사이드 배너가 맡으므로 렌더하지 않는다.
 * 사용 예) <AdBanner />  (기본 placement = mobileInline)
 */
defineProps({
    placement: { type: String, default: 'mobileInline' }
});

const showAds = useShowAds();
const narrow  = useMediaQuery(`(max-width: ${MOBILE_MAX_WIDTH}px)`);
const visible = computed(() => showAds.value && narrow.value);
</script>

<style scoped lang="scss">
.ad-inline {
    display: flex;
    justify-content: center;
    margin: 12px 0;
}
</style>
