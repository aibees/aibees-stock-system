<template>
    <div id="ad-gate">
        <div class="gate-card">
            <!-- 2026-11-22 꿀 광고: 보면 꿀, 건너뛰면 바로 들어간다(보상형 광고는 이용자가 골라야 한다 — AdMob 정책) -->
            <img v-if="nativeAds && mode !== 'timer'" class="jar" src="/img/emoji/honey.png" alt="" />
            <h2>{{ title }}</h2>
            <p v-if="honeyNext" class="sub">광고를 끝까지 보면 꿀 {{ honeyNext }}을 드려요.</p>
            <p v-if="honeyLeft" class="left">오늘 {{ honeyLeft }}번 더 받을 수 있어요</p>

            <!-- 앱(AdMob)은 보상형 광고가 전체 화면으로 뜨므로 자리표시 광고칸을 그리지 않는다 -->
            <AdSlot v-if="!nativeAds" placement="gate" />

            <p v-if="message" class="msg">{{ message }}</p>

            <!-- 앱: 보상형 광고를 끝까지 보면 통과 -->
            <button v-if="nativeAds && mode !== 'timer'" class="btn-go"
                :disabled="mode !== 'ready'" @click="watchAd">
                {{ mode === 'loading' ? '광고 준비 중…' : mode === 'showing' ? '광고 재생 중…' : (honeyNext ? '광고 보고 꿀 받기' : '광고 보기') }}
            </button>
            <button v-if="nativeAds && mode !== 'timer'" type="button" class="btn-skip" :disabled="mode === 'showing'" @click="pass">건너뛰고 바로 보기</button>

            <!-- 웹, 또는 앱에서 광고를 못 받았을 때: 기다리지 않고 바로 들어간다 -->
            <button v-else class="btn-go" @click="pass">계속하기</button>
        </div>
    </div>
</template>

<script setup>
import AdSlot from './common/AdSlot.vue';
import { AD_GATE_SECONDS } from '@scripts/adConfig.js';
import { adPassPath, grantAdPass, resetGateCount } from '@scripts/useAdGate.js';
import { assUserSession } from '@scripts/stores/user-stores';
import { hasFeature } from '@scripts/useAccess.js';
import { isNativeAdsEnabled, loadRewardedAd, showRewardedAd } from '@scripts/useAdMob.js';
import { useHoneyStore } from '@scripts/stores/honey-store.js';

const router = useRouter();
const route  = useRoute();

// next 는 앱 내부 경로만 허용한다(오픈 리다이렉트 방지).
const next = computed(() => {
    const n = String(route.query.next ?? '');
    return n.startsWith('/') && !n.startsWith('//') && !n.startsWith('/ad-gate') ? n : '/home';
});

/**
 * mode
 *   loading  보상형 광고 불러오는 중(앱)
 *   ready    광고 준비 끝 — 버튼을 누르면 재생(앱)
 *   showing  재생 중(앱)
 *   timer    기존 방식: AD_GATE_SECONDS 대기 후 통과(웹, 또는 앱에서 광고를 못 받았을 때)
 * 앱에서 광고를 못 받는 경우(미채움·네트워크·동의 없음)에도 사용자를 막지 않고 timer 로 떨어진다.
 * 이 게이트는 UX 정책이지 보안 경계가 아니다.
 */
const userSession = assUserSession();
const honey = useHoneyStore();
const nativeAds = isNativeAdsEnabled();
// 로그인했고 꿀 정보가 있으면 '광고 보고 꿀 N 받기'. 오늘 광고 꿀을 다 받았으면 게이트 없이 바로 들어간다.
// 웹은 광고로 꿀이 쌓이지 않으므로(서버 측 확인은 앱 광고만) 앱에서만 꿀 문구를 보인다.
const honeyNext = computed(() => (nativeAds && honey.summary && honey.summary.ad.count < honey.summary.ad.max ? honey.summary.ad.next : 0));
const honeyLeft = computed(() => (nativeAds && honey.summary ? Math.max(0, honey.summary.ad.max - honey.summary.ad.count) : 0));
const title = computed(() => (nativeAds && mode.value !== 'timer'
    ? (honeyNext.value ? `광고 보고 꿀 ${honeyNext.value} 받기` : '광고를 보고 이용해 보세요')
    : '광고 후 이용할 수 있어요'));
const mode = ref(nativeAds ? 'loading' : 'timer');
const message = ref('');
const remain = ref(0);   // 2026-11-22 강제 대기 없음(꿀 광고로 바뀜). AD_GATE_SECONDS 는 쓰지 않는다
void AD_GATE_SECONDS;
let timer = null;

const startTimer = () => {
    mode.value = 'timer';
    remain.value = 0;
    clearInterval(timer);
};

const prepareAd = async () => {
    mode.value = 'loading';
    const uid = userSession.user.loginInfo.user_id;
    if (await loadRewardedAd({ ssvUserId: uid ? String(uid) : undefined, ssvCustomData: 'GATE' })) {
        mode.value = 'ready';
    } else {
        message.value = '광고를 불러오지 못해 잠시 후 이용할 수 있어요.';
        startTimer();
    }
};

const pass = () => {
    resetGateCount(userSession.user.loginInfo.user_id);   // 광고를 다 봤으니 N번 카운트를 처음부터
    grantAdPass(adPassPath(next.value));   // 이동할 경로 하나에만 쓰는 1회용 통과권
    router.replace(next.value);
};

const proceed = () => {
    if (remain.value > 0) return;
    pass();
};

const watchAd = async () => {
    if (mode.value !== 'ready') return;
    mode.value = 'showing';
    message.value = '';
    const result = await showRewardedAd();
    if (result === 'rewarded') { if (honeyNext.value) honey.afterGateAd(); return pass(); }
    if (result === 'dismissed') {
        // 보상 없이 닫음 → 소진된 광고를 새로 받아 다시 시도하게 한다.
        message.value = '광고를 끝까지 보면 꿀이 쌓여요.';
        return prepareAd();
    }
    message.value = '광고를 재생하지 못해 잠시 후 이용할 수 있어요.';
    startTimer();
};

onMounted(async () => {
    if (hasFeature('AD_FREE')) { router.replace(next.value); return; }
    if (userSession.user.accessToken) {
        const s = await honey.load();
        if (s && s.ad.count >= s.ad.max) { pass(); return; }
    }
    if (nativeAds) prepareAd();
    else startTimer();
});
onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped lang="scss">
#ad-gate {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 16px;
    background: #f7f7f7;
    color: #141414;
}
.gate-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    max-width: 360px;
    width: 100%;
    padding: 28px 20px;
    background: #fff;
    border: 1px solid #dcdcdc;
    border-radius: 12px;
    h2 { margin: 0; font-size: 17px; }
    .sub { margin: 0; font-size: 12px; color: #737373; line-height: 1.5; }
    .msg { margin: 0; font-size: 12px; color: #c0392b; text-align: center; }
}
.btn-go {
    width: 100%;
    padding: 12px;
    border: 0;
    border-radius: 8px;
    background: #141414;
    color: #fff;
    font-size: 14px;
    cursor: pointer;
    &:disabled { background: #dcdcdc; color: #9a9a9a; cursor: default; }
}

/* 꿀 광고 */
.jar { width: 52px; height: 52px; margin: 0 auto; display: block; }
.left { margin: 0; font-size: 12.5px; color: #4E5968; text-align: center; }
.btn-skip { margin-top: 2px; height: 40px; border: 0; background: transparent; color: #8B95A1; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
</style>
