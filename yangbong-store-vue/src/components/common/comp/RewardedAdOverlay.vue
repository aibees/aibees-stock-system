<template>
    <!-- 보상형 광고 전체 덮개(App.vue 에 한 번). 불러오는 중·재생 중·꿀 확인 중 동안 화면을 덮어 다른 버튼을 못 누르게 한다.
         앱에서는 재생 중에 네이티브 광고가 이 덮개 위에 뜬다. 목업에서는 여기에 가짜 광고를 그린다. -->
    <div v-if="st.phase" class="rao" role="dialog" aria-modal="true" aria-live="polite" :aria-label="label">
        <div v-if="st.mock" class="mock">
            <p class="mk">목업 광고</p>
            <p class="mt">실제 앱에서는 여기서 광고가 재생돼요</p>
            <button type="button" class="b1" @click="answerMockAd('rewarded')">끝까지 보기</button>
            <button type="button" class="b2" @click="answerMockAd('dismissed')">중간에 닫기</button>
            <button type="button" class="b2" @click="answerMockAd('failed')">재생 실패</button>
        </div>
        <div v-else class="box">
            <img src="/img/emoji/honey.png" alt="" />
            <span class="spin" aria-hidden="true"></span>
            <p>{{ label }}</p>
            <small v-if="st.phase === 'loading'">잠시만 기다려 주세요</small>
        </div>
    </div>
    <p v-if="notice" :key="st.noticeKey" class="rao-notice" role="status">{{ notice }}</p>
</template>

<script setup>
import { rewardedAdState as st, answerMockAd } from '@scripts/useRewardedAd.js';

const label = computed(() => ({
    loading: '광고 불러오는 중이에요',
    showing: '광고 재생 중이에요',
    checking: '꿀을 확인하고 있어요',
}[st.phase] ?? ''));

// 끝난 뒤 안내는 3초 보이고 사라진다
const notice = ref('');
let timer = null;
watch(() => st.noticeKey, () => {
    notice.value = st.notice;
    clearTimeout(timer);
    if (notice.value) timer = setTimeout(() => { notice.value = ''; }, 3200);
});
onBeforeUnmount(() => clearTimeout(timer));
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.rao {
    position: fixed; inset: 0; z-index: 1900;   // HoneyPop(2000) 이 위에 뜬다
    display: flex; align-items: center; justify-content: center;
    background: rgba(255, 255, 255, .96);
    font-family: $font-body; color: $ink; text-align: center;
}
.box {
    display: flex; flex-direction: column; align-items: center;
    img { width: 56px; height: 56px; }
    .spin { width: 22px; height: 22px; margin-top: 18px; border-radius: 50%; border: 2.5px solid $honey-100; border-top-color: $honey-500; animation: rao-spin .8s linear infinite; }
    p { margin: 14px 0 0; font-size: 16px; font-weight: 700; letter-spacing: -.3px; }
    small { margin-top: 6px; font-size: 13px; color: $sub; }
}
.mock {
    width: min(320px, calc(100% - 32px)); padding: 24px 20px; border: 1px solid $line; border-radius: 14px; background: #fff;
    .mk { margin: 0; font-size: 12.5px; font-weight: 800; color: $amber-700; }
    .mt { margin: 6px 0 16px; font-size: 14px; color: $sub-ink; }
    button { width: 100%; height: 44px; margin-top: 6px; border: 0; border-radius: 10px; font: inherit; font-size: 14.5px; font-weight: 700; cursor: pointer; }
    .b1 { background: #5A3C08; color: #fff; }
    .b2 { background: transparent; color: $sub; }
}
.rao-notice {
    position: fixed; left: 50%; bottom: calc(var(--lnb-total, 0px) + 20px); z-index: 1950; transform: translateX(-50%);
    width: max-content; max-width: calc(100% - 32px); margin: 0; padding: 11px 16px; border-radius: 12px;
    background: #191F28; color: #fff; font-family: $font-body; font-size: 13.5px; line-height: 1.45; text-align: center; word-break: keep-all;
    box-shadow: 0 8px 22px rgba(0, 0, 0, .14);
}
@keyframes rao-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .box .spin { animation-duration: 2.4s; } }
</style>
