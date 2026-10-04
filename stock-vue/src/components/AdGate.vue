<template>
    <div id="ad-gate">
        <div class="gate-card">
            <h2>잠시 광고 후 이용할 수 있어요</h2>
            <p class="sub">광고 없이 이용하려면 관리자에게 광고 제거 권한을 요청하세요.</p>

            <AdSlot placement="gate" />

            <button class="btn-go" :disabled="remain > 0" @click="proceed">
                {{ remain > 0 ? `${remain}초 후 계속하기` : '계속하기' }}
            </button>
        </div>
    </div>
</template>

<script setup>
import AdSlot from './common/AdSlot.vue';
import { AD_GATE_SECONDS } from '@scripts/adConfig.js';
import { grantAdPass } from '@scripts/useAdGate.js';
import { hasFeature } from '@scripts/useAccess.js';

const router = useRouter();
const route  = useRoute();

// next 는 앱 내부 경로만 허용한다(오픈 리다이렉트 방지).
const next = computed(() => {
    const n = String(route.query.next ?? '');
    return n.startsWith('/') && !n.startsWith('//') && !n.startsWith('/ad-gate') ? n : '/home';
});

const remain = ref(AD_GATE_SECONDS);
let timer = null;

const proceed = () => {
    if (remain.value > 0) return;
    grantAdPass();
    router.replace(next.value);
};

onMounted(() => {
    if (hasFeature('AD_FREE')) { router.replace(next.value); return; }
    timer = setInterval(() => {
        remain.value -= 1;
        if (remain.value <= 0) clearInterval(timer);
    }, 1000);
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
