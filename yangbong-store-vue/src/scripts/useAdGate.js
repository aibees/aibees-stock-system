/**
 * 광고 게이트 — 진입 횟수 카운트 + 1회용 통과권.
 *
 * ── N번에 한 번 ──
 * 게이트 대상 메뉴(개별주식·개별차트·매수추천)에 들어갈 때마다 사용자별로 1씩 센다(세 메뉴가 카운터 하나를 같이 쓴다).
 * 카운트가 N 에 닿으면 광고 게이트로 보내고, 광고를 다 보면(grantAdPass) 0 으로 되돌린다.
 * 게이트에서 광고를 안 보고 빠져나가면 리셋하지 않는다 → 다음 진입 때 다시 게이트.
 * N 은 공통코드 master_codes(stock/setting/ad, code=GATE_INTERVAL, desc=숫자)를 /master/menus/my 의
 * settings 로 받는다. 못 받았거나 값이 이상하면 DEFAULT_GATE_INTERVAL.
 * 카운트는 이 기기의 localStorage(사용자별 키)에 둔다 — 기기·웹/앱마다 따로 세고, 앱 재설치·브라우저 데이터
 * 삭제 시 0 부터 다시 센다(UX 정책이라 이 정도 오차는 허용).
 *
 * ── 통과권 ──
 * 광고를 다 보면
 * "이동할 경로 하나"에만 쓸 수 있는 통과권을 주고, 그 경로로 들어가는 순간 소모된다.
 * (예전에는 한 번 보면 30분간 다시 묻지 않았다 — 입장마다 노출로 바꿨다)
 *
 * sessionStorage 를 쓰는 이유: 앱(Capacitor)에서 게이트 → 원래 경로 이동 사이에 화면이 다시 그려져도
 * 통과권이 유지되게. 저장소를 못 쓰는 환경(사생활 보호 모드 등)은 메모리로 폴백한다.
 * 이 게이트는 UX 정책이지 보안 경계가 아니다 — 서버 API 는 막지 않는다.
 */
const KEY = 'adGatePass';

export const DEFAULT_GATE_INTERVAL = 5;
const COUNT_KEY_PREFIX = 'adGateCount:';
const memoryCount = {};   // localStorage 를 못 쓰는 환경용

/** 공통코드 값 → N. 1 이상의 정수가 아니면 기본값. */
export const gateInterval = (settings) => {
    const n = Number.parseInt(settings?.GATE_INTERVAL, 10);
    return Number.isInteger(n) && n >= 1 ? n : DEFAULT_GATE_INTERVAL;
};

const readCount = (userId) => {
    try {
        const v = Number.parseInt(localStorage.getItem(COUNT_KEY_PREFIX + userId), 10);
        if (Number.isInteger(v) && v >= 0) return v;
    } catch (_) { /* ignore */ }
    return memoryCount[userId] ?? 0;
};
const writeCount = (userId, v) => {
    memoryCount[userId] = v;
    try { localStorage.setItem(COUNT_KEY_PREFIX + userId, String(v)); } catch (_) { /* ignore */ }
};

/** 게이트 대상 메뉴 진입 1회를 센다. 이번 진입에 광고를 보여야 하면 true. */
export const countGateEntry = (userId, interval) => {
    const next = readCount(userId) + 1;
    writeCount(userId, next);
    return next >= interval;
};

/** 광고를 다 본 뒤 카운트를 0 으로. */
export const resetGateCount = (userId) => writeCount(userId, 0);

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
