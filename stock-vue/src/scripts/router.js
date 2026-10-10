import { createWebHistory, createRouter } from 'vue-router'
import { loadComponent } from './utils/componentLoader.js'
import aibeesApi from './aibeesApi.js'
import { assUserSession } from "./stores/user-stores";
import { ensureAccess } from "./useAccess.js";
import { consumeAdPass } from "./useAdGate.js";
import { AD_GATE_MENU_CODES, AD_ENABLED } from "./adConfig.js";
import { isAuthPath } from "./authPaths.js";
import AdGate from '@/components/AdGate.vue';
import NaverCallback from '@/components/NaverCallback.vue';
import SignupConsent from '@/components/SignupConsent.vue';
import Signup from '@/components/Signup.vue';

// ----- import components -----
import Home from '@/components/Home.vue'
import Login from '@/components/Login.vue'
import App from '@/components/App.vue'
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
        // 광고 게이트. 로그인 필요(PUBLIC_PATHS 아님). 가드가 AD_FREE 없는 사용자를 여기로 보낸다.
        path: "/ad-gate",
        name: "ad-gate",
        component: AdGate
    },
    {
        // 네이버 로그인 콜백(code/state 를 서버로 넘겨 로그인/연결/가입). 비로그인 공개 경로.
        path: "/oauth/naver",
        name: "naver-callback",
        component: NaverCallback
    },
    {
        // 네이버 가입 — 개인정보 처리방침 동의(동의해야 토큰 발급). 비로그인 공개 경로.
        path: "/oauth/naver/consent",
        name: "signup-consent",
        component: SignupConsent
    },
    {
        // 이메일 회원가입(인증코드 + 항목별 동의). 비로그인 공개 경로.
        path: "/signup",
        name: "signup",
        component: Signup
    },
    {
        path: "/user-option",
        name: "user-option",
        component: UserOption
    }
]

// 라우트로 등록된 전체 메뉴 경로(로그인 전 전체 목록 기준). 이 중 사용자 권한에 없는
// 경로는 가드가 막는다. 목록에 없는 경로(정적 라우트, 404 등)는 권한 대상이 아니다.
let restrictedPaths = new Set();
// 광고 게이트 대상 경로(AD_GATE_MENU_CODES 의 메뉴). AD_FREE 가 없으면 진입 전에 광고를 본다.
let adGatedPaths = new Set();

const normPath = (p) => '/' + String(p ?? '').replace(/^\/+/, '').replace(/\/+$/, '');

const getRouteList = async () => {
  try {
    const { data } = await aibeesApi.get('/api/v1/master/menus', { params: { enabled_flag: 'Y' } });
    const routerResult = data.data;
    const userSession = assUserSession();
    userSession.setMenuList(routerResult);

    restrictedPaths = new Set();
    adGatedPaths = new Set();
    routerResult.forEach(r => {
        restrictedPaths.add(normPath(r.menu_path));
        (r.children ?? []).forEach(c => {
            const full = normPath(r.menu_path) + normPath(c.menu_path);
            restrictedPaths.add(full);
            if (AD_GATE_MENU_CODES.includes(c.menu_code)) adGatedPaths.add(full);
        });
    });

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

// 로그인 없이 열 수 있는 화면은 로그인·가입 흐름뿐이다(authPaths.js). 홈을 포함한 나머지는 전부 로그인 필요.

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
    router.beforeEach(async (to, from) => {
        const userSession = assUserSession();
        const loggedIn = userSession.isUserSession();
        const isAuth = isAuthPath(to.path);
        const target = normPath(to.path);

        // 비로그인: 로그인·가입 화면만 연다. 나머지는 모두 로그인 화면으로.
        if (!loggedIn) {
            return isAuth ? true : { path: '/login' };
        }
        // 로그인 상태에서 로그인·가입 화면으로 오면 홈으로(네이버 콜백·동의 화면은 흐름 중이라 그대로 둔다).
        if (to.path === '/login' || to.path === '/signup') {
            return { path: '/home' };
        }

        // 권한(메뉴/기능)을 받는다. Lnb 가 sessionStorage 의 menuList 를 읽는데 그 값이 권한 반영본이어야 한다.
        // 받아 둔 권한이 로그인 상태와 어긋나면(예: 게스트 때 받은 권한이 남음) 다시 받는다.
        const stale = userSession.access.loaded && userSession.access.asGuest === loggedIn;
        const access = isAuth ? null : await ensureAccess(stale);
        const allowed = !!access && access.paths.includes(target);
        const isMenuPath = restrictedPaths.has(target);

        // 로그인했지만 권한(role_menu)에 없는 메뉴.
        if (!isAuth && isMenuPath && !allowed) {
            alert("접근 권한이 없는 메뉴입니다.");
            return { path: '/home' };
        }

        // 광고 게이트: 접근이 허용된 게이트 대상 메뉴에 "들어올 때마다". AD_FREE 보유자는 건너뛴다.
        //   같은 메뉴 안에서 쿼리만 바뀌는 이동(종목 검색·기간 변경)은 재입장이 아니라 묻지 않는다.
        //   게이트에서 광고를 다 보면 이 경로 전용 1회용 통과권이 생기고, 여기서 소모된다.
        const entering = normPath(from.path) !== target;
        if (AD_ENABLED && access?.loaded && allowed && adGatedPaths.has(target) && entering
            && !access.features.includes('AD_FREE') && !consumeAdPass(target)) {
            return { path: '/ad-gate', query: { next: to.fullPath } };
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
