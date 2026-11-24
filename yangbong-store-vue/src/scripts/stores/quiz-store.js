/**
 * 퀴즈 모음 기록: 문제별 마지막 결과(맞힘/틀림). 트레이닝 진행 기록처럼 이 기기(localStorage)에 둔다.
 * 저장소 접근은 사생활 보호 모드 등에서 실패할 수 있어 try/catch — 실패해도 이번 실행 동안은 동작한다.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { allQuestions, findQuestion } from '../trainingQuiz.js';
import { useReviewStore } from './review-store.js';

const STORAGE_KEY = 'yb-training-quiz';

const readSaved = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
        return v && typeof v === 'object' && !Array.isArray(v) ? v : {};
    } catch {
        return {};
    }
};

export const useQuizStore = defineStore('training-quiz', () => {
    const results = ref(readSaved());
    const questions = allQuestions();

    const record = (id, isRight) => {
        results.value = { ...results.value, [id]: isRight ? 'right' : 'wrong' };
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(results.value));
        } catch { /* 저장 실패 — 이번 실행 동안만 기억한다 */ }
        // 다시 보기(2026-11-24): 틀리면 오답노트에, 오답노트 문제를 다시 맞히면 복습 한 칸 앞으로
        const review = useReviewStore();
        if (isRight) review.solvedAgain(id);
        else review.addWrong(id, findQuestion(id)?.chapterName ?? '');
    };

    const rightCount = computed(() => questions.filter(q => results.value[q.id] === 'right').length);
    const wrongQuestions = computed(() => questions.filter(q => results.value[q.id] === 'wrong'));
    const rightIn = (list) => list.filter(q => results.value[q.id] === 'right').length;

    return { results, record, rightCount, wrongQuestions, rightIn, total: questions.length };
});
