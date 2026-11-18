/**
 * 트레이닝 진행 기록: 마친 단계의 key 목록. 가입 없이도 쓰므로 이 기기(localStorage 'yb-training')에 둔다.
 * 계정으로 옮기는 동기화는 아직 없다(필요하면 성향처럼 yangbong 스키마에 테이블을 두고 updatedAt 으로 맞춘다).
 *
 * 순서대로 잠금은 2026-11-18 에 폐지했다(2026-11-15 에는 앞 단계를 마쳐야 다음이 열렸다).
 * 지금은 어느 단계든 바로 볼 수 있고, '마침' 기록과 '지금 차례'(안 마친 첫 단계) 표시만 남는다.
 *
 * 저장소 접근은 사생활 보호 모드 등에서 실패할 수 있어 모두 try/catch — 실패해도 이번 실행 동안은 동작한다.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { allStages } from '../training.js';

const STORAGE_KEY = 'yb-training';

const readSaved = () => {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const v = raw ? JSON.parse(raw) : null;
        return v && typeof v === 'object' ? v : {};
    } catch {
        return {};
    }
};

export const useTrainingStore = defineStore('training', () => {
    const saved = readSaved();
    const done = ref(Array.isArray(saved.done) ? saved.done.filter(k => typeof k === 'string') : []);
    const updatedAt = ref(Number(saved.updatedAt) || 0);

    const persist = () => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ done: done.value, updatedAt: updatedAt.value }));
        } catch { /* 저장 실패 — 이번 실행 동안만 기억한다 */ }
    };

    const stages = allStages();
    const doneSet = computed(() => new Set(done.value));
    const isDone = (key) => doneSet.value.has(key);

    // 모든 단계가 처음부터 열려 있다(2026-11-18, 순서대로 잠금 폐지). 없는 단계만 닫힌 것으로 본다.
    const isOpen = (key) => stages.some(s => s.key === key);

    /** 지금 할 차례: 아직 안 마쳤고 열려 있는 첫 단계. 다 마쳤으면 null. */
    const nextStage = computed(() => stages.find(s => !isDone(s.key) && isOpen(s.key)) ?? null);

    // 지금 목차에 있는 단계만 센다(없어진 단계의 기록은 세지 않는다).
    const doneCount = computed(() => stages.filter(s => isDone(s.key)).length);
    const total = stages.length;

    /** 단계를 마친다. 본문 없는 단계는 마칠 수 없다. */
    const complete = (key) => {
        const s = stages.find(x => x.key === key);
        if (!s || !s.lesson || !isOpen(key) || isDone(key)) return false;
        done.value = [...done.value, key];
        updatedAt.value = Date.now();
        persist();
        return true;
    };

    return { done, updatedAt, isDone, isOpen, nextStage, doneCount, total, complete };
});
