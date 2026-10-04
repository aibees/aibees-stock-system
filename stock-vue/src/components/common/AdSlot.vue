<template>
    <div class="ad-slot" :style="{ width: size.width + 'px', height: size.height + 'px' }">
        <!-- 자리표시: 광고 계정 연동 전, 또는 앱(WebView) 환경 -->
        <div v-if="mode === 'placeholder'" class="ad-placeholder">
            <span class="tag">AD</span>
            <span class="dim">{{ size.width }} × {{ size.height }}</span>
            <span v-if="isNative" class="hint">앱 광고 연동 예정</span>
        </div>

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
 * ※ adsense / adfit 분기는 계정 연동 전이라 실서비스에서 검증되지 않았다.
 */
const props = defineProps({
    placement: { type: String, default: 'side' }
});

const isNative = Capacitor.isNativePlatform();
const size = computed(() => AD_SIZES[props.placement] ?? AD_SIZES.side);

const mode = computed(() => {
    if (isNative) return 'placeholder';
    if (AD_PROVIDER === 'adsense'
        && AD_CONFIG.adsense.client && AD_CONFIG.adsense.slots[props.placement]) return 'adsense';
    if (AD_PROVIDER === 'adfit' && AD_CONFIG.adfit.units[props.placement]) return 'adfit';
    return 'placeholder';
});

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
        if (mode.value === 'adsense') {
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
</script>

<style scoped lang="scss">
.ad-slot {
    position: relative;
    overflow: hidden;
    background: #f1f1f1;
    border: 1px dashed #c4c4c4;
    border-radius: 6px;
    box-sizing: border-box;
}
.ad-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    color: #9a9a9a;
    font-size: 12px;
    .tag { font-weight: 700; letter-spacing: 1px; }
    .hint { font-size: 11px; }
}
</style>
