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

    // [수정] 메뉴 1건의 컴포넌트 해석 실패가 **전체 라우트**를 날려버리던 문제.
    //   loadComponent() 는 번들에 해당 .vue 가 없으면 throw 한다. 예전에는 그 예외가
    //   forEach 를 타고 아래 catch 까지 올라가 return [] 이 되어, 멀쩡한 메뉴까지
    //   전부 라우트 미등록 상태가 됐다. setMenuList() 는 그 전에 이미 끝나므로
    //   "메뉴는 보이는데 누르면 NotFound" 라는 진단하기 어려운 증상이 된다.
    //   실제로 master_menu 에 행을 넣고 프런트를 아직 재배포하지 않은 동안
    //   앱 전체 메뉴가 죽었다(2026-10-03, TradeProfit).
    //   DB 메뉴 등록과 프런트 배포는 원래 시점이 어긋날 수 있으므로, 못 찾은
    //   메뉴만 건너뛰고 나머지는 정상 등록한다.
    const safeComponent = (m) => {
        try {
            return loadComponent(m);
        } catch (e) {
            console.error(`[router] 컴포넌트 없음 → 메뉴 건너뜀: ${m.menu_code}/${m.menu_component}`, e);
            return null;
        }
    };

    routerResult.forEach(r => {
        let tmp = {}
        tmp.path = r.menu_path;
        tmp.name = r.menu_name;
        tmp.component = safeComponent(r);

        let child = []
        if ('children' in r) {
            r.children.forEach(c => {
                const childComponent = safeComponent(c);
                if (!childComponent) return;   // 이 자식만 건너뛴다
                let childTmp = {}
                let meta = {}
                childTmp.path = c.menu_path;
                childTmp.name = c.menu_name;
                childTmp.component = childComponent;
                meta.title = c.menu_title;
                // set meta
                childTmp.meta = meta;
                child.push(childTmp);
            });
        }
        tmp.children = child;
        // 부모 컴포넌트를 못 찾으면 자식까지 띄울 수 없다(router-view 가 없음) → 통째로 skip.
        if (!tmp.component) {
            console.error(`[router] 부모 컴포넌트 없음 → 하위 메뉴까지 건너뜀: ${r.menu_code}`);
            return;
        }
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
