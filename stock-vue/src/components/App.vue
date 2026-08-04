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
  background-color: #fff;
  margin: 0;
}
#app {
  height: 100%;
  font-family: "맑은 고딕", "Malgun Gothics", sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #f7f7f7;

}
</style>