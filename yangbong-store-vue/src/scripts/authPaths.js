/**
 * 로그인 없이 열 수 있는 화면 정의.
 * 라우터 가드(router.js), 하단 탭바 숨김(App.vue), 광고 숨김(useAds.js)이 같이 쓴다.
 */

/** 로그인·가입 흐름. 로그인한 사용자가 /login·/signup 으로 오면 홈으로 보낸다. */
export const AUTH_PATHS = ['/login', '/signup', '/find-account', '/oauth/naver', '/oauth/naver/consent'];

export const isAuthPath = (path) => AUTH_PATHS.includes(path);

/** 성향 질문(온보딩). 처음 실행할 때 한 번 자동으로 열리고, 홈의 "처음이세요?"로 다시 연다. */
export const ONBOARDING_PATH = '/onboarding';

/** 앱 소개. 앱을 처음 열 때 성향 질문 앞에 한 번 나온다. */
export const INTRO_PATH = '/intro';

/** 성향 질문 뒤 첫 결과: 내 조건에 맞는 종목과 관심 종목 담기. */
export const PICKS_PATH = '/start';

/**
 * 로그인·가입 흐름 말고 비로그인에게 열리는 화면: 홈과 온보딩(2026-11-15 "가입 없이 홈 전체 공개").
 * 홈이 부르는 API(시황·공지·주목 종목·성과)는 서버에서도 비로그인을 허용한다. 이 밖의 화면은 로그인해야 열린다.
 */
// 홈에서 이어지는 화면(매수추천·공지)도 연다 — 안 그러면 홈의 "전체 보기"·공지를 누른 비로그인이 로그인 화면으로 튕긴다.
// 종목 상세(/stock/info)는 넣지 않는다(2026-11-20) — 재무·뉴스·AI 분석이 로그인 사용자용이라 비로그인은 로그인 화면으로 안내한다.
export const GUEST_PATHS = ['/home', INTRO_PATH, ONBOARDING_PATH, PICKS_PATH, '/menu', '/stock', '/stock/preset', '/stock/persona', '/stock/buy-target', '/stock/chart', '/board/notice', '/board/notice/detail'];

/** 트레이닝(/training, /training/<장>, /training/<장>/<단계>)도 가입 없이 연다. 메뉴 권한과 무관한 정적 라우트다. */
export const GUEST_PREFIXES = ['/training', '/support'];

export const isGuestPath = (path) =>
    GUEST_PATHS.includes(path) || GUEST_PREFIXES.some(p => path === p || path.startsWith(p + '/'));

/**
 * 로그인 뒤 돌아갈 곳. 라우터 가드가 비로그인을 로그인 화면으로 보낼 때 가려던 주소를 기억하고,
 * 로그인이 끝나는 곳(이메일·구글·네이버·가입 동의)이 꺼내 쓴다. 한 번 꺼내면 지운다.
 * 네이버는 외부 페이지를 다녀오므로 sessionStorage 에 둔다. 이 사이트 안의 경로('/x', '//' 아님)만 받는다.
 */
const AFTER_LOGIN_KEY = 'afterLogin';
const isSafeInternal = (p) => typeof p === 'string' && p.startsWith('/') && !p.startsWith('//') && !isAuthPath(p.split('?')[0]);
export const rememberAfterLogin = (fullPath) => {
    try { if (isSafeInternal(fullPath)) sessionStorage.setItem(AFTER_LOGIN_KEY, fullPath); } catch { /* 저장 못 하면 홈으로 */ }
};
export const takeAfterLogin = () => {
    try {
        const p = sessionStorage.getItem(AFTER_LOGIN_KEY);
        sessionStorage.removeItem(AFTER_LOGIN_KEY);
        return isSafeInternal(p) ? p : null;
    } catch { return null; }
};

/** 탭바·광고 없이 그 화면에만 집중하는 경로: 로그인·가입 흐름, 앱 소개, 온보딩. */
export const isFocusPath = (path) => isAuthPath(path) || path === ONBOARDING_PATH || path === INTRO_PATH || path === PICKS_PATH;
