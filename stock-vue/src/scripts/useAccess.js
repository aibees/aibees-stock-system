/**
 * 접근 권한(메뉴/기능) 로더.
 *
 * 서버가 정본이다: GET /api/v1/master/menus/my 가 로그인 사용자의 권한(user_auth)으로
 * 접근 가능한 메뉴 트리와 기능 플래그(features)를 내려준다.
 *
 * 라우트 등록(router.js)은 로그인 전에 전체 메뉴로 하므로, 접근 제어는 여기서 받은
 * 목록으로 네비게이션 가드와 메뉴 노출에서 한다. 메뉴를 숨기는 것은 보안 경계가
 * 아니다 — 데이터 API 의 권한 검사는 서버(@require_auth 등)가 따로 맡는다.
 *
 * state 는 스토어에 두고 이 파일은 aibeesApi 와 스토어를 잇기만 한다
 * (aibeesApi 가 스토어를 import 하므로 스토어가 aibeesApi 를 import 하면 순환).
 */
import aibeesApi from './aibeesApi.js';
import { assUserSession } from './stores/user-stores.js';

const norm = (p) => String(p ?? '').replace(/^\/+/, '').replace(/\/+$/, '');

// 트리 → 이동 허용 경로. 부모는 '/trade', 리프는 '/trade/profit'.
const collectPaths = (menus) => {
    const paths = [];
    for (const m of menus) {
        paths.push('/' + norm(m.menu_path));
        for (const c of (m.children ?? [])) {
            paths.push('/' + norm(m.menu_path) + '/' + norm(c.menu_path));
        }
    }
    return paths;
};

let inflight = null;

/** 권한을 (아직 안 받았으면) 받아 스토어에 채운다. 실패하면 빈 권한(fail-closed)으로 둔다. */
export const ensureAccess = async (force = false) => {
    const store = assUserSession();
    if (store.access.loaded && !force) return store.access;
    if (inflight) return inflight;

    inflight = (async () => {
        // 토큰이 있으면 로그인 사용자 권한, 없으면 게스트(공개 메뉴) 권한을 받게 된다.
        const guest = !store.user.accessToken;
        try {
            const { data } = await aibeesApi.get('/api/v1/master/menus/my', {
                params: { enabled_flag: 'Y' }
            });
            const menus = data.data?.menus ?? [];
            store.access.paths    = collectPaths(menus);
            store.access.features = data.data?.features ?? [];
            store.access.roles    = data.data?.roles ?? [];
            store.access.settings = data.data?.settings ?? {};
            // Lnb / TradeDashboard 가 sessionStorage 의 menuList 를 읽으므로 권한이 반영된
            // 트리로 덮어쓴다(전체 목록은 router.js 가 따로 들고 있다).
            store.setMenuList(menus);
            store.access.asGuest = guest;
            store.access.loaded = true;
        } catch (e) {
            console.error('[access] 권한 로드 실패 — 제한 메뉴 접근을 막는다', e);
            store.access.paths    = [];
            store.access.features = [];
            store.access.roles    = [];
            store.access.settings = {};
            store.access.loaded   = false; // 다음 이동 때 재시도
            store.setMenuList([]);         // 전체 목록이 메뉴에 노출되지 않게 비운다
        } finally {
            inflight = null;
        }
        return store.access;
    })();
    return inflight;
};

/** 기능 플래그 보유 여부. 예) hasFeature('AD_FREE') */
export const hasFeature = (code) => assUserSession().access.features.includes(code);

/**
 * 권한(role) 보유 여부. 예) hasRole('WORKER_USER')
 * 대소문자는 구분하지 않는다. ADMIN 이라고 다른 권한을 자동으로 갖지는 않는다(AD_FREE 와 같은 원칙) —
 * 필요하면 그 사용자에게 해당 권한을 따로 부여한다.
 */
export const hasRole = (code) =>
    assUserSession().access.roles.some(r => String(r).toUpperCase() === String(code).toUpperCase());

export const WORKER_ROLE = 'WORKER_USER';
