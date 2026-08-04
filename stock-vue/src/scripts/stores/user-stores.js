import { defineStore } from "pinia";
import { reactive, computed } from "vue";
import { setCookie, getCookie, removeCookie } from "@/scripts/utils/cookieUtils";

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
    // ──────────────────────────────────────────────
    const isUserSession = () => {
        // sessionStorage 우선, 없으면 localStorage(자동로그인) 확인
        const cookieVal = getCookie('userSession');
        const sessionUser =
            JSON.parse(sessionStorage.getItem('userSession')) ??
            (cookieVal ? JSON.parse(cookieVal) : null);

        if (sessionUser !== null && user.loginInfo.user_name === '') {
            user.loginInfo    = sessionUser.loginInfo;
            user.expireTime   = new Date(sessionUser.expireTime);
            user.accessToken  = sessionUser.accessToken;
            user.refreshToken = sessionUser.refreshToken ?? '';
        }
        return (
            user.loginInfo.user_name !== '' &&
            user.accessToken !== '' &&
            user.expireTime > new Date()
        );
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
            setCookie('userSession', serialized); // 30일 유지
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
        // 자동로그인 상태라면 쿠키도 갱신
        if (getCookie('userSession')) {
            setCookie('userSession', serialized);
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
        removeCookie('userSession'); // 자동로그인 해제
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
