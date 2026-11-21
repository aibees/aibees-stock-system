/**
 * 내 설정의 보조지표 — 정의·기본값·판정. 화면 의존 없는 순수 함수.
 *
 * 지표마다 켜고 끌 수 있고 수치(기간·배수·일수 등)를 고칠 수 있다. 성향 preset(안정/균형/공격)은
 * 이 수치들을 미리 정해 둔 묶음일 뿐이다(scripts/data/personaConfig.json 의 types[].settings).
 * 손절·익절 같은 매도 기준은 양봉상회에 없다(2026-11-15) — 여기는 "어떤 회사를 볼 것인가"의 조건만 다룬다.
 *
 * 판정은 서버가 준 buy-target 한 행의 chart_data(일봉 OHLCV)로 화면에서 다시 계산한다(서버 플래그는 쓰지 않는다).
 * 그래서 후보는 서버가 이미 추린 종목 안에서만 고를 수 있다 — 조건을 더 엄격하게는 가능하지만 넓혀서 새 종목을 불러오진 못한다.
 */
import { numOrNull, volumeFacts } from './stockSignals.js';
import { volatilityPct } from './persona.js';

/**
 * 지표 정의. params 는 화면의 − + 입력 범위(choices 가 있으면 그 값들 사이만 오간다).
 *
 * tier (2026-11-22 내 설정 개편)
 *   basic   : 기본 제공 — 거래량 급증·MACD·OBV·이평선(5·20·60)·볼린저밴드·ATR.
 *             트레이닝에서 그 지표의 단계(lesson, 트레이닝 단계 key)를 마치면 내 설정에서 직접 켜고 끌 수 있다.
 *             마치기 전에는 성향(preset)이 정한 값 그대로 쓰이고, 화면에서는 반투명하게 잠가 둔다.
 *             lesson 이 null 이면 아직 그 지표의 트레이닝이 없어 열리지 않는다.
 *   premium : 프리미엄(준비 중) — 화면에서 가리고, 판정에도 쓰지 않는다(normalizeSettings 가 항상 끈다).
 */
export const INDICATORS = [
    { key: 'surge', label: '거래량 급증', tier: 'basic', lesson: 'chart-basic/volume',
      desc: '며칠 안에 전날보다 거래가 갑자기 늘었는가',
      params: [{ key: 'ratio', label: '전날의', unit: '배 이상', min: 1.5, max: 10, step: 0.5 },
               { key: 'days', label: '최근', unit: '일 안에', min: 1, max: 10, step: 1 }] },
    { key: 'macd', label: 'MACD', tier: 'basic', lesson: 'chart-advanced/macd-obv',
      desc: '내리던 흐름이 오름으로 바뀌었는가(MACD선이 시그널선을 위로 뚫음)',
      params: [{ key: 'fast', label: '짧은 기간', unit: '일', min: 3, max: 20, step: 1 },
               { key: 'slow', label: '긴 기간', unit: '일', min: 10, max: 60, step: 1 },
               { key: 'signal', label: '시그널', unit: '일', min: 3, max: 20, step: 1 },
               { key: 'days', label: '최근', unit: '일 안에', min: 1, max: 10, step: 1 }] },
    { key: 'obv', label: 'OBV', tier: 'basic', lesson: 'chart-advanced/macd-obv',
      desc: '사려는 거래가 늘고 있는가(OBV가 평균선을 위로 뚫음)',
      params: [{ key: 'ma', label: '평균 기간', unit: '일', min: 3, max: 30, step: 1 },
               { key: 'days', label: '최근', unit: '일 안에', min: 1, max: 10, step: 1 }] },
    { key: 'ma', label: '이평선', tier: 'basic', lesson: 'chart-basic/ma',
      desc: '종가가 평균 가격(5·20·60일선) 위에 있는가',
      params: [{ key: 'period', label: '', unit: '일선 위', min: 5, max: 60, step: 1, choices: [5, 20, 60] }] },
    { key: 'bb', label: '볼린저밴드', tier: 'basic', lesson: 'chart-advanced/bb',
      desc: '종가가 밴드 상단 아래라서 아직 과열은 아닌가',
      params: [{ key: 'period', label: '기간', unit: '일', min: 5, max: 60, step: 1 },
               { key: 'std', label: '폭', unit: '배(표준편차)', min: 1, max: 3, step: 0.5 }] },
    { key: 'volat', label: 'ATR(가격변동성)', tier: 'basic', lesson: 'chart-advanced/atr',
      desc: '최근 20일 하루 평균 가격 움직임(ATR)이 종가의 일정 % 이상인가',
      params: [{ key: 'minPct', label: '하루 평균', unit: '% 이상', min: 1, max: 15, step: 0.5 }] },

    // ── 프리미엄(준비 중) ──
    { key: 'volume', label: '거래량 평균 대비', tier: 'premium', lesson: null,
      desc: '오늘 거래량이 최근 N일 평균의 M배 이상인가',
      params: [{ key: 'ratio', label: '최근 20일 평균의', unit: '배 이상', min: 1, max: 10, step: 0.5 }] },
    { key: 'cap', label: '회사 규모', tier: 'premium', lesson: null,
      desc: '시가총액이 일정 크기 이상인가',
      params: [{ key: 'minEok', label: '시가총액', unit: '억 원 이상', min: 100, max: 100000, step: 100 }] },
];
export const BASIC_INDICATORS = INDICATORS.filter(d => d.tier === 'basic');
export const PREMIUM_INDICATORS = INDICATORS.filter(d => d.tier === 'premium');
const isPremium = (key) => PREMIUM_INDICATORS.some(d => d.key === key);

/** choices 가 있는 수치는 가장 가까운 선택지로 맞춘다. */
const snapChoice = (p, v) => (p.choices
    ? p.choices.reduce((best, c) => (Math.abs(c - v) < Math.abs(best - v) ? c : best), p.choices[0])
    : v);

export const ORDER_OPTIONS = [
    { key: 'default',    label: '시장이 주목하는 순서', desc: '서버가 정한 순서 그대로' },
    { key: 'market_cap', label: '큰 회사 먼저',         desc: '시가총액이 큰 회사부터' },
    { key: 'volatility', label: '크게 움직이는 회사 먼저', desc: '최근 가격 변동이 큰 회사부터' },
];
export const orderLabel = (key) => (ORDER_OPTIONS.find(o => o.key === key) ?? ORDER_OPTIONS[0]).label;

/** 지표 기본 수치(모두 끔 상태가 아니라 "균형형 바탕"). preset 이 이 위에 덮어쓴다. */
export const DEFAULT_SETTINGS = {
    minPass: 2,
    order: 'default',
    volume: { on: false, ratio: 1.5 },   // 프리미엄(준비 중) — 항상 꺼짐
    surge:  { on: false, ratio: 3, days: 5 },
    macd:   { on: true,  fast: 12, slow: 26, signal: 9, days: 3 },
    obv:    { on: true,  ma: 9, days: 3 },
    ma:     { on: true,  period: 20 },
    bb:     { on: false, period: 20, std: 2 },
    cap:    { on: false, minEok: 1000 },  // 프리미엄(준비 중) — 항상 꺼짐
    volat:  { on: false, minPct: 3 },
};

const clamp = (v, min, max, fallback) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return fallback;
    return Math.min(max, Math.max(min, n));
};

/** 모르는 값·빠진 값·범위 밖 값을 기본값/범위로 바로잡은 새 객체. base 는 비어 있는 칸을 채울 값. */
export const normalizeSettings = (s, base = DEFAULT_SETTINGS) => {
    const out = {};
    const onCount = (o) => BASIC_INDICATORS.filter(d => o[d.key]?.on).length;
    for (const d of INDICATORS) {
        const b = base[d.key] ?? DEFAULT_SETTINGS[d.key];
        const v = s?.[d.key] ?? {};
        // 프리미엄 지표는 준비 중이라 저장된 값·성향과 관계없이 항상 끈다
        const row = { on: isPremium(d.key) ? false : (typeof v.on === 'boolean' ? v.on : !!b.on) };
        for (const p of d.params) row[p.key] = snapChoice(p, clamp(v[p.key] ?? b[p.key], p.min, p.max, b[p.key] ?? p.min));
        out[d.key] = row;
    }
    if (out.macd.fast >= out.macd.slow) out.macd.fast = Math.max(3, out.macd.slow - 1);
    out.order = ORDER_OPTIONS.some(o => o.key === s?.order) ? s.order : (base.order ?? 'default');
    const on = Math.max(1, onCount(out));
    out.minPass = Math.round(clamp(s?.minPass ?? base.minPass, 1, on, Math.min(on, 2)));
    return out;
};

/** 두 설정이 같은 값인가(preset 과 같은지 비교). */
export const sameSettings = (a, b) => JSON.stringify(normalizeSettings(a)) === JSON.stringify(normalizeSettings(b));

const fmtNum = (n) => (Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10));
const eokText = (n) => (n >= 10000 ? `${fmtNum(n / 10000)}조` : `${n.toLocaleString()}억`);

/** 지표 한 줄 요약(내 설정 보기·목록용). 꺼져 있으면 null. 예) "평소 거래량의 1.5배 이상" */
export const indicatorSummary = (key, s) => {
    const v = s[key];
    if (!v?.on || isPremium(key)) return null;
    switch (key) {
        case 'volume': return `최근 20일 평균의 ${fmtNum(v.ratio)}배 이상`;
        case 'surge':  return `최근 ${v.days}일 안에 전날의 ${fmtNum(v.ratio)}배 이상`;
        case 'macd':   return `${v.fast}·${v.slow}·${v.signal}일, 최근 ${v.days}일 안에 오름 신호`;
        case 'obv':    return `${v.ma}일 평균 돌파, 최근 ${v.days}일 안에`;
        case 'ma':     return `${v.period}일선 위`;
        case 'bb':     return `${v.period}일, 폭 ${fmtNum(v.std)}배 — 상단 아래`;
        case 'cap':    return `시가총액 ${eokText(v.minEok)} 원 이상`;
        case 'volat':  return `하루 평균 ${fmtNum(v.minPct)}% 이상 움직임`;
        default: return null;
    }
};

/** 켜 둔 지표(프리미엄은 쓰지 않으므로 빼고 센다). */
export const enabledKeys = (s) => BASIC_INDICATORS.filter(d => s[d.key]?.on).map(d => d.key);

/** "N개 중 M개 이상" 문구. */
export const passRuleText = (s) => {
    const n = enabledKeys(s).length;
    if (!n) return '켜 둔 지표가 없어 모든 회사를 보여 드려요';
    const m = Math.min(s.minPass, n);
    return m >= n ? `켜 둔 ${n}개 지표를 모두 충족` : `켜 둔 ${n}개 지표 중 ${m}개 이상 충족`;
};

/* ── 계산 ── */
const closesOf = (rows) => rows.map(r => numOrNull(r.close));

const ema = (values, period) => {
    const k = 2 / (period + 1);
    const out = [];
    let prev = null;
    for (const v of values) {
        if (v === null) { out.push(null); continue; }
        prev = prev === null ? v : v * k + prev * (1 - k);
        out.push(prev);
    }
    return out;
};
const sma = (values, period, end) => {
    const seg = values.slice(Math.max(0, end - period + 1), end + 1);
    if (seg.length < period || seg.some(v => v === null)) return null;
    return seg.reduce((a, b) => a + b, 0) / period;
};
/** 마지막 days 개 봉 안에 a 가 b 를 아래에서 위로 뚫었는가. */
const crossedUp = (a, b, days) => {
    for (let i = a.length - 1; i >= Math.max(1, a.length - days); i--) {
        if ([a[i], b[i], a[i - 1], b[i - 1]].some(v => v === null || v === undefined)) continue;
        if (a[i - 1] <= b[i - 1] && a[i] > b[i]) return true;
    }
    return false;
};

const barsOf = (item) => {
    const ymd = String(item?.ymd || '');
    return (item?.chart_data || []).filter(r => !ymd || String(r.date || '').slice(0, 10).replaceAll('-', '') <= ymd);
};

/**
 * 한 행을 설정으로 판정한다.
 *   rows  : 켜 둔 지표별 {key, label, pass, text}. text 는 충족했을 때 보여 줄 쉬운 말(꺼진 지표는 없다).
 *   pass  : 충족한 지표 수 / total: 켜 둔 지표 수
 *   match : pass >= minPass (켜 둔 지표가 없으면 true)
 */
export const evaluate = (item, settings) => {
    const s = normalizeSettings(settings);
    const bars = barsOf(item);
    const closes = closesOf(bars);
    const rows = [];

    for (const d of INDICATORS) {
        const v = s[d.key];
        if (!v.on) continue;
        let pass = false;
        let text = '';

        if (d.key === 'volume') {
            const { avgRatio } = volumeFacts({ ...item, chart_data: bars });
            pass = avgRatio !== null && avgRatio >= v.ratio;
            if (pass) text = `거래량이 평소의 ${avgRatio >= 10 ? Math.round(avgRatio).toLocaleString() : avgRatio.toFixed(1)}배`;
        } else if (d.key === 'surge') {
            let best = null;
            for (let i = Math.max(1, bars.length - v.days); i < bars.length; i++) {
                const prev = numOrNull(bars[i - 1].volume);
                const cur = numOrNull(bars[i].volume);
                if (!prev || cur === null) continue;
                if (best === null || cur / prev > best) best = cur / prev;
            }
            pass = best !== null && best >= v.ratio;
            if (pass) text = `최근 ${v.days}일 안에 거래가 전날의 ${best.toFixed(1)}배로 늘었어요`;
        } else if (d.key === 'macd') {
            if (closes.length >= v.slow + v.signal) {
                const line = ema(closes, v.fast).map((x, i) => {
                    const slow = ema(closes, v.slow)[i];
                    return x === null || slow === null ? null : x - slow;
                });
                const sig = ema(line, v.signal);
                pass = crossedUp(line, sig, v.days);
            }
            if (pass) text = '내리던 흐름이 오름으로 바뀌었어요';
        } else if (d.key === 'obv') {
            if (bars.length > v.ma + 1) {
                const obv = [0];
                for (let i = 1; i < bars.length; i++) {
                    const c = closes[i], p = closes[i - 1], vol = numOrNull(bars[i].volume) ?? 0;
                    obv.push(obv[i - 1] + (c > p ? vol : (c < p ? -vol : 0)));
                }
                const avg = obv.map((_, i) => sma(obv, v.ma, i));
                pass = crossedUp(obv, avg, v.days);
            }
            if (pass) text = '사려는 거래가 늘고 있어요';
        } else if (d.key === 'ma') {
            const avg = sma(closes, v.period, closes.length - 1);
            const last = closes[closes.length - 1];
            pass = avg !== null && last !== null && last > avg;
            if (pass) text = `${v.period}일 평균 가격보다 위에 있어요`;
        } else if (d.key === 'bb') {
            const end = closes.length - 1;
            const mid = sma(closes, v.period, end);
            if (mid !== null) {
                const seg = closes.slice(end - v.period + 1, end + 1);
                const sd = Math.sqrt(seg.reduce((a, c) => a + (c - mid) ** 2, 0) / v.period);
                pass = closes[end] <= mid + v.std * sd;
            }
            if (pass) text = '아직 크게 오르진 않았어요';
        } else if (d.key === 'cap') {
            const cap = numOrNull(item.market_cap);
            pass = cap !== null && cap >= v.minEok;
            if (pass) text = `시가총액 ${eokText(cap)} 원`;
        } else if (d.key === 'volat') {
            const vol = volatilityPct({ ...item, chart_data: bars });
            pass = vol !== null && vol >= v.minPct;
            if (pass) text = `하루 평균 ${vol.toFixed(1)}% 움직여요`;
        }
        rows.push({ key: d.key, label: d.label, pass, text });
    }

    const passCount = rows.filter(r => r.pass).length;
    return { rows, pass: passCount, total: rows.length, match: rows.length === 0 || passCount >= Math.min(s.minPass, rows.length) };
};

/** 충족한 지표의 쉬운 말(앞에서부터). */
export const passedReasons = (ev) => ev.rows.filter(r => r.pass && r.text).map(r => r.text);
