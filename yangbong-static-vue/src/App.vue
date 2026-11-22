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
      <a class="made" :href="CHAGOK_URL" rel="noopener">
        <svg width="22" height="16" viewBox="0 0 104 76" aria-hidden="true"><rect x="2" y="56" width="100" height="18" rx="3" fill="#11213A" opacity=".22"/><rect x="6" y="30" width="100" height="18" rx="3" fill="#11213A" opacity=".48"/><rect x="0" y="4" width="100" height="18" rx="3" fill="#E8A33D"/></svg>
        Chagok Labs<em>가 만듭니다 →</em>
      </a>
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
import { CONTACT, CHAGOK_URL } from './site.js';
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
.made {
  display: inline-flex; align-items: center; gap: 8px; margin-bottom: 18px; padding: 9px 13px;
  border: 1px solid var(--line); border-radius: 10px; color: var(--ink); font-size: 14px; font-weight: 700; text-decoration: none;
}
.made em { font-style: normal; color: var(--sub); font-weight: 600; }
.made:hover { border-color: var(--brand); }
.site-foot p a { color: inherit; }
</style>
