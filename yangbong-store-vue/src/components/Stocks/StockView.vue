<template>
    <div id="stocks-view">
        <!-- /stock 으로 바로 오면 주식분석 허브(매수추천·AI 분석·차트 확인)를 보여준다 -->
        <router-view v-slot="{ Component }">
            <component :is="Component" v-if="Component" />
            <StockDashboard v-else />
        </router-view>
    </div>
</template>

<script setup>
import StockDashboard from './StockDashboard.vue';
</script>
