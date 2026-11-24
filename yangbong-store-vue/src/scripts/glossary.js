/**
 * 주식 용어 사전 데이터 도우미. 용어 내용은 data/glossary.json 에서만 고친다.
 *   term 표제어 · short 목록의 한 줄 뜻 · easy 쉽게 말하면 · example 예시 · caution 헷갈리기 쉬운 점
 *   aliases 검색용 다른 이름 · related 관련 용어(term 이름) · lesson 관련 강의("<장 slug>/<단계 id>")
 *   figure(선택) 양봉·음봉처럼 그림이 필요한 설명
 */
import DATA from './data/glossary.json';
import TOPICS from './data/glossaryTopics.json';

const INITIALS = ['ㄱ', 'ㄱ', 'ㄴ', 'ㄷ', 'ㄷ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅂ', 'ㅅ', 'ㅅ', 'ㅇ', 'ㅈ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];
export const LATIN_GROUP = 'A-Z';

/** 목록 묶음 이름: 한글은 첫 자음(ㄲ→ㄱ처럼 합침), 그 밖에는 A-Z */
export const groupOf = (term) => {
    const code = term.charCodeAt(0) - 0xAC00;
    return code >= 0 && code < 11172 ? INITIALS[Math.floor(code / 588)] : LATIN_GROUP;
};

const compareTerms = (a, b) => {
    const latinA = groupOf(a.term) === LATIN_GROUP;
    const latinB = groupOf(b.term) === LATIN_GROUP;
    if (latinA !== latinB) return latinA ? 1 : -1;   // 한글 먼저, 영문은 뒤
    return a.term.localeCompare(b.term, 'ko');
};

/**
 * 분류 칩은 용어의 category 를 그대로 보여주지 않고 categoryGroups 로 묶어서 보여준다(칩이 너무 많아지지 않게).
 * 용어 데이터의 category 는 그대로 두고 화면 묶음만 glossaryTopics.json 에서 바꾼다.
 * 어느 묶음에도 없는 category 는 자기 이름으로 칩이 하나 생긴다(새 분류를 넣고 묶음 추가를 잊어도 용어가 사라지지 않게).
 */
const GROUPS = TOPICS.categoryGroups ?? {};
const groupNameOf = (category) => Object.keys(GROUPS).find(g => GROUPS[g].includes(category)) ?? category;
export const glossaryCategories = () => [...new Set(DATA.categories.map(groupNameOf))];
export const categoryGroupOf = (t) => groupNameOf(t.category);

/**
 * 주제(경제 첫걸음 · 가계와 생활 · ...): 분류(category)와 별개의 갈래.
 * 용어마다 topic 을 따로 적지 않고 data/glossaryTopics.json 에서 정한다.
 *   우선순위: byTerm[id] → 용어 자신의 topic → byCategory[category] → defaultTopic
 */
export const glossaryTopics = () => TOPICS.topics;
export const topicOf = (t) => TOPICS.byTerm[t.id] ?? t.topic ?? TOPICS.byCategory[t.category] ?? TOPICS.defaultTopic;
export const glossaryTerms = () => [...DATA.terms].sort(compareTerms);

const normalize = (s) => String(s ?? '').toLowerCase().replace(/\s+/g, '');

/** 표제어·다른 이름·한 줄 뜻에서 찾는다(대소문자·띄어쓰기 무시) */
export const matchesTerm = (item, query) => {
    const q = normalize(query);
    return !q || [item.term, item.short, ...(item.aliases ?? [])].some(v => normalize(v).includes(q));
};
