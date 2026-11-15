/**
 * 성향(persona) — 온보딩 질문, 유형 판정, 유형별 종목 순서·정리할 가격 계산. 화면 의존 없는 순수 함수.
 *
 * 유형·질문은 코드가 아니라 데이터다(기획안 3.4 "유형을 데이터로 관리").
 *   정본: 공통코드 master_codes stock/setting/screen 의 PERSONA_CONFIG (desc 에 JSON 한 덩어리)
 *         → /master/menus/my 응답의 settings 로 온다(비로그인 포함).
 *   기본값: data/personaConfig.json — 공통코드가 없거나 형식이 틀리면 이걸 쓴다.
 *   앱은 웹 빌드를 내장하므로 기본값을 바꾸면 새 빌드가 필요하다. 공통코드는 배포 없이 바뀐다.
 *
 * 2026-11-15 초안 결정(기획안 15장):
 *   - 성향은 목록을 거르지 않고 순서만 바꾼다(안정 = 시가총액 큰 순, 균형 = 서버 순서, 공격 = 변동 큰 순).
 *   - 살 만한 가격 = 표시일 종가, 정리할 가격 = 종가 × (1 − stopPct%) 를 호가 단위로 내림.
 *   - 같은 설정이면 누가 보든 같은 목록이어야 한다(동률은 서버 순서로 고정).
 */
import DEFAULT_CONFIG from './data/personaConfig.json';
import { numOrNull, volumeFacts } from './stockSignals.js';

export const SETTING_CODE = 'PERSONA_CONFIG';

const validConfig = (c) =>
    c && Array.isArray(c.types) && c.types.length > 0
    && c.types.every(t => t && t.key && t.name && Number.isFinite(Number(t.stopPct)))
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

/** 국내 주식 호가 단위(2023-01-25 이후 코스피·코스닥 공통). */
export const tickSize = (price) => {
    if (price < 2000) return 1;
    if (price < 5000) return 5;
    if (price < 20000) return 10;
    if (price < 50000) return 50;
    if (price < 200000) return 100;
    if (price < 500000) return 500;
    return 1000;
};

/** 정리할 가격: 종가 × (1 − stopPct%) 를 호가 단위로 내림. 종가가 없으면 null. */
export const stopPrice = (close, stopPct) => {
    const c = numOrNull(close);
    const p = Number(stopPct);
    if (c === null || c <= 0 || !Number.isFinite(p)) return null;
    const raw = c * (1 - p / 100);
    const tick = tickSize(raw);
    return Math.floor(raw / tick) * tick;
};

/* ── 한 줄 이유: 기존 조건 플래그를 쉬운 말로. 앞에서부터 최대 2개 ──
 * 용어 풀이(기획안 4.3): 거래량 급증 → "평소보다 N배 많이 거래됨". 지표 이름은 쓰지 않는다. */
const ratioText = (r) => (r >= 10 ? Math.round(r).toLocaleString() : r.toFixed(1));
export const plainReasons = (item) => {
    const out = [];
    const { avgRatio } = volumeFacts(item);
    if (avgRatio !== null && avgRatio >= 1.5) out.push(`평소보다 ${ratioText(avgRatio)}배 많이 거래됨`);
    else if (item.is_vol_surge === 'Y') out.push('최근 거래가 갑자기 늘어남');
    if (item.is_bb_mid_breakout === 'Y') out.push('최근 평균 가격 위로 올라섬');
    if (item.macd_cross === 'G') out.push('내리던 흐름이 오르는 쪽으로 바뀜');
    if (item.obv_cross === 'G') out.push('사려는 거래가 늘어나는 중');
    if (item.is_bb_mid_breakout !== 'Y' && item.is_over_on_mid === 'Y') out.push('최근 20일 평균 가격보다 위');
    if (item.is_under_bb_upper === 'Y') out.push('아직 크게 오르지는 않음');
    return out;
};
export const reasonText = (item) => plainReasons(item).slice(0, 2).join(' · ') || '여러 조건을 함께 만족';

/**
 * 시황 한 줄: 코스피·코스닥 20일 수익률이 둘 다 오르면 "오르는 흐름", 둘 다 내리면 "내리는 흐름",
 * 엇갈리면 "오르내리는 중". 둘 중 하나라도 값이 없으면 null(줄을 그리지 않는다).
 */
export const marketMood = (snapshot) => {
    const r20 = (key) => numOrNull((snapshot || []).find(m => m.key === key)?.rate_20d);
    const a = r20('kospi');
    const b = r20('kosdaq');
    if (a === null || b === null) return null;
    if (a > 0 && b > 0) return { text: '오르는 흐름', cls: 'up' };
    if (a < 0 && b < 0) return { text: '내리는 흐름', cls: 'down' };
    return { text: '오르내리는 중', cls: 'flat' };
};
