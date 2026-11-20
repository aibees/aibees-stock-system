import { createRouter, createWebHistory } from 'vue-router';
import Home from './pages/Home.vue';

// 앱 심사·스토어 등록에 쓰는 주소라 경로를 바꾸지 않는다: /privacy, /terms
const routes = [
  { path: '/', name: 'home', component: Home, meta: { title: '양봉상회' } },
  { path: '/privacy', name: 'privacy', component: () => import('./pages/Privacy.vue'), meta: { title: '개인정보 처리방침 | 양봉상회' } },
  { path: '/terms', name: 'terms', component: () => import('./pages/Terms.vue'), meta: { title: '이용약관 | 양봉상회' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, saved) {
    if (saved) return saved;
    if (to.hash) return { el: to.hash };
    return { top: 0 };
  },
});

router.afterEach((to) => {
  document.title = to.meta.title || '양봉상회';
});

export default router;
