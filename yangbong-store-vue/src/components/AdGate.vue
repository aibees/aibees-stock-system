<template>
    <div id="ad-gate">
        <div class="gate-card">
            <!-- 2026-11-22 꿀 광고: 보면 꿀, 건너뛰면 바로 들어간다(보상형 광고는 이용자가 골라야 한다 — AdMob 정책) -->
            <img v-if="supported" class="jar" src="/img/emoji/honey.png" alt="" />
            <p v-if="lessonGate" class="sub">수업 {{ lessonEvery }}개를 봤어요. 잠깐 쉬어 가요.</p>
            <h2>{{ title }}</h2>
            <p v-if="honeyNext" class="sub">광고를 끝까지 보면 꿀 {{ honeyNext }}을 드려요.</p>
            <p v-if="honeyLeft" class="left">오늘 {{ honeyLeft }}번 더 받을 수 있어요</p>

            <!-- 앱(AdMob)·목업은 보상형 광고가 전체 화면으로 뜨므로 자리표시 광고칸을 그리지 않는다 -->
            <AdSlot v-if="!supported" placement="gate" />

            <p v-if="message" class="msg">{{ message }}</p>

            <!-- 누르면 공통 덮개('광고 불러오는 중이에요')가 뜨고, 광고가 끝나면 결과대로 넘어간다(useRewardedAd.js) -->
            <template v-if="supported">
                <button class="btn-go" :disabled="busy" @click="watchAd">{{ failedOnce ? '다시 시도' : (honeyNext ? '광고 보고 꿀 받기' : '광고 보기') }}</button>
                <button type="button" class="btn-skip" :disabled="busy" @click="pass">건너뛰고 바로 보기</button>
            </template>

            <!-- 웹(광고 없음): 기다리지 않고 바로 들어간다 -->
            <button v-else class="btn-go" @click="pass">계속하기</button>
        </div>
    </div>
</template>

<script setup>
import AdSlot from './common/AdSlot.vue';
import { adPassPath, grantAdPass, resetGateCount, isLessonPath, resetLessonCount, lessonGateInterval } from '@scripts/useAdGate.js';
import { assUserSession } from '@scripts/stores/user-stores';
import { hasFeature } from '@scripts/useAccess.js';
import { preloadRewardedAd, rewardedAdSupported, runRewardedAd } from '@scripts/useRewardedAd.js';
import { useHoneyStore } from '@scripts/stores/honey-store.js';

const router = useRouter();
const route  = useRoute();

// next 는 앱 내부 경로만 허용한다(오픈 리다이렉트 방지).
const next = computed(() => {
    const n = String(route.query.next ?? '');
    return n.startsWith('/') && !n.startsWith('//') && !n.startsWith('/ad-gate') ? n : '/home';
});

/**
 * 광고 게이트. 앱은 들어오자마자 광고를 미리 불러 두고(덮개 없이), 누르면 공통 실행기가 덮개를 띄운다.
 * 결과:
 *   rewarded   통과 + 꿀 반영 확인(덮개 없이 뒤에서 — 다음 화면에서 '꿀 +N' 이 뜬다)
 *   dismissed  안내 후 그대로 머문다(광고를 다시 미리 불러 둔다)
 *   failed     안내 후 '다시 시도'·'건너뛰고 바로 보기'(불러오기 실패·시간 초과·재생 실패)
 * 광고를 못 받아도 사용자를 막지 않는다. 이 게이트는 UX 정책이지 보안 경계가 아니다.
 */
const userSession = assUserSession();
const honey = useHoneyStore();
const supported = rewardedAdSupported();
// 로그인했고 꿀 정보가 있으면 '광고 보고 꿀 N 받기'. 오늘 광고 꿀을 다 받았으면 게이트 없이 바로 들어간다.
// 웹은 광고로 꿀이 쌓이지 않으므로(서버 측 확인은 앱 광고만) 앱·목업에서만 꿀 문구를 보인다.
const honeyNext = computed(() => (supported && honey.summary && honey.summary.ad.count < honey.summary.ad.max ? honey.summary.ad.next : 0));
const honeyLeft = computed(() => (supported && honey.summary ? Math.max(0, honey.summary.ad.max - honey.summary.ad.count) : 0));
const title = computed(() => (supported
    ? (honeyNext.value ? `광고 보고 꿀 ${honeyNext.value} 받기` : '광고를 보고 이용해 보세요')
    : '광고 후 이용할 수 있어요'));
const message = ref('');
// 수업 학습 N개마다 오는 게이트인지(문구만 다르다)
const lessonGate = computed(() => isLessonPath(next.value));
const lessonEvery = computed(() => lessonGateInterval(userSession.access?.settings));
const busy = ref(false);
const failedOnce = ref(false);

const pass = () => {
    const uid = userSession.user.loginInfo.user_id;
    // 수업 게이트(학습 N개마다)는 수업 카운터만, 메뉴 게이트는 메뉴 카운터만 처음부터 센다
    if (isLessonPath(next.value)) resetLessonCount(uid);
    else resetGateCount(uid);   // 광고를 다 봤으니 N번 카운트를 처음부터
    grantAdPass(adPassPath(next.value));   // 이동할 경로 하나에만 쓰는 1회용 통과권
    router.replace(next.value);
};

const watchAd = async () => {
    if (busy.value) return;
    busy.value = true;
    message.value = '';
    const before = honey.summary;
    const result = await runRewardedAd({ customData: 'GATE' });
    busy.value = false;
    if (result === 'busy') return;
    if (result === 'rewarded') {
        // 꿀은 서버 SSV 로 들어온다. 기다리지 않고 넘어가고, 확인은 뒤에서(늦으면 전역 안내가 뜬다)
        if (userSession.user.accessToken && honeyNext.value) honey.afterAdReward({ before, wait: false });
        return pass();
    }
    if (result === 'dismissed') {
        message.value = honeyNext.value ? '광고를 끝까지 보면 꿀이 쌓여요.' : '광고를 끝까지 보거나 건너뛰고 바로 볼 수 있어요.';
        preloadRewardedAd('GATE');   // 본 광고는 소진됐다 — 다음 시도를 위해 새로 받아 둔다
        return;
    }
    failedOnce.value = true;
    message.value = '광고를 불러오지 못했어요. 다시 시도하거나 건너뛰고 바로 볼 수 있어요.';
};

onMounted(async () => {
    if (hasFeature('AD_FREE')) { router.replace(next.value); return; }
    if (userSession.user.accessToken) {
        const s = await honey.load();
        if (s && s.ad.count >= s.ad.max) { pass(); return; }
    }
    if (supported) preloadRewardedAd('GATE');
});
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
