/**
 * 학습한 날 기록 — 홈 '이번 주 학습' 줄(일~토)에 쓴다. 2026-11-24.
 *
 * "학습"으로 치는 것(하루에 하나라도 하면 그날은 한 걸로):
 *   - 수업 단계 마침(stores/training-store.js complete)
 *   - 퀴즈 한 문제 풀기(stores/quiz-store.js record)
 *   - 차트 퀴즈 답 내기(trainingChart.js submitAnswer)
 *
 * 이 기기에만 저장한다(localStorage 'yb-study-days', 'YYYY-MM-DD' 목록, 최근 120일만). 서버·계정에는 올리지 않으므로
 * 기기를 바꾸면 따라오지 않고, 이 기능이 들어간 날부터 쌓인다(그 전 기록은 날짜를 몰라 채울 수 없다).
 * 날짜는 기기의 현재 시간대(보통 한국) 기준.
 */
import { ref, computed } from 'vue';

const STORAGE_KEY = 'yb-study-days';
const KEEP_DAYS = 120;

const pad = (n) => String(n).padStart(2, '0');
export const ymdOf = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

const load = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY));
        return Array.isArray(v) ? v.filter(x => typeof x === 'string') : [];
    } catch {
        return [];
    }
};

const days = ref(load());

/** 오늘(또는 주어진 날)을 학습한 날로 적는다. 이미 있으면 아무것도 하지 않는다. */
export const markStudied = (date = new Date()) => {
    const key = ymdOf(date);
    if (days.value.includes(key)) return;
    days.value = [...days.value, key].sort().slice(-KEEP_DAYS);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(days.value)); } catch { /* 저장 못 해도 이번 화면에서는 동작 */ }
};

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

/** 오늘이 든 주(일요일 시작)의 7일. state: done(학습함) · today(오늘, 아직) · missed(지나감, 안 함) · future(아직 안 옴) */
export const useStudyWeek = () => {
    const week = computed(() => {
        const now = new Date();
        const todayKey = ymdOf(now);
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - now.getDay());
        return Array.from({ length: 7 }, (_, i) => {
            const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
            const key = ymdOf(d);
            const done = days.value.includes(key);
            const state = done ? 'done' : key === todayKey ? 'today' : key < todayKey ? 'missed' : 'future';
            return { key, label: WEEKDAYS[i], date: d.getDate(), done, isToday: key === todayKey, state };
        });
    });
    const doneCount = computed(() => week.value.filter(d => d.done).length);
    return { week, doneCount };
};
