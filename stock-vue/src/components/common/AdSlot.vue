<template>
    <div class="ad-slot" :style="{ width: size.width + 'px', height: size.height + 'px' }">
        <!-- 자리표시: 광고 계정 연동 전, 또는 앱(WebView) 환경 -->
        <div v-if="mode === 'placeholder'" class="ad-placeholder">
            <span class="tag">AD</span>
            <span class="dim">{{ size.width }} × {{ size.height }}</span>
            <span v-if="isNative" class="hint">앱 광고 연동 예정</span>
        </div>

        <div v-else-if="mode === 'gpt-test'" :id="gptDivId" class="ad-gpt"></div>

        <ins v-else-if="mode === 'adsense'" class="adsbygoogle"
            :style="{ display: 'inline-block', width: size.width + 'px', height: size.height + 'px' }"
            :data-ad-client="AD_CONFIG.adsense.client"
            :data-ad-slot="AD_CONFIG.adsense.slots[placement]"></ins>

        <ins v-else-if="mode === 'adfit'" class="kakao_ad_area" style="display: none;"
            :data-ad-unit="AD_CONFIG.adfit.units[placement]"
            :data-ad-width="size.width"
            :data-ad-height="size.height"></ins>
    </div>
</template>

<script setup>
import { Capacitor } from '@capacitor/core';
import { AD_PROVIDER, AD_CONFIG, AD_SIZES } from '@scripts/adConfig.js';

/**
 * 광고 1칸. placement 는 adConfig.AD_SIZES 의 키(side/gate/mobileInline/mobileBottom).
 * 제공자는 adConfig.AD_PROVIDER 로 고른다. 단위 ID 가 비어 있으면 자리표시로 떨어진다.
 *
 * ※ AdSense 는 앱 WebView 안에서 약관상 쓸 수 없어 앱에서는 자리표시만 그린다
 *   (앱은 AdMob 같은 네이티브 SDK 로 따로 붙여야 한다).
 * ※ gpt-test 는 구글 공개 샘플 단위로 테스트 광고만 그린다(수익 없음).
 * ※ adsense / adfit 분기는 계정 연동 전이라 실서비스에서 검증되지 않았다.
 */
const props = defineProps({
    placement: { type: String, default: 'side' }
});

const isNative = Capacitor.isNativePlatform();
const size = computed(() => AD_SIZES[props.placement] ?? AD_SIZES.side);

// 광고망이 이 칸을 못 채웠으면(no fill) 빈 구멍 대신 자리표시로 되돌린다.
const noFill = ref(false);

const mode = computed(() => {
    if (isNative || noFill.value) return 'placeholder';
    if (AD_PROVIDER === 'gpt-test') return 'gpt-test';
    if (AD_PROVIDER === 'adsense'
        && AD_CONFIG.adsense.client && AD_CONFIG.adsense.slots[props.placement]) return 'adsense';
    if (AD_PROVIDER === 'adfit' && AD_CONFIG.adfit.units[props.placement]) return 'adfit';
    return 'placeholder';
});

// 같은 placement 가 한 화면에 둘 이상일 수 있다(사이드 좌·우) → div id 는 인스턴스마다 따로.
const gptDivId = `gpt-ad-${props.placement}-${Math.random().toString(36).slice(2, 10)}`;
let gptSlot = null;
let onGptRender = null;

const releaseGpt = () => {
    const gt = window.googletag;
    const slot = gptSlot;
    const handler = onGptRender;
    gptSlot = null;
    onGptRender = null;
    gt?.cmd.push(() => {
        if (handler) gt.pubads().removeEventListener('slotRenderEnded', handler);
        if (slot) gt.destroySlots([slot]);
    });
};

const loadScriptOnce = (id, src, attrs = {}) => {
    if (document.getElementById(id)) return;
    const s = document.createElement('script');
    s.id = id;
    s.async = true;
    s.src = src;
    Object.entries(attrs).forEach(([k, v]) => s.setAttribute(k, v));
    document.head.appendChild(s);
};

onMounted(() => {
    try {
        if (mode.value === 'gpt-test') {
            window.googletag = window.googletag || { cmd: [] };
            loadScriptOnce('gpt-js', 'https://securepubads.g.doubleclick.net/tag/js/gpt.js');
            const { width, height } = size.value;
            window.googletag.cmd.push(() => {
                const gt = window.googletag;
                if (!document.getElementById(gptDivId)) return;   // 로드 전에 화면을 떠난 경우
                gptSlot = gt.defineSlot(AD_CONFIG.gptTest.unit, [width, height], gptDivId);
                if (!gptSlot) return;
                gptSlot.addService(gt.pubads());
                // 샘플 망은 같은 크기 광고를 한 페이지뷰에 하나만 줄 때가 있다(사이드 좌·우 중 한쪽이 빔).
                onGptRender = (e) => {
                    if (e.slot !== gptSlot || !e.isEmpty) return;
                    releaseGpt();
                    noFill.value = true;
                };
                gt.pubads().addEventListener('slotRenderEnded', onGptRender);
                gt.enableServices();
                gt.display(gptDivId);
            });
        } else if (mode.value === 'adsense') {
            loadScriptOnce('adsbygoogle-js',
                `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${AD_CONFIG.adsense.client}`,
                { crossorigin: 'anonymous' });
            (window.adsbygoogle = window.adsbygoogle || []).push({});
        } else if (mode.value === 'adfit') {
            // AdFit 스크립트는 로드 시점에 페이지의 ins 를 훑는다 → 슬롯이 늘 때마다 다시 붙인다.
            const old = document.getElementById('kakao-adfit-js');
            if (old) old.remove();
            loadScriptOnce('kakao-adfit-js', '//t1.daumcdn.net/kas/static/ba.min.js');
        }
    } catch (e) {
        console.error('[ad] 광고 로드 실패', e); // 광고 실패가 화면을 깨선 안 된다
    }
});

// SPA 라 화면을 떠나도 슬롯이 남는다 → 정리하지 않으면 같은 id 재정의·누수가 생긴다.
onBeforeUnmount(releaseGpt);
</script>

<style scoped lang="scss">
.ad-slot {
    position: relative;
    overflow: hidden;
    background: #fff;
    border: 1px dashed #F9E076;   /* 브랜드 허니색. 실제 광고가 들어가면 광고가 면을 덮는다 */
    border-radius: 6px;
    box-sizing: border-box;
}
.ad-gpt { width: 100%; height: 100%; }
.ad-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    color: #895129;
    opacity: .6;
    font-size: 12px;
    .tag { font-weight: 700; letter-spacing: 1px; }
    .hint { font-size: 11px; }
}
</style>
