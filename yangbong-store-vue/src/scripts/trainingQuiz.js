/**
 * 트레이닝 퀴즈 모음: 각 장의 확인 단계(trainingLessons.json 의 quiz)를 한곳에 모은다.
 * 문제 내용은 강의의 확인 문제와 같은 데이터를 쓴다 — 문제를 고치면 양쪽에 함께 반영된다.
 * 문제 id: "<장 slug>/<단계 id>#<순번>"
 */
import { chapters } from './training.js';

export const QUIZ_PATH = '/training/quiz';
export const quizSetPath = (set) => `${QUIZ_PATH}/${set}`;

const QUESTIONS = chapters().flatMap(ch => ch.stages
    .filter(s => s.isQuiz)
    .flatMap(s => s.lesson.quiz.map((q, i) => ({
        ...q,
        id: `${s.key}#${i}`,
        chapterSlug: ch.slug,
        chapterName: ch.name,
    }))));

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
