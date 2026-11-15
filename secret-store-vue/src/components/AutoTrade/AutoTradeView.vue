<template>
    <div id="auto-trade-view">
        <!-- ── 하위 화면 탭 ── -->
        <nav class="at-tabs">
            <router-link v-for="t in tabs" :key="t.path" :to="t.path" class="at-tab"
                :class="{ on: route.path === t.path }">
                {{ t.label }}
            </router-link>
            <span v-if="USE_MOCK" class="mock-chip">MOCK 데이터</span>
        </nav>

        <router-view />
    </div>
</template>

<script setup>
import { USE_MOCK } from '@scripts/useAutoTrade.js';

const route = useRoute();
const router = useRouter();

const tabs = [
    { path: '/auto-trade/mode', label: '운용방식 설정' },
    { path: '/auto-trade/limit-order', label: '매도 수기 등록' },
    { path: '/auto-trade/status', label: '운용 현황' },
];

// /auto-trade 로 진입하면 첫 화면으로 보낸다
onMounted(() => {
    if (route.path === '/auto-trade' || route.path === '/auto-trade/') {
        router.replace(tabs[0].path);
    }
});
</script>

<style lang="scss" scoped>
// 무채색 팔레트(/trade 대시보드와 통일). 변수명은 유지, 값만 회색조로 교체.
$white: #ffffff;
$gray-50: #fafafa;
$gray-100: #efefef;
$gray-300: #c4c4c4;
$gray-500: #737373;
$gray-900: #141414;
$navy: #141414;
$amber: #141414;

#auto-trade-view {
    min-height: 100vh;
    background: $gray-50;
}

.at-tabs {
    display: flex;
    align-items: center;
    gap: 4px;
    max-width: 1000px;
    margin: 0 auto;
    padding: 14px 16px 0;

    .at-tab {
        padding: 9px 16px;
        font-size: .83rem;
        font-weight: 600;
        color: $gray-500;
        text-decoration: none;
        background: $white;
        border: 1px solid $gray-100;

        &.on {
            background: $navy;
            border-color: $navy;
            color: #fff;
        }
    }

    .mock-chip {
        margin-left: auto;
        font-size: .7rem;
        font-weight: 700;
        color: $gray-900;
        background: $gray-100;
        border: 1px solid $gray-300;
        padding: 4px 10px;
    }

    @media (max-width: 600px) {
        flex-wrap: wrap;

        .at-tab {
            padding: 8px 12px;
            font-size: .78rem;
        }
    }
}
</style>
