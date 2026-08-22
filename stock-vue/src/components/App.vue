<script setup>
import Lnb from './common/Lnb.vue';
</script>

<template>
  <div>
    <Lnb />
    <router-view />
  </div>
</template>

<style lang="scss">
@use '@@/__variables.scss' as *;
body {
  height: 100%;
  background-color: #1a1a1a;
  margin: 0;

}
#app {
  height: 100%;
  font-family: "맑은 고딕", "Malgun Gothics", sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #f7f7f7;

  /* 상하좌우 노치 및 홈 바 영역 자동 대응 */
  padding-top: env(safe-area-inset-top);
  // padding-bottom: env(safe-area-inset-bottom);
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
</style>