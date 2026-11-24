<template>
    <!-- 화면 안 광고 1칸(앱 전용). 보일 조건(AD_FREE·작업자·로그인 화면 등)은 여기서 한 번에 정한다. 웹은 아무것도 그리지 않는다. -->
    <section v-if="visible" class="ad-inline-slot" aria-label="광고">
        <AdInlineBanner :header-selector="headerSelector" />
    </section>
</template>

<script setup>
/**
 * 하단 탭 화면(트레이닝·주식분석·메뉴)에 한 개씩 끼우는 화면 안 광고 — 앱(AdMob 적응형 배너) 전용.
 *
 * 홈에는 두지 않는다(2026-11-24): 홈은 옆으로 넘기는 탭으로 나뉘어, 네이티브가 따로 겹쳐 그리는 배너가
 * 탭이 넘어가는 동안 제자리에 남거나 어긋난다. 그래서 가로 이동이 없는 이 화면들로 옮겼다.
 *
 * 쓰는 곳: 한 화면에 하나만(같은 화면에 둘을 두면 네이티브 배너가 둘 떠서 서로 겹칠 수 있다).
 *   header-selector : 위에 고정(sticky)된 헤더가 있으면 그 선택자(예: '[data-ad-anchor]'). 배너가 그 아래로만 보이게 자른다.
 */
import AdInlineBanner from './AdInlineBanner.vue';
import { useShowAds } from '@scripts/useAds.js';
import { isNativeAdsEnabled } from '@scripts/useAdMob.js';
import { hasRole, WORKER_ROLE } from '@scripts/useAccess.js';

defineProps({
    headerSelector: { type: String, default: '' },
});

const showAds = useShowAds();
const isWorker = computed(() => hasRole(WORKER_ROLE));
const visible = computed(() => !isWorker.value && showAds.value && isNativeAdsEnabled());
</script>

<style scoped lang="scss">
/* 배너는 화면 너비를 꽉 채운다(좌우 여백 없음). 위아래만 숨 쉴 틈을 둔다 */
.ad-inline-slot { padding: 12px 0; }
</style>
