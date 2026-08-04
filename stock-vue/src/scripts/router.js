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

    return router;
}
