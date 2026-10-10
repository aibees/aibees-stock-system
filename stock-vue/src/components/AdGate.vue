<template>
    <div id="ad-gate">
        <div class="gate-card">
            <h2>{{ nativeAds && mode !== 'timer' ? '광고를 보고 이용할 수 있어요' : '잠시 광고 후 이용할 수 있어요' }}</h2>
            <p class="sub">광고 없이 이용하려면 관리자에게 광고 제거 권한을 요청하세요.</p>

            <!-- 앱(AdMob)은 보상형 광고가 전체 화면으로 뜨므로 자리표시 광고칸을 그리지 않는다 -->
            <AdSlot v-if="!nativeAds" placement="gate" />

            <p v-if="message" class="msg">{{ message }}</p>

            <!-- 앱: 보상형 광고를 끝까지 보면 통과 -->
            <button v-if="nativeAds && mode !== 'timer'" class="btn-go"
                :disabled="mode !== 'ready'" @click="watchAd">
                {{ mode === 'loading' ? '광고 준비 중…' : mode === 'showing' ? '광고 재생 중…' : '광고 보고 계속하기' }}
            </button>

            <!-- 웹, 또는 앱에서 광고를 못 받았을 때: 기존 대기 후 통과 -->
            <button v-else class="btn-go" :disabled="remain > 0" @click="proceed">
                {{ remain > 0 ? `${remain}초 후 계속하기` : '계속하기' }}
            </button>
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
const nativeAds = isNativeAdsEnabled();
const mode = ref(nativeAds ? 'loading' : 'timer');
const message = ref('');
const remain = ref(AD_GATE_SECONDS);
let timer = null;

const startTimer = () => {
    mode.value = 'timer';
    remain.value = AD_GATE_SECONDS;
    clearInterval(timer);
    timer = setInterval(() => {
        remain.value -= 1;
        if (remain.value <= 0) clearInterval(timer);
    }, 1000);
};

const prepareAd = async () => {
    mode.value = 'loading';
    if (await loadRewardedAd()) {
        mode.value = 'ready';
    } else {
        message.value = '광고를 불러오지 못해 잠시 후 이용할 수 있어요.';
        startTimer();
    }
};

const userSession = assUserSession();
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
    if (result === 'rewarded') return pass();
    if (result === 'dismissed') {
        // 보상 없이 닫음 → 소진된 광고를 새로 받아 다시 시도하게 한다.
        message.value = '광고를 끝까지 봐야 이용할 수 있어요.';
        return prepareAd();
    }
    message.value = '광고를 재생하지 못해 잠시 후 이용할 수 있어요.';
    startTimer();
};

onMounted(() => {
    if (hasFeature('AD_FREE')) { router.replace(next.value); return; }
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
</style>
