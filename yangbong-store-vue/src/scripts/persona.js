/**
 * 성향(persona) — 온보딩 질문, 유형 판정, 유형별 목록 순서. 화면 의존 없는 순수 함수.
 *
 * 유형은 코드가 아니라 데이터다(기획안 3.4 "유형을 데이터로 관리").
 *   정본: 공통코드 master_codes stock/setting/screen 의 PERSONA_CONFIG (desc 에 JSON 한 덩어리)
 *         → /master/menus/my 응답의 settings 로 온다(비로그인 포함).
 *   기본값: data/personaConfig.json — 공통코드가 없거나 형식이 틀리면 이걸 쓴다.
 *   앱은 웹 빌드를 내장하므로 기본값을 바꾸면 새 빌드가 필요하다. 공통코드는 배포 없이 바뀐다.
 *
 * 유형(preset)은 보조지표 수치 묶음(types[].settings)이다 — 지표 정의·판정은 scripts/indicators.js.
 * 손절·익절 같은 매도 기준은 양봉상회에 없다(2026-11-15). 같은 설정이면 누가 보든 같은 목록이어야 한다.
 */
import DEFAULT_CONFIG from './data/personaConfig.json';
import { numOrNull, volumeFacts } from './stockSignals.js';

export const SETTING_CODE = 'PERSONA_CONFIG';

const validConfig = (c) =>
    c && Array.isArray(c.types) && c.types.length > 0
    && c.types.every(t => t && t.key && t.name && t.settings && typeof t.settings === 'object')
    && Array.isArray(c.questions) && c.questions.length > 0
    && c.questions.every(q => q && q.text && Array.isArray(q.options) && q.options.length >= 2);

/** settings(공통코드 {code: desc})에서 설정을 읽는다. 없거나 깨졌으면 기본값. */
export const personaConfig = (settings) => {
    const raw = settings?.[SETTING_CODE];
    if (raw) {
        try {
            const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
            if (validConfig(parsed)) return parsed;
            console.warn('[persona] PERSONA_CONFIG 형식이 맞지 않아 기본값을 쓴다');
        } catch (e) {
            console.warn('[persona] PERSONA_CONFIG 를 읽지 못해 기본값을 쓴다', e);
        }
    }
    return DEFAULT_CONFIG;
};

/** key 로 유형을 찾는다. 없으면 기본 유형, 그것도 없으면 첫 유형. */
export const findType = (config, key) =>
    config.types.find(t => t.key === key)
    ?? config.types.find(t => t.key === config.defaultType)
    ?? config.types[0];

/**
 * 답으로 유형을 제안한다. answers[i] = 그 질문에서 고른 선택지 번호(없으면 null).
 * 'b' 가 있는 질문에서 b:true 를 고른 개수를 세어 bMin~bMax 에 드는 유형을 고른다.
 * 'mode' 가 있는 선택지는 화면(간편/전문가) 제안에 쓴다.
 */
export const suggestFromAnswers = (config, answers) => {
    let bCount = 0;
    let mode = null;
    config.questions.forEach((q, i) => {
        const opt = q.options[answers[i]];
        if (!opt) return;
        if (opt.b === true) bCount += 1;
        if (opt.mode) mode = opt.mode;
    });
    const type = config.types.find(t => bCount >= Number(t.bMin ?? 0) && bCount <= Number(t.bMax ?? Infinity))
        ?? findType(config, config.defaultType);
    return { type: type.key, mode: mode ?? 'simple', bCount };
};

/* ── 변동 크기: 최근 20일 평균 실제 변동폭(ATR) ÷ 종가 (%) ──
 * chart_data(일봉) 로 계산하고 표시일 이후 봉은 쓰지 않는다. 봉이 모자라면 null. */
const ATR_DAYS = 20;
export const volatilityPct = (item) => {
    const ymd = String(item?.ymd || '');
    const rows = (item?.chart_data || [])
        .filter(r => String(r.date || '').slice(0, 10).replaceAll('-', '') <= ymd)
        .map(r => ({ h: numOrNull(r.high), l: numOrNull(r.low), c: numOrNull(r.close) }))
        .filter(r => r.h !== null && r.l !== null && r.c !== null);
    if (rows.length < ATR_DAYS + 1) return null;
    const recent = rows.slice(-(ATR_DAYS + 1));
    let sum = 0;
    for (let i = 1; i < recent.length; i++) {
        const { h, l } = recent[i];
        const pc = recent[i - 1].c;
        sum += Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
    }
    const close = recent[recent.length - 1].c;
    return close > 0 ? (sum / ATR_DAYS) / close * 100 : null;
};

const ORDER_KEYS = {
    market_cap: (item) => numOrNull(item.market_cap),
    volatility: (item) => volatilityPct(item),
};

/**
 * 유형의 순서로 정렬한다. 서버 순서(index)를 동률 기준으로 써서 항상 같은 결과가 나온다.
 * 값이 없는 종목은 뒤로 보낸다. order 가 'default' 거나 모르는 값이면 서버 순서 그대로.
 */
export const orderForType = (items, type) => {
    const keyOf = ORDER_KEYS[type?.order];
    const indexed = (items || []).map((item, index) => ({ item, index }));
    if (!keyOf) return indexed.map(x => x.item);
    return indexed
        .map(x => ({ ...x, v: keyOf(x.item) }))
        .sort((a, b) => {
            if (a.v === null && b.v === null) return a.index - b.index;
            if (a.v === null) return 1;
            if (b.v === null) return -1;
            return b.v !== a.v ? b.v - a.v : a.index - b.index;
        })
        .map(x => x.item);
};

/** 사용자가 직접 정한 설정의 유형 key(preset 이 아님). 값은 persona 스토어의 custom 에 있다. */
export const CUSTOM_KEY = 'custom';

/**
 * 오늘 시장을 날씨로 비유한다(2026-11-15). 기준은 코스피·코스닥의 오늘 등락률 평균(avg).
 *   천둥번개 : 둘 중 하나라도 −5% 이하(사이드카가 걸릴 만한 급락)
 *   쾌청     : avg ≥ +1.5%   많이 오름
 *   따뜻     : avg ≥ 0       조금 오름(보합 포함)
 *   흐림     : avg < 0       조금 내림
 * 오늘 등락률은 서버의 rate(전일 종가 대비 %), 없으면 spark(최근 종가들)의 마지막 두 값으로 구한다. 둘 다 없으면 null(줄을 그리지 않는다).
 * 임계값은 초안 — 바꾸려면 아래 상수만 고친다.
 */
export const WEATHER_BIG_UP = 2;
export const WEATHER_STORM = -5;

export const dailyRate = (m) => {
    const r = numOrNull(m?.rate);
    if (r !== null) {
        return r;
    }
    const sp = (m?.spark || []).map(numOrNull).filter(v => v !== null);

    if (sp.length < 2 || !sp[sp.length - 2]) {
        return null;
    }
    return (sp[sp.length - 1] / sp[sp.length - 2] - 1) * 100;
};

export const marketWeather = (snapshot) => {
    const a = dailyRate((snapshot || []).find(m => m.key === 'kospi'));
    const b = dailyRate((snapshot || []).find(m => m.key === 'kosdaq'));

    if (a === null || b === null) {
        return null
    };
    const avg = (a + b) / 2;
    const base = { avg, kospi: a, kosdaq: b };

    if (Math.min(a, b) <= WEATHER_STORM) {
        return { ...base, key: 'storm', text: '천둥번개', desc: '시장이 크게 흔들리는 날이에요', cls: 'down' }
    };
    if (avg >= WEATHER_BIG_UP) {
        return { ...base, key: 'sunny', text: '쾌청', desc: '시장이 많이 오른 날이에요', cls: 'up' };
    }
    if (avg >= 0) {
        return { ...base, key: 'warm', text: '따뜻', desc: '시장이 조금 오른 날이에요', cls: 'up' };
    }
    return { ...base, key: 'cloudy', text: '흐림', desc: '시장이 조금 내린 날이에요', cls: 'down' };
};
