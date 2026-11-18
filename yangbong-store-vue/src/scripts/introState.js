/** 앱 소개를 이 기기에서 봤는지. 저장소를 못 쓰면 이번 실행 동안만 기억한다. */
const STORAGE_KEY = 'yb-intro-seen';
let seenInMemory = false;

export const isIntroSeen = () => {
    if (seenInMemory) return true;
    try {
        return localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
        return false;
    }
};

export const markIntroSeen = () => {
    seenInMemory = true;
    try {
        localStorage.setItem(STORAGE_KEY, '1');
    } catch { /* 저장 실패 — 이번 실행 동안만 기억한다 */ }
};
