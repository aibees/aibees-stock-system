/**
 * 트레이닝 차트 퀴즈(2026-11-22). 명세: meetings/설계_2026-11-22_트레이닝-화면.md
 * 서버: py-yangbong-api router_training_chart.py (/api/v1/training/today · /<id>/hint · /<id>/answer · /history · /questions/<id>)
 *
 * 문구 규칙(명세 9장): 정답·오답·매수·매도·추천·승률이라고 쓰지 않는다.
 *   isMatch → "같은 방향을 봤어요 / 다른 방향이었어요". 방향 라벨(UP 등)은 보여 주지 않고 실제 수익률로만 쓴다.
 */
import aibeesApi from './aibeesApi.js';
import { markStudied } from './studyLog.js';

export const CHART_QUIZ_PATH = '/training/chart';
export const CHART_QUIZ_REVIEW_PATH = '/training/chart/review';

export const INDICATORS = [
    { key: 'MA', label: '이동평균' },
    { key: 'VOLUME', label: '거래량' },
    { key: 'RSI', label: 'RSI' },
    { key: 'MACD', label: 'MACD' },
    { key: 'BOLLINGER', label: '볼린저' },
];
const LABEL = Object.fromEntries(INDICATORS.map(i => [i.key, i.label]));

/** 문제 화면 우측 표시: "Lv.2 · 이동평균 + 거래량" */
export const levelText = (q) => `Lv.${q.level} · ${(q.defaultIndicators ?? []).map(k => LABEL[k] ?? k).join(' + ')}`;

export const CHOICES = [
    { key: 'UP', label: '상승', icon: '▲' },
    { key: 'FLAT', label: '보합', icon: '─' },
    { key: 'DOWN', label: '하락', icon: '▼' },
];

export const matchText = (isMatch) => (isMatch ? '같은 방향을 봤어요' : '다른 방향이었어요');
export const choiceLabel = (key) => CHOICES.find(c => c.key === key)?.label ?? '';

/** +7.4% / -4.0% / 0.0% */
export const signed = (n) => (n == null ? '-' : `${n > 0 ? '+' : ''}${Number(n).toFixed(1)}%`);

/** 지표 토글 상태는 세션 동안 다음 문제에도 유지한다(명세 3-1). null 이면 문제의 기본 켜짐을 쓴다. */
const TOGGLE_KEY = 'yb-chart-quiz-indicators';
export const loadToggles = () => {
    try {
        const v = JSON.parse(sessionStorage.getItem(TOGGLE_KEY) || 'null');
        return Array.isArray(v) ? v : null;
    } catch { return null; }
};
export const saveToggles = (keys) => {
    try { sessionStorage.setItem(TOGGLE_KEY, JSON.stringify(keys)); } catch { /* 이번 화면 동안만 */ }
};

// silentError: 화면이 이유(구독 필요 등)를 직접 보여 준다 — 인터셉터 alert 를 띄우지 않는다
const opt = { silentError: true };
const unwrap = (r) => r.data?.data;
export const errorCode = (e) => e?.error?.code ?? e?.response?.data?.error?.code ?? null;

export const fetchToday = () => aibeesApi.get('/api/v1/training/today', opt).then(unwrap);
export const fetchQuestion = (id) => aibeesApi.get(`/api/v1/training/questions/${id}`, opt).then(unwrap);
export const fetchHint = (id) => aibeesApi.post(`/api/v1/training/${id}/hint`, {}, opt).then(unwrap);
export const submitAnswer = (id, answer, usedHint) =>
    aibeesApi.post(`/api/v1/training/${id}/answer`, { answer, usedHint }, opt).then(unwrap)
        .then((res) => { markStudied(); return res; });   // 답이 접수된 날 = 학습한 날(홈 '이번 주 학습')
export const fetchHistory = () => aibeesApi.get('/api/v1/training/history', opt).then(unwrap);
