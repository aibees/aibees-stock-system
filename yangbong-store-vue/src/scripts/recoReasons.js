/**
 * 매수추천 "추천 이유" — 보조지표 판정(conditionSummary)을 초보자가 읽을 수 있는 한 문장으로 바꾼다(2026-11-17).
 *
 *   recoReasons(item) → { top, rest, passed, failed }
 *     passed : 충족한 지표의 이유 문장(아래 PRIORITY 순서). 목록 줄에는 passed[0] 하나만, 나머지는 개수로.
 *     failed : 미달 지표의 "아직 아닌 것" 문장(펼친 상세에서 연하게).
 *
 * 판정 자체는 stockSignals.js 그대로다 — 여기서는 문장만 고른다. 투자 권유로 읽히지 않게 사실만 말한다.
 */
import { conditionSummary, volumeFacts } from './stockSignals.js';

// 목록 줄 한 문장으로 무엇을 먼저 보여줄지: 초보자가 바로 와닿는 것부터
const PRIORITY = ['거래급등', 'MACD 크로스', 'BB중심돌파', 'OBV 크로스', '중심선위', 'BB상단아래', '거래제한'];

const ratioText = (r) => (r >= 10 ? Math.round(r).toLocaleString() : r.toFixed(1));

const TEXT = {
    '거래급등': {
        name: '거래급증',
        pass: (f) => (f.surge ? `거래량이 전날보다 ${ratioText(f.surge.ratio)}배 늘었어요` : '거래량이 갑자기 늘었어요'),
        detail: (f) => (f.surge ? `거래급증 · ${f.surge.date} 기준` : '거래급증'),
        fail: '거래량이 크게 늘지는 않았어요',
    },
    'MACD 크로스': { name: 'MACD', pass: '오르는 흐름으로 바뀌는 신호가 나왔어요', fail: '흐름이 바뀌는 신호는 아직이에요' },
    'BB중심돌파': { name: '볼린저밴드 돌파', pass: '가격이 평균 범위 위로 올라섰어요', fail: '가격이 평균 범위 위로 올라서진 않았어요' },
    'OBV 크로스': { name: 'OBV', pass: '사려는 돈이 꾸준히 들어오고 있어요', fail: '사려는 돈이 들어오는 흐름은 약해요' },
    '중심선위': { name: '20일선', pass: '20일 평균 가격보다 위에 있어요', fail: '20일 평균 가격 아래에 있어요' },
    'BB상단아래': { name: '비과열', pass: '아직 많이 오르지 않은 편이에요', fail: '최근 많이 오른 편이에요' },
    '거래제한': { name: '거래량', pass: '거래가 충분히 활발해요', fail: '거래가 아직 적은 편이에요' },
};

const call = (v, f) => (typeof v === 'function' ? v(f) : v);

export const recoReasons = (item) => {
    const facts = volumeFacts(item);
    const rows = conditionSummary(item).rows
        .filter(r => TEXT[r.key])
        .sort((a, b) => PRIORITY.indexOf(a.key) - PRIORITY.indexOf(b.key));

    const passed = rows.filter(r => r.pass).map(r => ({
        key: r.key,
        text: call(TEXT[r.key].pass, facts),
        detail: call(TEXT[r.key].detail, facts) ?? TEXT[r.key].name,
    }));
    const failed = rows.filter(r => !r.pass).map(r => ({
        key: r.key,
        text: TEXT[r.key].fail,
        detail: TEXT[r.key].name,
    }));
    return { passed, failed, top: passed[0] ?? null, rest: Math.max(0, passed.length - 1) };
};
