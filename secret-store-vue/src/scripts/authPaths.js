/**
 * 로그인 전에 열 수 있는 화면(= 로그인·가입 흐름) 목록. 이 외의 모든 화면은 로그인해야 열린다.
 * 라우터 가드(router.js), 하단 탭바 숨김(App.vue), 광고 숨김(useAds.js)이 같이 쓴다.
 */
export const AUTH_PATHS = ['/login', '/signup', '/oauth/naver', '/oauth/naver/consent'];

export const isAuthPath = (path) => AUTH_PATHS.includes(path);
