/**
 * 광고 게이트 통과 기록.
 * sessionStorage 에 통과 시각만 둔다(탭을 닫으면 사라짐). 저장소를 못 쓰는 환경
 * (사생활 보호 모드 등)에서는 메모리로 폴백하므로 새로고침하면 다시 본다.
 * 이 게이트는 UX 정책이지 보안 경계가 아니다 — 서버 API 는 막지 않는다.
 */
import { AD_GATE_PASS_MINUTES } from './adConfig.js';

const KEY = 'adGatePassAt';
let memoryPassAt = 0;

export const hasAdPass = () => {
    let at = memoryPassAt;
    try { at = Number(sessionStorage.getItem(KEY) || 0) || at; } catch (_) { /* ignore */ }
    // AD_GATE_PASS_MINUTES=0(매번 광고)이어도 게이트 → 원래 경로 이동 직후 가드가 한 번은
    // 통과시켜야 무한 리다이렉트가 안 생긴다. 그래서 최소 유효시간을 10초로 둔다.
    const windowMs = Math.max(AD_GATE_PASS_MINUTES * 60 * 1000, 10 * 1000);
    return at > 0 && Date.now() - at < windowMs;
};

export const grantAdPass = () => {
    memoryPassAt = Date.now();
    try { sessionStorage.setItem(KEY, String(memoryPassAt)); } catch (_) { /* ignore */ }
};

export const clearAdPass = () => {
    memoryPassAt = 0;
    try { sessionStorage.removeItem(KEY); } catch (_) { /* ignore */ }
};
