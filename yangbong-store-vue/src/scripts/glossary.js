/**
 * 주식 용어 사전 데이터 도우미. 용어 내용은 data/glossary.json 에서만 고친다.
 *   term 표제어 · short 목록의 한 줄 뜻 · easy 쉽게 말하면 · example 예시 · caution 헷갈리기 쉬운 점
 *   aliases 검색용 다른 이름 · related 관련 용어(term 이름) · lesson 관련 강의("<장 slug>/<단계 id>")
 *   figure(선택) 양봉·음봉처럼 그림이 필요한 설명
 */
import DATA from './data/glossary.json';

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

export const glossaryCategories = () => DATA.categories;
export const glossaryTerms = () => [...DATA.terms].sort(compareTerms);

const normalize = (s) => String(s ?? '').toLowerCase().replace(/\s+/g, '');

/** 표제어·다른 이름·한 줄 뜻에서 찾는다(대소문자·띄어쓰기 무시) */
export const matchesTerm = (item, query) => {
    const q = normalize(query);
    return !q || [item.term, item.short, ...(item.aliases ?? [])].some(v => normalize(v).includes(q));
};
