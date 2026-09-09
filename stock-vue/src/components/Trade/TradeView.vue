<template>
    <div id="trade-view">
        <router-view v-slot="{ Component }">
            <component :is="Component" v-if="Component" />
            <TradeDashboard v-else />
        </router-view>
    </div>
</template>

<script setup>
import TradeDashboard from './TradeDashboard.vue';
</script>

<style lang="scss" scoped>

</style>