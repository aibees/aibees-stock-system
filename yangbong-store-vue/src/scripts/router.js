import { createWebHistory, createRouter } from 'vue-router'
import { loadComponent } from './utils/componentLoader.js'
import aibeesApi from './aibeesApi.js'
import { assUserSession } from "./stores/user-stores";
import { ensureAccess } from "./useAccess.js";
import { consumeAdPass, countGateEntry, gateInterval } from "./useAdGate.js";
import { AD_GATE_MENU_CODES, AD_ENABLED } from "./adConfig.js";
import { isAuthPath, isGuestPath, INTRO_PATH, ONBOARDING_PATH, PICKS_PATH } from "./authPaths.js";
import { isIntroSeen } from "./introState.js";
import { usePersonaStore } from "./stores/persona-store.js";
import { NOTICE_DETAIL_PATH, NOTICE_LIST_PATH } from "./notice.js";
import AdGate from '@/components/AdGate.vue';
import NaverCallback from '@/components/NaverCallback.vue';
import SignupConsent from '@/components/SignupConsent.vue';
import Signup from '@/components/Signup.vue';

// ----- import components -----
// 홈은 간편/전문가 모드로 갈린다(HomeEntry). 기존 Home.vue 는 전문가 모드 화면으로 그대로 둔다.
import HomeEntry from '@/components/Home/HomeEntry.vue'
import Menu from '@/components/Menu.vue'
import Onboarding from '@/components/Home/Onboarding.vue'
import IntroPage from '@/components/Home/IntroPage.vue'
import FirstPicks from '@/components/Home/FirstPicks.vue'
import StockPreset from '@/components/Stocks/StockPreset.vue'
import TrainingHub from '@/components/Training/TrainingHub.vue'
import TrainingHome from '@/components/Training/TrainingHome.vue'
import TrainingGlossary from '@/components/Training/TrainingGlossary.vue'
import SupportFaq from '@/components/Support/SupportFaq.vue'
import SupportContact from '@/components/Support/SupportContact.vue'
import SupportDoc from '@/components/Support/SupportDoc.vue'
import TrainingQuizHome from '@/components/Training/TrainingQuizHome.vue'
import TrainingQuizPlay from '@/components/Training/TrainingQuizPlay.vue'
import TrainingLesson from '@/components/Training/TrainingLesson.vue'
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
        // 비로그인 접근 가능(authPaths.GUEST_PATHS). dynamic menu API 실패해도 항상 존재하도록 static 등록.
        path: "/home",
        name: "home",
        component: HomeEntry
    },
    {
        // 앱 소개. 앱 첫 실행 때 홈 앞에 한 번 나오고, 웹은 홈의 "처음이세요?"로 연다.
        path: INTRO_PATH,
        name: "intro",
        component: IntroPage
    },
    {
        // 첫 실행 결과: 내 조건에 맞는 종목 → 관심 종목 담기 → 알림 제안.
        path: PICKS_PATH,
        name: "first-picks",
        component: FirstPicks
    },
    {
        // 성향 질문(온보딩). 비로그인 접근 가능. ?pick=1 이면 질문 없이 유형 고르기 화면부터.
        path: ONBOARDING_PATH,
        name: "onboarding",
        component: Onboarding
    },
    {
        // 전체 메뉴. 트레이닝 항목은 정적이라 서버 메뉴 없이도 열린다(서버 메뉴가 있으면 그 아래에 이어 붙는다).
        path: "/menu",
        name: "menu",
        component: Menu
    },
    {
        // 내 설정(preset). 주식분석 그룹의 화면이지만 서버 메뉴와 무관한 정적 라우트(비로그인도 연다).
        path: "/stock/preset",
        name: "stock-preset",
        component: StockPreset
    },
    {
        // 트레이닝 첫 화면: 수업 듣기 · 퀴즈 · 용어 사전 입구. 비로그인 접근 가능(authPaths.GUEST_PREFIXES).
        path: "/training",
        name: "training",
        component: TrainingHub
    },
    {
        // 수업 목록(장 → 단계)
        path: "/training/lessons",
        name: "training-lessons",
        component: TrainingHome
    },
    {
        // 고객지원: 자주 묻는 질문 · 문의하기 · 이용약관 · 개인정보 처리방침. 비밀번호 없이 열린다(authPaths.GUEST_PREFIXES).
        path: "/support",
        redirect: "/support/faq"
    },
    { path: "/support/faq", name: "support-faq", component: SupportFaq },
    { path: "/support/contact", name: "support-contact", component: SupportContact },
    { path: "/support/terms", name: "support-terms", component: SupportDoc },
    { path: "/support/privacy", name: "support-privacy", component: SupportDoc },
    {
        path: "/training/glossary",
        name: "training-glossary",
        component: TrainingGlossary
    },
    {
        path: "/training/quiz",
        name: "training-quiz",
        component: TrainingQuizHome
    },
    {
        // all · wrong · today · <장 slug>
        path: "/training/quiz/:set",
        name: "training-quiz-play",
        component: TrainingQuizPlay
    },
    {
        // 장 바로가기(전체 메뉴의 장 항목·단계 화면의 뒤로): 같은 목차 화면을 그 장 위치로 연다(scrollBehavior).
        path: "/training/:chapter",
        name: "training-chapter",
        component: TrainingHome
    },
    {
        path: "/training/:chapter/:stage",
        name: "training-stage",
        component: TrainingLesson
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
    },
    {
        // 공지 짧은 주소: /notice/12 → 상세(/board/notice/detail?id=12), /notice → 목록.
        //   화면은 메뉴(Board) 라우트라 리다이렉트된 경로에서 권한 가드가 그대로 적용된다.
        path: "/notice/:id(\\d+)?",
        name: "notice-short",
        redirect: (to) => (to.params.id
            ? { path: NOTICE_DETAIL_PATH, query: { id: to.params.id } }
            : { path: NOTICE_LIST_PATH })
    }
]

// 라우트로 등록된 전체 메뉴 경로(로그인 전 전체 목록 기준). 이 중 사용자 권한에 없는
// 경로는 가드가 막는다. 목록에 없는 경로(정적 라우트, 404 등)는 권한 대상이 아니다.
let restrictedPaths = new Set();
// 광고 게이트 대상 경로(AD_GATE_MENU_CODES 의 메뉴). AD_FREE 가 없으면 진입 전에 광고를 본다.
let adGatedPaths = new Set();
// 메뉴 경로 → menu_code (메뉴 접근 기록용).
let menuCodeByPath = new Map();
// 접근 기록을 남기지 않는 화면(광고 게이트는 메뉴로 가는 중간 단계).
const NO_ACCESS_LOG_ROUTES = new Set(['NotFound', 'ad-gate']);

const normPath = (p) => '/' + String(p ?? '').replace(/^\/+/, '').replace(/\/+$/, '');

const getRouteList = async () => {
  try {
    const { data } = await aibeesApi.get('/api/v1/master/menus', { params: { enabled_flag: 'Y' } });
    const routerResult = data.data;
    const userSession = assUserSession();
    userSession.setMenuList(routerResult);

    restrictedPaths = new Set();
    adGatedPaths = new Set();
    menuCodeByPath = new Map();
    routerResult.forEach(r => {
        restrictedPaths.add(normPath(r.menu_path));
        menuCodeByPath.set(normPath(r.menu_path), r.menu_code);
        (r.children ?? []).forEach(c => {
            const full = normPath(r.menu_path) + normPath(c.menu_path);
            restrictedPaths.add(full);
            menuCodeByPath.set(full, c.menu_code);
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

// 로그인 없이 열 수 있는 화면은 로그인·가입 흐름과 홈·온보딩뿐이다(authPaths.js). 나머지는 전부 로그인 필요.
//   (2026-10-10 에 홈까지 로그인 전용으로 막았다가 2026-11-15 "가입 없이 홈 전체 공개" 결정으로 다시 열었다)

export const setRouterToApp = async () => {
    const dynamicRoutes = await getRouteList();
    const router = createRouter({
      history: createWebHistory(),
      routes: [...routes],
      // 화면이 바뀌면 뒤로가기를 포함해 항상 맨 위에서 시작한다. 없으면 이전 화면의 스크롤 위치가 그대로 남는다.
      // 쿼리만 바뀌는 같은 화면 안의 이동은 읽던 위치를 유지한다.
      scrollBehavior(to, from) {
        if (to.path === from.path) return false;
        // 트레이닝 장 바로가기는 그 장 제목으로(고정 머리글 높이만큼 띄운다). 없는 장이면 맨 위.
        if (to.name === 'training-chapter' && document.getElementById(`ch-${to.params.chapter}`)) {
            return { el: `#ch-${to.params.chapter}`, top: 84 };
        }
        return { top: 0, left: 0 };
      },
    });

    dynamicRoutes.forEach(d => {
        // /home·/menu 는 위에서 static 으로 등록했으므로 중복 방지
        if (['/home', 'home', '/menu', 'menu'].includes(d.path)) return;
        router.addRoute(d);
    });

    // ── 전역 네비게이션 가드 ──
    router.beforeEach(async (to, from) => {
        const userSession = assUserSession();
        const loggedIn = userSession.isUserSession();
        const isAuth = isAuthPath(to.path);
        const target = normPath(to.path);

        // 주식분석(/stock)으로 바로 오면 매수추천을 연다(2026-11-15: 주식분석 대시보드 → 매수추천으로 대체).
        //   하단 탭·각 화면의 뒤로(back="/stock")가 모두 여기로 온다. 이동한 뒤 권한·광고 게이트는 매수추천 기준으로 다시 본다.
        if (target === '/stock') return { path: '/stock/buy-target', query: to.query, replace: true };

        const isGuest = isGuestPath(target);

        if (!loggedIn) {
            // 비로그인: 로그인·가입 흐름은 그대로, 홈·온보딩은 게스트로 연다. 나머지는 모두 로그인 화면으로.
            if (isAuth) return true;
            if (!isGuest) return { path: '/login' };
        } else if (to.path === '/login' || to.path === '/signup') {
            // 로그인 상태에서 로그인·가입 화면으로 오면 홈으로(네이버 콜백·동의 화면은 흐름 중이라 그대로 둔다).
            return { path: '/home' };
        }

        // 권한(메뉴/기능)을 받는다. Lnb 가 sessionStorage 의 menuList 를 읽는데 그 값이 권한 반영본이어야 한다.
        // 비로그인이면 게스트 권한(공개 메뉴·설정값)을 받는다 — 광고 노출과 성향 설정(공통코드)이 이 값을 쓴다.
        // 받아 둔 권한이 로그인 상태와 어긋나면(예: 게스트 때 받은 권한이 남음) 다시 받는다.
        const stale = userSession.access.loaded && userSession.access.asGuest === loggedIn;
        const access = isAuth ? null : await ensureAccess(stale);
        const allowed = !!access && access.paths.includes(target);
        const isMenuPath = restrictedPaths.has(target);

        // 권한(role_menu)에 없는 메뉴. 게스트 화면(홈·온보딩)은 메뉴 권한과 무관하게 열린다.
        if (!isAuth && !isGuest && isMenuPath && !allowed) {
            alert("접근 권한이 없는 메뉴입니다.");
            return { path: '/home' };
        }

        // 성향: 로그인 상태의 첫 이동 때 계정 저장값과 맞춘다(새 기기에서 로그인하면 계정 값을 받아 온다).
        //   이미 맞췄으면 바로 돌아온다. 실패해도 기기 값으로 진행한다.
        const persona = usePersonaStore();
        if (loggedIn) await persona.syncWithAccount();

        // 처음 실행: 홈으로 들어올 때 앱 소개 → 성향 질문 순서로 한 번 연다(권한을 받은 뒤라 매매 사용자는 제외된다).
        if (target === '/home' && persona.needsOnboarding()) {
            return { path: isIntroSeen() ? ONBOARDING_PATH : INTRO_PATH };
        }

        // 광고 게이트: 접근이 허용된 게이트 대상 메뉴에 들어올 때. AD_FREE 보유자는 건너뛴다.
        //   같은 메뉴 안에서 쿼리만 바뀌는 이동(종목 검색·기간 변경)은 재입장이 아니라 묻지 않는다.
        //   게이트에서 광고를 다 보면 이 경로 전용 1회용 통과권이 생기고, 여기서 소모된다.
        const entering = normPath(from.path) !== target;
        //   N번에 한 번만: 진입마다 사용자별로 세고 N 에 닿았을 때만 게이트로(광고 보고 돌아온 진입은 세지 않는다).
        //   게이트(/ad-gate)는 로그인 전용이라 비로그인(게스트)에는 걸지 않는다 — 걸면 로그인 화면으로 튕긴다(게스트 화면의 광고는 홈 띠 배너가 맡는다).
        if (AD_ENABLED && loggedIn && access?.loaded && allowed && adGatedPaths.has(target) && entering
            && !access.features.includes('AD_FREE') && !consumeAdPass(target)
            && countGateEntry(userSession.user.loginInfo.user_id, gateInterval(access.settings))) {
            return { path: '/ad-gate', query: { next: to.fullPath } };
        }
    });

    // ── 메뉴(화면) 접근 기록 ──
    //   로그인 사용자가 다른 화면으로 들어왔을 때만 1건(같은 화면 안의 쿼리 변경은 세지 않는다).
    //   기록 실패는 화면 이동과 무관하므로 무시한다.
    router.afterEach((to, from, failure) => {
        if (failure || NO_ACCESS_LOG_ROUTES.has(to.name) || isAuthPath(to.path)) return;
        if (!assUserSession().isUserSession()) return;
        const target = normPath(to.path);
        if (from.matched.length && normPath(from.path) === target) return;
        aibeesApi.post('/api/v1/access-logs/menu', { path: target, menuCode: menuCodeByPath.get(target) ?? null })
            .catch(() => { /* ignore */ });
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
