<template>
    <div id="board-view">
        <!-- /board 로 바로 오면 공지사항 목록을 보여준다 -->
        <router-view v-slot="{ Component }">
            <component :is="Component" v-if="Component" />
            <NoticeList v-else />
        </router-view>
    </div>
</template>

<script setup>
import NoticeList from './NoticeList.vue';
</script>
