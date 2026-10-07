/**
 * 광고 게이트 통과권 — 1회용.
 * 게이트 대상 메뉴(개별주식·개별차트·매수추천)는 들어갈 때마다 광고를 본다. 광고를 다 보면
 * "이동할 경로 하나"에만 쓸 수 있는 통과권을 주고, 그 경로로 들어가는 순간 소모된다.
 * (예전에는 한 번 보면 30분간 다시 묻지 않았다 — 입장마다 노출로 바꿨다)
 *
 * sessionStorage 를 쓰는 이유: 앱(Capacitor)에서 게이트 → 원래 경로 이동 사이에 화면이 다시 그려져도
 * 통과권이 유지되게. 저장소를 못 쓰는 환경(사생활 보호 모드 등)은 메모리로 폴백한다.
 * 이 게이트는 UX 정책이지 보안 경계가 아니다 — 서버 API 는 막지 않는다.
 */
const KEY = 'adGatePass';

/** 통과권 키로 쓰는 경로: 쿼리·해시 제거, 앞뒤 슬래시 정리(router.js 의 normPath 와 같은 규칙). */
export const adPassPath = (fullPath) =>
    '/' + String(fullPath ?? '').split(/[?#]/)[0].replace(/^\/+/, '').replace(/\/+$/, '');
// 통과권을 받고 이 시간 안에 쓰지 않으면 무효(게이트에서 다른 곳으로 빠졌다가 나중에 들어오는 경우)
const PASS_TTL_MS = 60 * 1000;
let memoryPass = null;

const read = () => {
    try {
        const raw = sessionStorage.getItem(KEY);
        if (raw) return JSON.parse(raw);
    } catch (_) { /* ignore */ }
    return memoryPass;
};

export const clearAdPass = () => {
    memoryPass = null;
    try { sessionStorage.removeItem(KEY); } catch (_) { /* ignore */ }
};

/** 광고를 다 본 뒤 호출. path 는 쿼리 없는 경로(예: /stock/info). */
export const grantAdPass = (path) => {
    memoryPass = { path, at: Date.now() };
    try { sessionStorage.setItem(KEY, JSON.stringify(memoryPass)); } catch (_) { /* ignore */ }
};

/** 이 경로에 쓸 통과권이 있으면 소모하고 true. 없거나 만료면 false(→ 광고 게이트로). */
export const consumeAdPass = (path) => {
    const pass = read();
    clearAdPass();
    return !!pass && pass.path === path && Date.now() - pass.at < PASS_TTL_MS;
};
