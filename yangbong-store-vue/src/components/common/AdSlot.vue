<template>
    <div ref="rootRef" class="ad-slot" :class="{ fill: isFill }" :style="boxStyle">
        <!-- 자리표시: 광고 계정 연동 전, 또는 앱(WebView) 환경 -->
        <div v-if="mode === 'placeholder'" class="ad-placeholder" :class="{ row: isFill }">
            <span class="tag">AD</span>
            <span class="dim">{{ isFill ? '가로 꽉 참' : `${size.width} × ${size.height}` }}</span>
            <span v-if="isNative" class="hint">앱 광고 연동 예정</span>
        </div>

        <!-- 테스트 광고는 고정 크기 소재뿐이라, 꽉 채움 칸에서는 칸 너비에 맞춰 같은 비율로 확대한다.
             (실광고에 이렇게 하면 약관 위반 — 실광고는 아래 adsense 의 반응형 단위가 칸을 채운다) -->
        <div v-else-if="mode === 'gpt-test'" :id="gptDivId" class="ad-gpt" :style="gptStyle"></div>

        <ins v-else-if="mode === 'adsense' && isFill" class="adsbygoogle"
            :style="{ display: 'block', width: '100%', height: fillHeight + 'px' }"
            :data-ad-client="AD_CONFIG.adsense.client"
            :data-ad-slot="AD_CONFIG.adsense.slots[placement]"
            data-ad-format="horizontal"
            data-full-width-responsive="true"></ins>

        <ins v-else-if="mode === 'adsense'" class="adsbygoogle"
            :style="{ display: 'inline-block', width: size.width + 'px', height: size.height + 'px' }"
            :data-ad-client="AD_CONFIG.adsense.client"
            :data-ad-slot="AD_CONFIG.adsense.slots[placement]"></ins>

        <ins v-else-if="mode === 'adfit'" class="kakao_ad_area" style="display: none;"
            :data-ad-unit="AD_CONFIG.adfit.units[placement]"
            :data-ad-width="creative.width"
            :data-ad-height="creative.height"></ins>
    </div>
</template>

<script setup>
import { Capacitor } from '@capacitor/core';
import { AD_PROVIDER, AD_CONFIG, AD_SIZES } from '@scripts/adConfig.js';

/**
 * 광고 1칸. placement 는 adConfig.AD_SIZES 의 키(side/gate/homeHero/mobileInline/mobileBottom).
 * 제공자는 adConfig.AD_PROVIDER 로 고른다. 단위 ID 가 비어 있으면 자리표시로 떨어진다.
 *
 * 꽉 채움(AD_SIZES[placement].fill) 칸: 부모 너비를 그대로 쓰고, 높이는 그 너비에 맞는 배너 비율
 * (AD_SIZES[placement].creatives 중 칸에 맞는 것)로 정한다. 정한 높이는 'height' 이벤트로
 * 알린다(하단 고정 배너가 탭바 위치를 맞추는 데 쓴다).
 *
 * ※ AdSense 는 앱 WebView 안에서 약관상 쓸 수 없어 앱에서는 자리표시만 그린다
 *   (앱은 AdMob 같은 네이티브 SDK 로 따로 붙여야 한다).
 * ※ gpt-test 는 구글 공개 샘플 단위로 테스트 광고만 그린다(수익 없음).
 * ※ adsense / adfit 분기는 계정 연동 전이라 실서비스에서 검증되지 않았다.
 */
const props = defineProps({
    placement: { type: String, default: 'side' }
});
const emit = defineEmits(['height']);

const isNative = Capacitor.isNativePlatform();
const size = computed(() => AD_SIZES[props.placement] ?? AD_SIZES.side);
const isFill = computed(() => !!size.value.fill);

/* ── 꽉 채움: 너비 측정 → 소재 크기·높이 결정 ── */
const rootRef = ref(null);
const boxWidth = ref(0);
let ro = null;

// 칸 너비에 맞는 소재(넓은 것부터 보고 칸에 맞는 첫 번째, 없으면 가장 작은 것)
const fillCreatives = computed(() => size.value.creatives ?? [{ width: size.value.width, height: size.value.height, minBoxWidth: 0 }]);
const pickCreative = (w) => {
    const list = fillCreatives.value;
    return list.find(c => w >= c.minBoxWidth) ?? list[list.length - 1];
};

// 소재 크기는 처음 잰 너비로 한 번 정한다(광고 요청 뒤에 바꾸면 슬롯을 다시 만들어야 한다).
const creative = ref(isFill.value ? fillCreatives.value[fillCreatives.value.length - 1] : size.value);
const scale = computed(() => (isFill.value && boxWidth.value ? boxWidth.value / creative.value.width : 1));
const fillHeight = computed(() => Math.round(creative.value.height * scale.value));

const boxStyle = computed(() => (isFill.value
    ? { width: '100%', height: fillHeight.value + 'px' }
    : { width: size.value.width + 'px', height: size.value.height + 'px' }));

const gptStyle = computed(() => (isFill.value
    ? { width: creative.value.width + 'px', height: creative.value.height + 'px', transform: `scale(${scale.value})` }
    : null));

watch(fillHeight, (h) => { if (isFill.value) emit('height', h); });

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
    if (isFill.value && rootRef.value) {
        boxWidth.value = rootRef.value.clientWidth;
        creative.value = pickCreative(boxWidth.value);
        emit('height', fillHeight.value);
        ro = new ResizeObserver(([entry]) => { boxWidth.value = entry.contentRect.width; });
        ro.observe(rootRef.value);
    }
    try {
        if (mode.value === 'gpt-test') {
            window.googletag = window.googletag || { cmd: [] };
            loadScriptOnce('gpt-js', 'https://securepubads.g.doubleclick.net/tag/js/gpt.js');
            const { width, height } = creative.value;
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
onBeforeUnmount(() => {
    ro?.disconnect();
    releaseGpt();
});
</script>

<style scoped lang="scss">
.ad-slot {
    position: relative;
    overflow: hidden;
    background: #fff;
    border: 1px dashed #F9E076;   /* 브랜드 허니색. 실제 광고가 들어가면 광고가 면을 덮는다 */
    border-radius: 6px;
    box-sizing: border-box;

    // 꽉 채움 칸은 테두리·둥근 모서리 없이 광고 면이 칸 끝까지 닿게 한다.
    &.fill { border: 0; border-radius: 0; }
}
.ad-gpt { width: 100%; height: 100%; transform-origin: 0 0; }
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
    &.row { flex-direction: row; gap: 8px; border: 1px dashed #F9E076; box-sizing: border-box; }
    .tag { font-weight: 700; letter-spacing: 1px; }
    .hint { font-size: 11px; }
}
</style>
