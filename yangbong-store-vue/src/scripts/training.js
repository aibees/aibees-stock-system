/**
 * 트레이닝 커리큘럼: 장(chapter) → 단계(stage). 앞 단계를 마쳐야 다음 단계가 열린다(2026-11-15 결정, 순서대로 잠금).
 *
 *   data/trainingToc.json     : 장·단계 목차(제목 순서). 단계를 늘리면 여기에 항목만 더한다.
 *   data/trainingLessons.json : 단계 본문. 키는 "<장 slug>/<단계 id>".
 *                               { body: [블록...] } 은 읽는 단계, { quiz: [문항...] } 은 장 끝의 확인 단계.
 *                               본문이 없는 단계는 "준비 중" — 열려도 마칠 수 없어서 그 뒤 단계는 계속 잠겨 있다.
 *
 * 본문 블록: {p} 문단, {h} 소제목, {terms:[[용어, 뜻]...]}, {note} 참고, {figure, caption} 그림(TrainingFigure.vue).
 * 문항: { q, options:[...], answer: 정답 index, explain }.
 *
 * 진행 기록(마친 단계)은 stores/training-store.js — 키는 단계의 key("<장>/<단계>")라서
 * 단계 순서를 바꾸거나 사이에 끼워 넣어도 이미 마친 기록은 그대로 남는다. 단계 id 는 바꾸지 않는다.
 */
import TOC from './data/trainingToc.json';
import LESSONS from './data/trainingLessons.json';

export const TRAINING_PATH = '/training';

const hasLesson = (l) => !!l && ((l.body?.length ?? 0) > 0 || (l.quiz?.length ?? 0) > 0);

// 장마다 단계에 전체 순번(no)·키(key)·본문을 붙여 둔다. 목차는 바뀌지 않으므로 한 번만 만든다.
const CHAPTERS = (() => {
    let no = 0;
    return TOC.chapters.map((ch, ci) => {
        const stages = ch.stages.map((s, si) => {
            no += 1;
            const key = `${ch.slug}/${s.id}`;
            const lesson = LESSONS[key] ?? null;
            return {
                ...s,
                key,
                no,
                chapterSlug: ch.slug,
                indexInChapter: si + 1,
                lesson: hasLesson(lesson) ? lesson : null,
                isQuiz: (lesson?.quiz?.length ?? 0) > 0,
            };
        });
        return { ...ch, no: ci + 1, stages, first: stages[0]?.no ?? 0, last: stages.at(-1)?.no ?? 0 };
    });
})();
const STAGES = CHAPTERS.flatMap(c => c.stages);

export const chapters = () => CHAPTERS;
export const allStages = () => STAGES;
export const soonItems = () => TOC.soon ?? [];

export const findChapter = (slug) => CHAPTERS.find(c => c.slug === slug) ?? null;
export const findStage = (chapterSlug, stageId) => STAGES.find(s => s.key === `${chapterSlug}/${stageId}`) ?? null;

/** 커리큘럼 안에서 바로 다음 단계(장을 넘어간다). 마지막이면 null. */
export const followingStage = (stage) => {
    const i = STAGES.findIndex(s => s.key === stage?.key);
    return i < 0 ? null : STAGES[i + 1] ?? null;
};

export const chapterPath = (chapter) => `${TRAINING_PATH}/${chapter.slug ?? chapter}`;
export const stagePath = (stage) => `${TRAINING_PATH}/${stage.key}`;
