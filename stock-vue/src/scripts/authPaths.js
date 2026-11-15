/**
 * 로그인 없이 열 수 있는 화면 정의.
 * 라우터 가드(router.js), 하단 탭바 숨김(App.vue), 광고 숨김(useAds.js)이 같이 쓴다.
 */

/** 로그인·가입 흐름. 로그인한 사용자가 /login·/signup 으로 오면 홈으로 보낸다. */
export const AUTH_PATHS = ['/login', '/signup', '/oauth/naver', '/oauth/naver/consent'];

export const isAuthPath = (path) => AUTH_PATHS.includes(path);

/** 성향 질문(온보딩). 처음 실행할 때 한 번 자동으로 열리고, 홈의 "처음이세요?"로 다시 연다. */
export const ONBOARDING_PATH = '/onboarding';

/**
 * 로그인·가입 흐름 말고 비로그인에게 열리는 화면: 홈과 온보딩(2026-11-15 "가입 없이 홈 전체 공개").
 * 홈이 부르는 API(시황·공지·주목 종목·성과)는 서버에서도 비로그인을 허용한다. 이 밖의 화면은 로그인해야 열린다.
 */
export const GUEST_PATHS = ['/home', ONBOARDING_PATH];

export const isGuestPath = (path) => GUEST_PATHS.includes(path);

/** 탭바·광고 없이 그 화면에만 집중하는 경로: 로그인·가입 흐름과 온보딩. */
export const isFocusPath = (path) => isAuthPath(path) || path === ONBOARDING_PATH;
