<template>
    <div id="stocks-view">
        <!-- 주식분석 하위 화면. /stock 으로 바로 오면 라우터 가드가 매수추천(/stock/buy-target)으로 보낸다
             (2026-11-15 주식분석 대시보드 → 매수추천으로 대체. StockDashboard.vue 는 지금 쓰지 않는다). -->
        <router-view />
    </div>
</template>
