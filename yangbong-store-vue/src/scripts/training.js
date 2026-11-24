/**
 * 트레이닝 커리큘럼: 장(chapter) → 단계(stage). 모든 단계가 처음부터 열려 있다(2026-11-18, 순서대로 잠금 폐지).
 *
 *   data/trainingToc.json     : 장·단계 목차(제목 순서). 단계를 늘리면 여기에 항목만 더한다.
 *                               단계마다 title(레슨 화면의 긴 제목) · short(목차·버튼의 짧은 제목) · sub(목차의 회색 한 줄 설명).
 *   data/trainingLessons.json : 단계 본문. 키는 "<장 slug>/<단계 id>".
 *                               { body: [블록...] } 은 읽는 단계, { quiz: [문항...] } 은 장 끝의 확인 단계.
 *                               본문이 없는 단계는 "준비 중" — 열 수는 있지만 마칠 수 없다.
 *
 * 본문 블록: {p} 문단, {h} 소제목, {terms:[[용어, 뜻]...]}, {note} 참고, {figure, caption} 그림(TrainingFigure.vue).
 *   2026-11-24 경제 기초용: {calc:{title, rows:[[이름, 값]...], sum:[이름, 값]}} 계산 상자,
 *   {table:{head:[...], rows:[[...]...]}} 비교 표, {policy:[['live'|'plan', 글]...]} 시행 중·개편안,
 *   {ask:{q, options, answer, explain}} 수업 안 상황형 퀴즈(틀리면 오답노트). 단계의 basis:true 는 기준일 표시.
 * 문항: { q, options:[...], answer: 정답 index, explain }.
 *
 * 진행 기록(마친 단계)은 stores/training-store.js — 키는 단계의 key("<장>/<단계>")라서
 * 단계 순서를 바꾸거나 사이에 끼워 넣어도 이미 마친 기록은 그대로 남는다. 단계 id 는 바꾸지 않는다.
 */
import TOC from './data/trainingToc.json';
import LESSONS from './data/trainingLessons.json';

export const TRAINING_PATH = '/training';
export const LESSONS_PATH = `${TRAINING_PATH}/lessons`;
/** 수업 목록을 코스로 열기(/training/lessons?course=econ) */
export const coursePath = (course) => `${LESSONS_PATH}?course=${course.slug ?? course}`;
export const GLOSSARY_PATH = `${TRAINING_PATH}/glossary`;

const hasLesson = (l) => !!l && ((l.body?.length ?? 0) > 0 || (l.quiz?.length ?? 0) > 0);

// 코스(2026-11-24): 경제 기초(무료, 강) · 투자 실전(단계). trainingToc.json 의 courses 가 장 slug 를 묶는다.
//   단계 순번(no)은 코스 안에서 1부터 센다(경제 기초 1~19강, 투자 실전 1~37단계). 단계 key 는 그대로라 진행 기록은 바뀌지 않는다.
const COURSE_OF = Object.fromEntries((TOC.courses ?? []).flatMap(c => c.chapters.map(slug => [slug, c.slug])));

// 장마다 단계에 코스 안 순번(no)·키(key)·본문을 붙여 둔다. 목차는 바뀌지 않으므로 한 번만 만든다.
const CHAPTERS = (() => {
    const counter = {};
    const chapterNo = {};
    return TOC.chapters.map((ch) => {
        const course = COURSE_OF[ch.slug] ?? 'invest';
        chapterNo[course] = (chapterNo[course] ?? 0) + 1;
        const stages = ch.stages.map((s, si) => {
            counter[course] = (counter[course] ?? 0) + 1;
            const key = `${ch.slug}/${s.id}`;
            const lesson = LESSONS[key] ?? null;
            return {
                ...s,
                key,
                no: counter[course],
                course,
                chapterSlug: ch.slug,
                indexInChapter: si + 1,
                lesson: hasLesson(lesson) ? lesson : null,
                isQuiz: (lesson?.quiz?.length ?? 0) > 0,
            };
        });
        return { ...ch, course, no: chapterNo[course], stages, first: stages[0]?.no ?? 0, last: stages.at(-1)?.no ?? 0 };
    });
})();
const STAGES = CHAPTERS.flatMap(c => c.stages);

/** 코스 목록: { slug, name, title, free, unit('강'|'단계'), emoji, basis, chapters:[장], stages:[단계] } */
const COURSES = (TOC.courses ?? []).map(c => {
    const chs = CHAPTERS.filter(ch => ch.course === c.slug);
    return { ...c, chapters: chs, stages: chs.flatMap(ch => ch.stages) };
});
export const courses = () => COURSES;
export const findCourse = (slug) => COURSES.find(c => c.slug === slug) ?? null;
export const DEFAULT_COURSE = COURSES[0]?.slug ?? 'invest';
/** 단계 번호 글자: 경제 기초는 'N강', 투자 실전은 'N단계' */
export const stageNoText = (stage) => `${stage.no}${findCourse(stage.course)?.unit ?? '단계'}`;

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
