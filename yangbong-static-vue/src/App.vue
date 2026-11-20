<template>
  <header class="site-head">
    <div class="wrap">
      <RouterLink to="/" class="brand">
        <img src="@/logo.svg" alt="" width="28" height="28" />
        <span>양봉상회</span>
      </RouterLink>
      <nav>
        <RouterLink :to="{ path: '/', hash: '#install' }">앱 설치하기</RouterLink>
      </nav>
    </div>
  </header>

  <RouterView />

  <footer class="site-foot">
    <div class="wrap">
      <nav>
        <RouterLink to="/terms">이용약관</RouterLink>
        <RouterLink to="/privacy"><strong>개인정보 처리방침</strong></RouterLink>
      </nav>
      <p>운영: 차곡랩스 · 문의 <a :href="`mailto:${CONTACT}`">{{ CONTACT }}</a></p>
      <p>© 2026 차곡랩스 (chagoklabs)</p>
    </div>
  </footer>
</template>

<script setup>
import { CONTACT } from './site.js';
</script>

<style scoped>
.site-head { border-bottom: 1px solid var(--line); background: var(--bg); }
.site-head .wrap { display: flex; align-items: center; justify-content: space-between; height: 56px; }
.brand { display: inline-flex; align-items: center; gap: 8px; color: var(--ink); font-weight: 700; font-size: 17px; text-decoration: none; }
.site-head nav a { color: var(--sub); font-size: 14px; text-decoration: none; }
.site-head nav a:hover { color: var(--ink); }

.site-foot { border-top: 1px solid var(--line); color: var(--sub); font-size: 13px; }
.site-foot .wrap { padding-top: 24px; padding-bottom: 40px; }
.site-foot nav { display: flex; gap: 16px; margin-bottom: 10px; }
.site-foot nav a { color: var(--sub); text-decoration: none; }
.site-foot nav a:hover { color: var(--ink); }
.site-foot nav strong { color: var(--ink); font-weight: 600; }
.site-foot p { margin: 2px 0; }
.site-foot p a { color: inherit; }
</style>
