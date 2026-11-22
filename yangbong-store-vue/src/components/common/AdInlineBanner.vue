<template>
    <!-- 화면 안 AdMob 배너 자리(앱 전용). 실제 배너는 네이티브(InlineAd 플러그인)가 이 칸 위에 겹쳐 그리고 스크롤을 따라 옮긴다.
         광고를 못 받으면 칸을 접는다. -->
    <div v-if="!failed" ref="slotRef" class="ad-inline" aria-label="광고"></div>
</template>

<script setup>
/**
 * 화면 안(스크롤되는 콘텐츠 사이) AdMob 배너 — 앱(iOS/Android) 전용, 2026-11-22.
 *
 * @capacitor-community/admob 배너는 화면 위/아래 고정뿐이라, 앱 안 플러그인 InlineAd
 * (ios/App/App/InlineAdPlugin.swift · android/.../InlineAdPlugin.java)로 따로 붙인다.
 *   - 이 컴포넌트는 빈 칸(320×50 자리)만 그리고, 그 칸의 문서 좌표를 플러그인에 알린다.
 *   - 스크롤은 네이티브가 스스로 따라간다. 여기서는 레이아웃이 바뀌어 칸이 움직였을 때만 다시 알린다.
 *   - 고정 헤더(headerSelector)와 하단 탭바(#comm-lnb) 영역에서는 배너를 잘라 그 위로 올라오지 않게 한다.
 *   - 웹 팝업([aria-modal="true"] 또는 [data-cover-inline-ad])이 떠 있는 동안은 숨긴다 — 네이티브 배너는 웹 요소보다 늘 위다.
 *
 * 노출 여부(AD_FREE·로그인 화면 등)는 부르는 쪽이 useShowAds 로 정한다. 이 컴포넌트는 앱 + AdMob 켜짐일 때만 쓴다.
 */
import { registerPlugin } from '@capacitor/core';
import { initAdMob, getBannerAdUnitId } from '@scripts/useAdMob.js';

const InlineAd = registerPlugin('InlineAd');

const props = defineProps({
    /** 위쪽 고정 헤더 선택자. 배너가 그 아래로만 보이게 자른다. */
    headerSelector: { type: String, default: '' },
});

const slotRef = ref(null);
const failed = ref(false);

let alive = true;
let shown = false;
let listeners = [];
let ro = null;
let mo = null;
let raf = 0;
let last = '';
let lastHidden = false;

/** 칸 위치·자르는 범위·팝업 여부를 잰다(CSS px). */
const measure = () => {
    const el = slotRef.value;
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const header = props.headerSelector ? document.querySelector(props.headerSelector) : null;
    const lnb = document.getElementById('comm-lnb');
    const lnbTop = lnb && lnb.offsetParent !== null ? lnb.getBoundingClientRect().top : window.innerHeight;
    return {
        x: r.left + window.scrollX,
        y: r.top + window.scrollY,
        width: r.width,
        height: r.height,
        clipTop: header ? Math.max(0, header.getBoundingClientRect().bottom) : 0,
        clipBottom: Math.max(0, window.innerHeight - lnbTop),
        hidden: !!document.querySelector('[aria-modal="true"], [data-cover-inline-ad]'),
    };
};

/** 바뀐 게 있을 때만 플러그인에 알린다(스크롤은 네이티브가 따라가므로 여기서 보내지 않는다). */
const sync = () => {
    raf = 0;
    if (!shown) return;
    const m = measure();
    if (!m) return;
    // 헤더가 스크롤에 따라 움직이지 않으니(sticky) y 는 문서 좌표로 고정 — 스크롤만으로는 값이 바뀌지 않는다.
    const key = [m.x, m.y, m.width, m.height, m.clipTop, m.clipBottom].map(v => Math.round(v)).join(',');
    if (key !== last) {
        last = key;
        const { hidden, ...geo } = m;
        InlineAd.update(geo).catch(() => {});
    }
    if (m.hidden !== lastHidden) {
        lastHidden = m.hidden;
        InlineAd.setHidden({ hidden: m.hidden }).catch(() => {});
    }
};
const schedule = () => { if (!raf) raf = requestAnimationFrame(sync); };

onMounted(async () => {
    const adId = getBannerAdUnitId();
    if (!adId) { failed.value = true; return; }
    if (!(await initAdMob()) || !alive) { if (alive) failed.value = true; return; }
    await nextTick();
    const m = measure();
    if (!m || !alive) return;

    listeners.push(await InlineAd.addListener('failed', (e) => {
        console.warn('[admob] 화면 안 배너 로드 실패:', e?.message);
        failed.value = true;   // 빈 칸이 남지 않게 접는다
        InlineAd.remove().catch(() => {});
        shown = false;
    }));

    const { hidden, ...geo } = m;
    try {
        await InlineAd.show({ adId, ...geo });
    } catch (e) {
        console.warn('[admob] 화면 안 배너 표시 실패:', e?.message ?? e);
        failed.value = true;
        return;
    }
    if (!alive) { InlineAd.remove().catch(() => {}); return; }
    shown = true;
    last = [geo.x, geo.y, geo.width, geo.height, geo.clipTop, geo.clipBottom].map(v => Math.round(v)).join(',');
    lastHidden = false;
    if (hidden) schedule();

    // 레이아웃 변화(위쪽 콘텐츠 로딩·화면 회전)와 팝업 열림·닫힘을 본다
    ro = new ResizeObserver(schedule);
    ro.observe(document.body);
    mo = new MutationObserver(schedule);
    mo.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['aria-modal', 'data-cover-inline-ad', 'class', 'style'] });
    window.addEventListener('resize', schedule);
});

onBeforeUnmount(() => {
    alive = false;
    if (raf) cancelAnimationFrame(raf);
    ro?.disconnect();
    mo?.disconnect();
    window.removeEventListener('resize', schedule);
    listeners.forEach(h => h?.remove?.());
    listeners = [];
    if (shown) InlineAd.remove().catch(() => {});
    shown = false;
});
</script>

<style scoped>
/* 배너(320×50)가 들어갈 자리. 네이티브 배너가 이 칸 가운데 위에 그려진다. */
.ad-inline {
    width: 100%;
    height: 50px;
}
</style>
