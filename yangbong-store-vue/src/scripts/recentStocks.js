/**
 * 최근 조회한 회사. 주식분석 대시보드가 보여 주고, 종목 상세(AI 분석)·차트·매수추천 상세를 열 때 쌓는다.
 * 이 기기(localStorage)에만 두며 최근 순 10개. 저장소 접근은 실패할 수 있어 전부 try/catch — 실패해도 화면은 동작한다.
 */
const KEY = 'yb-recent-stocks';
const MAX = 10;

export const getRecent = () => {
    try {
        const v = JSON.parse(localStorage.getItem(KEY) || '[]');
        return Array.isArray(v) ? v.filter(r => r && r.code) : [];
    } catch { return []; }
};

/** 같은 회사는 맨 앞으로 옮기고 이름·시각을 갱신한다. 이름이 비면 이전 이름을 유지한다. */
export const addRecent = (code, name) => {
    const c = String(code ?? '').trim();
    if (!c) return;
    try {
        const prev = getRecent();
        const old = prev.find(r => r.code === c);
        const next = [{ code: c, name: String(name || old?.name || c), ts: Date.now() }, ...prev.filter(r => r.code !== c)].slice(0, MAX);
        localStorage.setItem(KEY, JSON.stringify(next));
    } catch { /* 기록 못 해도 조회에는 영향 없다 */ }
};

export const clearRecent = () => {
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
};
