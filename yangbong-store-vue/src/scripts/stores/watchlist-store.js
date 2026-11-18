/**
 * 관심 종목: 가입 없이 쓰도록 이 기기(localStorage)에 저장한다.
 * 저장 시점의 이름·가격을 함께 둬서, 그날 분석 목록에 없는 종목도 홈에 표시할 수 있게 한다.
 * 알림 발송 서버를 붙일 때 계정·기기 단위 서버 저장으로 옮긴다.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

const STORAGE_KEY = 'yb-watchlist';

const readSaved = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        return { items: Array.isArray(v.items) ? v.items.filter(x => x?.code) : [], alerts: v.alerts === true };
    } catch {
        return { items: [], alerts: false };
    }
};

export const useWatchlistStore = defineStore('watchlist', () => {
    const saved = readSaved();
    const items = ref(saved.items);
    const alerts = ref(saved.alerts);

    const persist = () => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ items: items.value, alerts: alerts.value }));
        } catch { /* 저장 실패 — 이번 실행 동안만 기억한다 */ }
    };

    const count = computed(() => items.value.length);
    const has = (code) => items.value.some(x => x.code === code);

    /** 담기/빼기. 담았으면 true */
    const toggle = ({ code, name, close = null, rate = null }) => {
        if (has(code)) {
            items.value = items.value.filter(x => x.code !== code);
            persist();
            return false;
        }
        items.value = [{ code, name, close, rate, addedAt: Date.now() }, ...items.value];
        persist();
        return true;
    };
    const setAlerts = (on) => { alerts.value = !!on; persist(); };

    return { items, alerts, count, has, toggle, setAlerts };
});
