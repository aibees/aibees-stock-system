/**
 * 공통 - 서버와의 통신 utility
 */
import axios from 'axios';
import { assUserSession } from './stores/user-stores';

// ──────────────────────────────────────────────────────────────
// [추가] refreshApi: 토큰 재발급 전용 axios 인스턴스
// 메인 aibeesApi 의 interceptor 를 거치지 않도록 별도 생성.
// 재발급 요청 → 401 → 재발급 요청 의 무한 루프 방지가 목적.
// ──────────────────────────────────────────────────────────────
const refreshApi = axios.create({
    timeout: 10000,
    baseURL: aibeesGlobal.API_SERVER_URL
});

const aibeesApi = axios.create({
    timeout: 180000,
    baseURL: aibeesGlobal.API_SERVER_URL
});

export const batchApi = axios.create({
    timeout: 180000,
    baseURL: aibeesGlobal.BATCH_SERVER_URL
});

// ──────────────────────────────────────────────────────────────
// [추가] Silent Refresh 동시 요청 방지용 변수
// isRefreshing: 현재 재발급 요청이 진행 중인지 여부
// failedQueue: 재발급 대기 중인 원래 요청들의 Promise 목록
// ──────────────────────────────────────────────────────────────
let isRefreshing = false;
let failedQueue  = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(p => error ? p.reject(error) : p.resolve(token));
    failedQueue = [];
};

// ──────────────────────────────────────────────────────────────
// REQUEST INTERCEPTOR
// [수정] 고정 문자열 헤더 대신, 스토어의 accessToken 을 꺼내
//        표준 Bearer 형식으로 Authorization 헤더에 첨부.
//        interceptor 함수 내부에서 store 를 호출하므로
//        Pinia 초기화 이후에만 실행되어 순환 참조 문제 없음.
// ──────────────────────────────────────────────────────────────
const authRequestInterceptor = (config) => {
    const userSession = assUserSession();
    if (userSession.user.accessToken) {
        config.headers['Authorization'] = `Bearer ${userSession.user.accessToken}`;
    }
    config.headers['Content-Type'] = 'application/json';
    return config;
};

aibeesApi.interceptors.request.use(authRequestInterceptor, (error) => Promise.reject(error));
batchApi.interceptors.request.use(authRequestInterceptor, (error) => Promise.reject(error));

// ──────────────────────────────────────────────────────────────
// RESPONSE INTERCEPTOR
// [수정] 401 응답 처리 추가
//
// 흐름:
//  1. 서버가 401 반환 → refreshToken 존재 여부 확인
//  2. refreshToken 없음 → 즉시 로그아웃 + 로그인 페이지 이동
//  3. refreshToken 있음 + 재발급 진행 중 → failedQueue 에 대기
//  4. refreshToken 있음 + 재발급 미진행 → /api/oauth/refresh 호출
//     - 성공: updateTokens() 로 스토어 갱신, 대기 큐 해소, 원래 요청 재시도
//     - 실패: 강제 로그아웃
//
// _retry 플래그: 같은 요청이 재시도 중에 다시 401 이 오면 무한 루프 방지
//
// [수정] "자동로그인 30일 유지" 대응 — 이 인터셉터를 aibeesApi 뿐 아니라
// batchApi(py-stock-batch, 매도 수기등록 등)에도 똑같이 붙인다.
// 예전엔 batchApi 는 response interceptor 자체가 없어서, accessToken이
// 만료된 채로(자동로그인 상태) 매도 수기등록을 호출하면 재발급 없이
// 그냥 401로 실패했었음. isRefreshing/failedQueue 는 두 인스턴스가
// 공유해서, 동시에 여러 API가 401을 맞아도 재발급 요청은 1번만 나간다.
// ──────────────────────────────────────────────────────────────
const attachAuthResponseInterceptor = (apiInstance) => {
    apiInstance.interceptors.response.use(
        (resp) => resp,
        async (error) => {
            const originalRequest = error.config;
            const userSession     = assUserSession();

            if (error.response?.status === 401 && !originalRequest._retry) {

                // refreshToken 자체가 없으면 재발급 불가 → 로그아웃
                if (!userSession.user.refreshToken) {
                    userSession.logoutUser();
                    window.location.href = '/login';
                    return Promise.reject(error);
                }

                // 이미 재발급 진행 중 → 큐에 넣고 대기
                if (isRefreshing) {
                    return new Promise((resolve, reject) => {
                        failedQueue.push({ resolve, reject });
                    }).then(token => {
                        originalRequest.headers['Authorization'] = `Bearer ${token}`;
                        return apiInstance(originalRequest);
                    }).catch(err => Promise.reject(err));
                }

                originalRequest._retry = true;
                isRefreshing           = true;

                try {
                    const { data } = await refreshApi.post('/api/oauth/refresh', {
                        refreshToken: userSession.user.refreshToken
                    });

                    const { accessToken, refreshToken } = data.data;

                    // 스토어 + sessionStorage 갱신
                    userSession.updateTokens(accessToken, refreshToken);

                    // 대기 중이던 요청들 모두 새 토큰으로 재시도
                    processQueue(null, accessToken);

                    // 원래 실패했던 요청 재시도
                    originalRequest.headers['Authorization'] = `Bearer ${accessToken}`;
                    return apiInstance(originalRequest);

                } catch (refreshError) {
                    processQueue(refreshError, null);
                    userSession.logoutUser();
                    window.location.href = '/login';
                    return Promise.reject(refreshError);

                } finally {
                    isRefreshing = false;
                }
            }

            // 401 이외의 에러 처리 (기존 로직 유지)
            // RESET_REQUIRED 는 호출부(Login.vue)에서 직접 처리하므로 여기서 alert 하지 않음
            const errCode = error.response?.data?.error?.code;
            if (error.response?.data?.error != null && errCode !== 'RESET_REQUIRED') {
                alert(error.response.data.error.message);
            }
            return Promise.reject(error.response?.data ?? error);
        }
    );
};

attachAuthResponseInterceptor(aibeesApi);
attachAuthResponseInterceptor(batchApi);

export default aibeesApi;
