/** 오늘의 경제 이슈 날짜 글자. '20261122' → '11. 22. (일)' */
const WD = '일월화수목금토';
export const issueDateText = (ymd) => {
    if (!ymd || ymd.length !== 8) return '';
    const d = new Date(Number(ymd.slice(0, 4)), Number(ymd.slice(4, 6)) - 1, Number(ymd.slice(6)));
    return `${d.getMonth() + 1}. ${d.getDate()}. (${WD[d.getDay()]})`;
};
/** '20261120' → '11/20' */
export const shortDate = (ymd) => (ymd && ymd.length === 8 ? `${Number(ymd.slice(4, 6))}/${Number(ymd.slice(6))}` : '');
