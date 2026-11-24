/**
 * 다시 보기(2026-11-24): 오답노트 · 헷갈린 용어 · 복습하기.
 *
 *   오답노트   : 수업 안 상황형 퀴즈·장 끝 확인 퀴즈·퀴즈 모음·오늘의 한 문제에서 틀린 문제가 저절로 모인다.
 *   헷갈린 용어 : 수업의 용어 묶음·용어 사전에서 '헷갈려요'를 누른 용어.
 *   복습하기   : 둘 중 오늘 다시 볼 때가 된 것만. 1일 → 3일 → 7일 간격, 3번 연속 맞히면 '졸업'(목록에서 빠진다).
 *               틀리거나 '아직 헷갈려요'면 처음(1일 뒤)부터 다시.
 *
 * 항목 key: 'q:<문제 id>' · 't:<용어>'
 *   { kind:'wrong'|'term', ref, label(어디서 왔는지), desc(용어 뜻), step(0~3), due(ms), addedAt, updatedAt, done }
 *
 * 가입 없이도 쓰므로 이 기기(localStorage 'yb-training-review')에 두고, 로그인하면 계정
 * (yangbong.user_training_review, sql/yangbong/016 · /api/v1/training/review)과 맞춘다. 항목마다 updatedAt 이 늦은 쪽이 이긴다.
 * 서버가 실패해도(표 미적용·네트워크) 기기 기록으로 계속 동작한다.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import aibeesApi from '../aibeesApi.js';
import { assUserSession } from './user-stores.js';

const STORAGE_KEY = 'yb-training-review';
const API_PATH = '/api/v1/training/review';
const DAY = 86400000;
export const REVIEW_STEPS = [1, 3, 7];          // 맞힐 때마다 다음 복습까지 며칠
export const GRADUATE_AT = REVIEW_STEPS.length;  // 3번 맞히면 졸업
export const REVIEW_PATH = '/training/review';

const readSaved = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        return v && typeof v === 'object' && v.items && typeof v.items === 'object' ? v : { items: {} };
    } catch {
        return { items: {} };
    }
};
const currentUserId = () => {
    const s = assUserSession();
    return s.user.accessToken ? (s.user.loginInfo?.user_id || null) : null;
};
/** 오늘 끝(로컬 시각 23:59:59) — 오늘 안에 돌아온 것까지 '오늘 할 것' */
const endOfToday = () => { const d = new Date(); d.setHours(23, 59, 59, 999); return d.getTime(); };
/** n일 뒤 0시 — 같은 날 몇 번 풀어도 다음 복습일은 날짜로 정한다 */
const daysLater = (n) => { const d = new Date(); d.setHours(0, 0, 0, 0); return d.getTime() + n * DAY; };

export const useReviewStore = defineStore('training-review', () => {
    const saved = readSaved();
    const items = ref(saved.items);
    const owner = ref(saved.owner ?? null);

    const persist = () => {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ items: items.value, owner: owner.value })); } catch { /* 이번 실행 동안만 */ }
    };

    /* ── 계정 저장: 바뀐 뒤 잠깐 모아서 한 번에 올린다 ── */
    let pushTimer = null;
    const schedulePush = () => {
        const uid = currentUserId();
        if (!uid) return;
        clearTimeout(pushTimer);
        pushTimer = setTimeout(() => {
            aibeesApi.put(API_PATH, { items: items.value }, { silentError: true })
                .then(() => { owner.value = uid; persist(); })
                .catch(e => console.warn('[review] 계정 저장 실패 — 기기에는 저장됨', e?.error?.message ?? e?.message ?? e));
        }, 800);
    };
    const set = (key, patch) => {
        const now = Date.now();
        items.value = { ...items.value, [key]: { ...(items.value[key] ?? {}), ...patch, updatedAt: now } };
        persist();
        schedulePush();
    };

    let syncedFor = null;
    const syncWithAccount = async () => {
        const uid = currentUserId();
        if (!uid || syncedFor === uid) return;
        syncedFor = uid;
        try {
            const { data } = await aibeesApi.get(API_PATH, { silentError: true });
            const remote = data?.data?.items ?? {};
            const local = owner.value == null || owner.value === uid ? items.value : {};
            const merged = { ...remote };
            let needPush = false;
            for (const [k, v] of Object.entries(local)) {
                if (!merged[k] || (v.updatedAt ?? 0) > (merged[k].updatedAt ?? 0)) { merged[k] = v; needPush = true; }
            }
            items.value = merged;
            owner.value = uid;
            persist();
            if (needPush) schedulePush();
        } catch (e) {
            console.warn('[review] 계정 동기화 실패 — 이 기기 기록으로 계속', e?.error?.message ?? e?.message ?? e);
        }
    };

    /* ── 담기 ── */
    /** 틀린 문제를 오답노트에(이미 있으면 처음부터 다시) */
    const addWrong = (questionId, label = '') => {
        const key = `q:${questionId}`;
        const old = items.value[key];
        set(key, { kind: 'wrong', ref: questionId, label: label || old?.label || '', step: 0, due: daysLater(1), done: false, addedAt: old?.addedAt ?? Date.now() });
    };
    const isConfusing = (term) => { const it = items.value[`t:${term}`]; return !!it && !it.done && !it.removed; };
    /** 헷갈려요 켜기/끄기 */
    const toggleTerm = (term, desc = '', label = '') => {
        const key = `t:${term}`;
        if (isConfusing(term)) { set(key, { removed: true }); return false; }
        set(key, { kind: 'term', ref: term, desc, label, step: 0, due: daysLater(1), done: false, removed: false, addedAt: Date.now() });
        return true;
    };

    /* ── 복습 결과: 맞힘/알았어요 → 다음 간격, 틀림/아직 → 처음부터 ── */
    const answer = (key, right) => {
        const it = items.value[key];
        if (!it) return;
        if (!right) { set(key, { step: 0, due: daysLater(1), done: false }); return; }
        const step = (it.step ?? 0) + 1;
        if (step >= GRADUATE_AT) set(key, { step, done: true, doneAt: Date.now() });
        else set(key, { step, due: daysLater(REVIEW_STEPS[step]) });
    };
    /** 오답노트에서 다시 풀어 맞히면(퀴즈 모음 등) 한 칸 나아간다 — 오늘 할 차례일 때만 */
    const solvedAgain = (questionId) => {
        const key = `q:${questionId}`;
        const it = items.value[key];
        if (it && !it.done && (it.due ?? 0) <= endOfToday()) answer(key, true);
    };

    const active = computed(() => Object.entries(items.value)
        .filter(([, v]) => !v.done && !v.removed)
        .map(([key, v]) => ({ key, ...v }))
        .sort((a, b) => (a.due ?? 0) - (b.due ?? 0)));
    const wrongList = computed(() => active.value.filter(v => v.kind === 'wrong'));
    const termList = computed(() => active.value.filter(v => v.kind === 'term'));
    const dueList = computed(() => { const end = endOfToday(); return active.value.filter(v => (v.due ?? 0) <= end); });

    return { items, addWrong, toggleTerm, isConfusing, answer, solvedAgain, wrongList, termList, dueList, syncWithAccount };
});
