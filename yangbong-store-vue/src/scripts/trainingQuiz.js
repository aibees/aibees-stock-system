/**
 * 트레이닝 퀴즈 모음: 각 장의 확인 단계(trainingLessons.json 의 quiz)를 한곳에 모은다.
 * 문제 내용은 강의의 확인 문제와 같은 데이터를 쓴다 — 문제를 고치면 양쪽에 함께 반영된다.
 * 문제 id: "<장 slug>/<단계 id>#<순번>"
 */
import { chapters } from './training.js';

export const QUIZ_PATH = '/training/quiz';
export const quizSetPath = (set) => `${QUIZ_PATH}/${set}`;

// 장 끝 확인 퀴즈(id "<단계 key>#<순번>") + 수업 안 상황형 퀴즈 {ask}(id "<단계 key>~<순번>", 2026-11-24 경제 기초)
const QUESTIONS = chapters().flatMap(ch => ch.stages.filter(s => s.lesson).flatMap(s => [
    ...(s.lesson.quiz ?? []).map((q, i) => ({ ...q, id: `${s.key}#${i}`, stageKey: s.key, chapterSlug: ch.slug, chapterName: ch.name })),
    ...(s.lesson.body ?? []).filter(b => b.ask).map((b, i) => ({ ...b.ask, id: `${s.key}~${i}`, stageKey: s.key, chapterSlug: ch.slug, chapterName: ch.name })),
]));
const BY_ID = Object.fromEntries(QUESTIONS.map(q => [q.id, q]));
export const findQuestion = (id) => BY_ID[id] ?? null;
/** 수업 안 상황형 퀴즈의 문제 id */
export const askId = (stageKey, i) => `${stageKey}~${i}`;

export const allQuestions = () => QUESTIONS;

export const quizChapters = () => chapters()
    .map(ch => ({ slug: ch.slug, name: ch.name, questions: QUESTIONS.filter(q => q.chapterSlug === ch.slug) }))
    .filter(ch => ch.questions.length);

/** 오늘의 한 문제: 날짜마다 바뀌고, 같은 날에는 같은 문제 */
export const todayQuestion = (date = new Date()) => {
    if (!QUESTIONS.length) return null;
    const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000);
    return QUESTIONS[day % QUESTIONS.length];
};
