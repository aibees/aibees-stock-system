import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

// 양봉상회 소개·정책 페이지(정적). API 호출이 없어서 .env 가 필요 없다.
// https://yangbong.chagoklabs.com 루트(/)에서 서빙한다 — 하위 경로로 옮기면 base 를 그 경로로 바꿔야 한다.
export default defineConfig({
  base: '/',
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: { host: '0.0.0.0', port: 19014 },
});
