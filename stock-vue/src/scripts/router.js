import { createWebHistory, createRouter } from 'vue-router'
import { loadComponent } from './utils/componentLoader.js'
import aibeesApi from './aibeesApi.js'
import { assUserSession } from "./stores/user-stores";

// ----- import components -----
import Home from '@/components/Home.vue'
import Login from '@/components/Login.vue'
import App from '@/components/App.vue'
import Group from '@/components/StocksGroup.vue';
import UserOption from '@/components/UserOption.vue';
import NotFound from '@/components/except/NotFound.vue'
// -----------------------------

const routes = [
    {
        path: "/:catchAll(.*)",
        name: "NotFound",
        component: NotFound
    },
    {
        path: "/",
        name: "root",
        component: App,
        redirect: '/home'
    },
    {
        // 비로그인 접근 가능. dynamic menu API 실패해도 항상 존재하도록 static 등록.
        path: "/home",
        name: "home",
        component: Home
    },
    {
        path: "/login",
        name: "login",
        component: Login
    },
    {
        path: "/group",
        name: "group",
        component: Group
    },
    {
        path: "/user-option",
        name: "user-option",
        component: UserOption
    }
]

const getRouteList = async () => {
  try {
    const { data } = await aibeesApi.get('/api/v1/master/menus', { params: { enabled_flag: 'Y' } });
    const routerResult = data.data;
    const userSession = assUserSession();
    userSession.setMenuList(routerResult);

    let saRouter = [];

    routerResult.forEach(r => {
        let tmp = {}
        tmp.path = r.menu_path;
        tmp.name = r.menu_name;
        tmp.component = loadComponent(r);
        
        let child = []
        if ('children' in r) {
            r.children.forEach(c => {                
                let childTmp = {}
                let meta = {}
                childTmp.path = c.menu_path;
                childTmp.name = c.menu_name;
                childTmp.component = loadComponent(c)
                meta.title = c.menu_title;
                // set meta
                childTmp.meta = meta;
                child.push(childTmp);
            });
        }
        tmp.children = child;
        saRouter.push(tmp);
    });

    return saRouter;
  } catch (e) {
    // 비로그인 등으로 메뉴 로드 실패해도 앱은 뜨도록 빈 라우트로 진행
    console.error('[router] 메뉴 목록 로드 실패, 빈 라우트로 진행', e);
    return [];
  }
}

// 로그인 없이 접근 가능한 화이트리스트
const PUBLIC_PATHS = ['/login', '/', '/home'];

export const setRouterToApp = async () => {
    const dynamicRoutes = await getRouteList();
    const router = createRouter({
      history: createWebHistory(),
      routes: [...routes],
    });

    dynamicRoutes.forEach(d => {
        // /home 은 위에서 static 으로 등록했으므로 중복 방지
        if (d.path === '/home' || d.path === 'home') return;
        router.addRoute(d);
    });

    // ── 전역 네비게이션 가드 ──
    router.beforeEach((to) => {
        const userSession = assUserSession();
        const isPublic = PUBLIC_PATHS.includes(to.path);

        if (!isPublic && !userSession.isUserSession()) {
            alert("로그인 이후 이용 가능합니다.");
            return { path: '/login' };
        }
    });

    // ── 배포 후 구버전 chunk 로드 실패 대응 ──
    //   재배포로 assets 해시가 바뀌면, 이미 열려있던 탭(구 index.js)이 없는 chunk 를 요청하고
    //   서버는 SPA fallback 으로 index.html(text/html) 을 돌려줘 dynamic import 가 실패한다.
    //   이동하려던 경로로 1회 전체 새로고침해 새 index.html/asset 을 받게 한다
    //   (sessionStorage 플래그로 무한 새로고침 방지 — 새로고침 후에도 실패하면 진짜 오류).
    const CHUNK_RELOAD_KEY = 'chunk-reload-at';
    const isChunkLoadError = (err) => /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i
        .test(String(err?.message || err));
    router.onError((err, to) => {
        if (!isChunkLoadError(err)) return;
        let last = 0;
        try { last = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) || 0); } catch (_) { /* ignore */ }
        if (Date.now() - last < 10_000) return;   // 직전에 이미 새로고침함 → 루프 방지
        try { sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now())); } catch (_) { /* ignore */ }
        window.location.assign(to?.fullPath || window.location.href);
    });

    return router;
}
