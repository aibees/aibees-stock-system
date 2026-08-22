import { defineStore } from "pinia";
import { reactive, computed } from "vue";

// [수정] 자동로그인 저장소를 cookie → localStorage 로 변경.
// 원인: Capacitor iOS WebView는 커스텀 스킴(capacitor://localhost) 위에서
// 뜨는데, 이 환경에서 document.cookie 로 설정한 쿠키가 앱을 완전히
// 종료했다 재실행하면 디스크에 정상적으로 유지되지 않는 케이스가 있음
// (실사용자 확인: "아이디 기억하기"(localStorage)는 되는데 "자동로그인"
// (cookie)만 안 됨 — 정확히 이 증상과 일치). localStorage는 WKWebView에서
// 안정적으로 영속되므로, 만료 개념만 직접 구현해서(AUTO_LOGIN_MS) 대체한다.
const AUTO_LOGIN_MS = 30 * 24 * 60 * 60 * 1000; // 30일

const saveAutoLogin = (userObj) => {
    localStorage.setItem('userSession', JSON.stringify({
        user: userObj,
        expiresAt: Date.now() + AUTO_LOGIN_MS
    }));
};

const loadAutoLogin = () => {
    const raw = localStorage.getItem('userSession');
    if (!raw) return null;
    try {
        const wrapper = JSON.parse(raw);
        if (!wrapper?.expiresAt || wrapper.expiresAt <= Date.now()) {
            localStorage.removeItem('userSession'); // 30일 지남 — 정리
            return null;
        }
        return wrapper.user ?? null;
    } catch {
        localStorage.removeItem('userSession');
        return null;
    }
};

const clearAutoLogin = () => localStorage.removeItem('userSession');

export const assUserSession = defineStore('user', () => {

    const user = reactive({
        loginInfo: {
            user_id: '',
            user_name: '',
            role: []
        },
        expireTime: null,
        accessToken: '',
        refreshToken: '',   // [추가] refresh token 필드
        menuList: []
    });

    const getUserInfo = computed(() => user.loginInfo.user_name);
    const getRole    = computed(() => user.loginInfo.role);

    // ──────────────────────────────────────────────
    // [추가] JWT payload 디코딩 (라이브러리 없이 순수 JS)
    // JWT는 header.payload.signature 구조이며,
    // payload는 Base64URL 인코딩된 JSON 문자열이다.
    // ──────────────────────────────────────────────
    const decodeJwt = (token) => {
        try {
            const base64 = token.split('.')[1]
                .replace(/-/g, '+')   // Base64URL → Base64 변환
                .replace(/_/g, '/');
            return JSON.parse(atob(base64));
        } catch {
            return null;
        }
    };

    // ──────────────────────────────────────────────
    // [수정] isUserSession
    // - refreshToken 도 세션에서 복원
    // - expireTime 비교를 new Date() 로 변경
    //   (기존 getKoreanNow() 는 환경에 따라 이중 보정될 수 있음)
    // - [수정] accessToken(JWT) 만료 == 로그아웃 이 아니도록 변경.
    //   "자동로그인" 쿠키는 30일짜리인데 accessToken exp 는 훨씬 짧아서
    //   (예: 30분) 예전엔 앱을 며칠 뒤 다시 열면 자동로그인 체크했어도
    //   무조건 로그인 화면으로 튕겨나갔음 — 자동로그인의 의미가 없었음.
    //   이제는 refreshToken 이 남아있으면 "로그인 상태"로 간주하고 통과시키고,
    //   실제 accessToken 재발급은 aibeesApi.js 의 401 인터셉터가 처음
    //   API를 호출하는 시점에 조용히 처리한다(Silent Refresh). refreshToken
    //   자체가 만료/무효면 그 갱신이 실패하면서 그때 진짜 로그아웃 처리됨.
    // ──────────────────────────────────────────────
    const isUserSession = () => {
        // sessionStorage 우선, 없으면 localStorage(자동로그인, 30일 이내) 확인
        const sessionUser =
            JSON.parse(sessionStorage.getItem('userSession')) ??
            loadAutoLogin();

        if (sessionUser !== null && user.loginInfo.user_name === '') {
            user.loginInfo    = sessionUser.loginInfo;
            user.expireTime   = new Date(sessionUser.expireTime);
            user.accessToken  = sessionUser.accessToken;
            user.refreshToken = sessionUser.refreshToken ?? '';
        }

        if (user.loginInfo.user_name === '' || user.accessToken === '') {
            return false;
        }

        // accessToken 아직 안 만료 → 정상 로그인 상태
        if (user.expireTime > new Date()) {
            return true;
        }

        // accessToken 은 만료됐지만 refreshToken 이 있으면 로그인 상태 유지.
        // (쿠키 자체 만료 = 30일 이므로, 그 안에서는 이 경로로 계속 통과됨)
        return user.refreshToken !== '';
    };

    // ──────────────────────────────────────────────
    // [수정] loginUser
    // - refreshToken 저장 추가
    // - expireTime을 클라이언트가 임의 계산하지 않고
    //   서버 JWT의 exp claim 에서 읽도록 변경.
    //   exp 가 없는 경우 fallback 으로 30분 사용.
    // ──────────────────────────────────────────────
    // autoLogin=true 이면 localStorage에도 저장 → 브라우저 재시작 후에도 유지
    const loginUser = (info, autoLogin = false) => {
        user.loginInfo    = { ...info.loginInfo };
        user.accessToken  = info.accessToken;
        user.refreshToken = info.refreshToken ?? '';

        const decoded = decodeJwt(info.accessToken);
        user.expireTime = decoded?.exp
            ? new Date(decoded.exp * 1000)
            : new Date(Date.now() + 30 * 60 * 1000);

        const serialized = JSON.stringify(user);
        sessionStorage.setItem('userSession', serialized);
        if (autoLogin) {
            saveAutoLogin(user); // 30일 유지 (localStorage)
        } else {
            clearAutoLogin();
        }
    };

    // ──────────────────────────────────────────────
    // [추가] updateTokens
    // Silent Refresh 성공 후 aibeesApi.js 에서 호출.
    // accessToken·refreshToken 을 교체하고 exp 도 재계산.
    // ──────────────────────────────────────────────
    const updateTokens = (accessToken, refreshToken) => {
        user.accessToken = accessToken;
        if (refreshToken) user.refreshToken = refreshToken;

        const decoded = decodeJwt(accessToken);
        user.expireTime = decoded?.exp
            ? new Date(decoded.exp * 1000)
            : new Date(Date.now() + 30 * 60 * 1000);

        const serialized = JSON.stringify(user);
        sessionStorage.setItem('userSession', serialized);
        // 자동로그인 상태였다면(localStorage에 저장돼 있었다면) 만료시각을
        // 다시 30일로 연장하며 갱신 — "쓰는 동안은 계속 유지"
        if (localStorage.getItem('userSession')) {
            saveAutoLogin(user);
        }
    };

    // ──────────────────────────────────────────────
    // [수정] logoutUser
    // - user.accessTime → user.expireTime 오타 수정
    // - refreshToken 초기화 추가
    // - menuList sessionStorage 도 함께 제거
    // ──────────────────────────────────────────────
    const logoutUser = () => {
        user.loginInfo = { user_id: '', user_name: '', role: [] };
        user.accessToken  = '';
        user.refreshToken = '';  // [추가]
        user.expireTime   = null; // [수정] accessTime → expireTime
        user.menuList     = [];

        sessionStorage.removeItem('userSession');
        sessionStorage.removeItem('menuList');
        clearAutoLogin(); // 자동로그인 해제
    };

    // ──────────────────────────────────────────────
    // [추가] isTokenExpiringSoon
    // 만료 1분 이내면 true 반환.
    // aibeesApi 에서 선제적 갱신 판단에 사용 가능.
    // ──────────────────────────────────────────────
    const isTokenExpiringSoon = () => {
        if (!user.expireTime) return true;
        return (new Date(user.expireTime) - new Date()) < 60 * 1000;
    };

    const setMenuList = (menu) => {
        user.menuList = menu;
        sessionStorage.setItem('menuList', JSON.stringify(user.menuList));
    };

    const loadMenuList = () => {
        const m = sessionStorage.getItem('menuList');
        return JSON.parse(m);
    };

    return {
        user,                  // [추가] accessToken/refreshToken 접근용으로 노출
        getUserInfo, getRole,
        loginUser, logoutUser, isUserSession,
        updateTokens, isTokenExpiringSoon, // [추가]
        setMenuList, loadMenuList
    };
});
