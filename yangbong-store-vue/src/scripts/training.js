/**
 * 트레이닝 목차. 내용은 data/trainingToc.json (데이터) — 강의가 늘면 JSON 에 항목만 더한다.
 * 지금은 목차만 있고 본문은 없다(2026-11-15 목업). soon:true 는 "준비 중" 항목이다.
 */
import TOC from './data/trainingToc.json';

export const TRAINING_PATH = '/training';

export const trainingGroups = () => TOC.groups;

export const allCourses = () => TOC.groups.flatMap(g => g.courses);

/** slug 로 강의를 찾는다. 없거나 준비 중이면 null(상세는 열지 않는다). */
export const findCourse = (slug) => allCourses().find(c => c.slug === slug && !c.soon) ?? null;
