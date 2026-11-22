/**
 * 목업: 트레이닝 차트 퀴즈(/api/v1/training/today · hint · answer · history · questions). npm run dev:mock 에서만 쓴다.
 * 차트는 시드 고정 난수로 지어낸 가상 시세다(실존 종목 아님). 서버 응답 모양은 py-yangbong-api router_training_chart.py 와 같다.
 * 구독 여부는 꿀 목업의 하루 이용권(hasPass)을 따른다 — 실제 서버와 같은 규칙.
 */
const rng = (seed) => () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const sma = (a, p) => a.map((_, i) => (i + 1 < p ? null : a.slice(i + 1 - p, i + 1).reduce((x, y) => x + y, 0) / p));
const ema = (a, p) => { const k = 2 / (p + 1); const o = []; a.forEach((x, i) => o.push(i ? k * x + (1 - k) * o[i - 1] : x)); return o; };
const rsi = (c, p = 14) => {
    const out = c.map(() => null);
    let ag = 0, al = 0;
    for (let i = 1; i <= p; i++) { const d = c[i] - c[i - 1]; ag += Math.max(d, 0) / p; al += Math.max(-d, 0) / p; }
    out[p] = al ? 100 - 100 / (1 + ag / al) : 100;
    for (let i = p + 1; i < c.length; i++) {
        const d = c[i] - c[i - 1];
        ag = (ag * (p - 1) + Math.max(d, 0)) / p; al = (al * (p - 1) + Math.max(-d, 0)) / p;
        out[i] = al ? 100 - 100 / (1 + ag / al) : 100;
    }
    return out;
};
const r2 = (v, n = 2) => (v == null ? null : Math.round(v * 10 ** n) / 10 ** n);

/** 가상 시세 300봉 → 기준일(뒤에서 21번째) 종가 = 100 으로 정규화한 문제 하나 */
const makeQuestion = (id, level, seed, drift) => {
    const r = rng(seed);
    const N = 300, base = N - 21;
    const closes = [];
    let p = 100;
    for (let i = 0; i < N; i++) {
        const trend = i > base ? drift : (i > base - 6 ? 0.9 : Math.sin(i / 17) * 0.25);
        p *= 1 + (trend + (r() - 0.5) * 3.2) / 100;
        closes.push(p);
    }
    const s = 100 / closes[base];
    const c = closes.map(x => x * s);
    const k = c.map((x, i) => {
        const o = (i ? c[i - 1] : x) * (1 + (r() - 0.5) * 0.01);
        return { o, c: x, h: Math.max(o, x) * (1 + r() * 0.012), l: Math.min(o, x) * (1 - r() * 0.012), v: 60 + r() * 80 + (i === base ? 220 : 0) };
    });
    const ma = { 5: sma(c, 5), 20: sma(c, 20), 60: sma(c, 60), 120: sma(c, 120) };
    const m = ema(c, 12).map((x, i) => x - ema(c, 26)[i]);
    const sg = ema(m, 9);
    const sd = c.map((_, i) => (i < 19 ? null : Math.sqrt(c.slice(i - 19, i + 1).reduce((a, x) => a + (x - ma[20][i]) ** 2, 0) / 20)));
    const rs = rsi(c);
    const slice = (a, b) => ({
        ma: Object.fromEntries(Object.entries(ma).map(([kk, v]) => [kk, v.slice(a, b).map(x => r2(x))])),
        rsi14: rs.slice(a, b).map(x => r2(x, 1)),
        macd: { macd: m.slice(a, b).map(x => r2(x, 3)), signal: sg.slice(a, b).map(x => r2(x, 3)), hist: m.slice(a, b).map((x, i) => r2(x - sg[a + i], 3)) },
        bollinger: {
            upper: ma[20].slice(a, b).map((x, i) => r2(x + 2 * sd[a + i])),
            mid: ma[20].slice(a, b).map(x => r2(x)),
            lower: ma[20].slice(a, b).map((x, i) => r2(x - 2 * sd[a + i])),
        },
    });
    const candle = (i, t) => ({ t, o: r2(k[i].o), h: r2(k[i].h), l: r2(k[i].l), c: r2(k[i].c), v: r2(k[i].v, 1) });
    const a = base - 119;
    const candles = Array.from({ length: 120 }, (_, j) => candle(a + j, j === 119 ? 'D' : `D-${119 - j}`));
    candles[119].c = 100;
    const future = Array.from({ length: 20 }, (_, j) => candle(base + 1 + j, `D+${j + 1}`));
    const ret = r2((c[base + 20] / 100 - 1) * 100, 1);
    const lows = future.map(f => f.l), highs = future.map(f => f.h);
    return {
        id, level,
        question: {
            questionId: id, level,
            defaultIndicators: { 1: ['MA'], 2: ['MA', 'VOLUME'], 3: ['MA', 'VOLUME', 'RSI', 'MACD'], 4: ['MA', 'VOLUME', 'RSI', 'MACD', 'BOLLINGER'] }[level],
            availableIndicators: ['MA', 'VOLUME', 'RSI', 'MACD', 'BOLLINGER'],
            basePrice: 100, baseChangeRate: r2((c[base] / c[base - 1] - 1) * 100, 1),
            snapshot: { candles, indicators: slice(a, base + 1) },
        },
        future, futureIndicators: slice(base + 1, base + 21),
        outcome: { returnRate: ret, maxDrawdown: r2(Math.min(0, (Math.min(...lows) / 100 - 1) * 100), 1), maxGain: r2(Math.max(0, (Math.max(...highs) / 100 - 1) * 100), 1) },
        direction: ret >= 5 ? 'UP' : ret <= -5 ? 'DOWN' : 'FLAT',
        hint: '마지막 봉의 종가가 20일선(초록)과 어떤 위치에 있는지, 그날 거래량이 평소보다 얼마나 많은지 보세요.',
        explanation: '마지막 봉에서 종가가 20일선을 위로 넘었고, 거래량은 직전 20일 평균의 3.1배였어요. 이후 20일 동안의 움직임은 위 숫자와 같아요.',
    };
};

const QS = [makeQuestion(9001, 1, 11, 0.45), makeQuestion(9002, 2, 23, -0.4), makeQuestion(9003, 2, 37, 0.05),
    makeQuestion(9004, 3, 41, 0.6), makeQuestion(9005, 4, 53, -0.5)];
const STATE = { attempts: {}, hints: new Set(), setIds: [9001, 9002, 9003] };
const byId = (id) => QS.find(q => q.id === Number(id));

export const chartQuizRoutes = ({ ok, body, hasPass }) => {
    const quota = () => {
        const used = STATE.setIds.filter(i => STATE.attempts[i]).length;
        return hasPass() ? { isSubscriber: true, dailyLimit: null, used, remaining: null }
            : { isSubscriber: false, dailyLimit: 3, used, remaining: Math.max(0, 3 - used) };
    };
    const total = () => Object.values(STATE.attempts).reduce((a, x) => a + x.score, 0);
    const extend = () => {
        const more = QS.find(q => !STATE.setIds.includes(q.id));
        if (more) STATE.setIds.push(more.id);
        return more?.id ?? null;
    };
    const canOpen = (q) => STATE.setIds.includes(q.id) || (hasPass() && STATE.attempts[q.id]);
    const sub403 = { __error: 403, code: 'SUBSCRIPTION_REQUIRED', message: '구독하면 지난 문제를 다시 풀 수 있어요.' };
    return [
        ['GET', '/api/v1/training/today', () => {
            let todo = STATE.setIds.filter(i => !STATE.attempts[i]);
            if (hasPass() && !todo.length) { const n = extend(); if (n) todo = [n]; }
            return ok({ ready: true, setDate: new Date().toISOString().slice(0, 10), quota: quota(), streakDays: 3, totalScore: total(),
                questions: todo.map(i => byId(i).question) });
        }],
        ['GET', /^\/api\/v1\/training\/questions\/(\d+)$/, (c, m) => {
            const q = byId(m[1]);
            if (!q) return { __error: 404, code: 'NOT_FOUND', message: '문제를 찾을 수 없어요.' };
            return canOpen(q) ? ok(q.question) : sub403;
        }],
        ['POST', /^\/api\/v1\/training\/(\d+)\/hint$/, (c, m) => {
            const q = byId(m[1]);
            if (!q || !canOpen(q)) return sub403;
            STATE.hints.add(q.id);
            return ok({ hint: q.hint, scoreMultiplier: 0.8 });
        }],
        ['POST', /^\/api\/v1\/training\/(\d+)\/answer$/, (c, m) => {
            const q = byId(m[1]);
            if (!q || !canOpen(q)) return sub403;
            const { answer, usedHint } = body(c);
            const isMatch = answer === q.direction;
            const retry = !!STATE.attempts[q.id];
            const hintUsed = !!usedHint || STATE.hints.has(q.id);
            const score = retry || !isMatch ? 0 : Math.round(100 * (hintUsed ? 0.8 : 1));
            if (!retry) STATE.attempts[q.id] = { answer, isMatch, score, at: Date.now() };
            let next = null;
            if (STATE.setIds.includes(q.id)) {
                next = STATE.setIds.find(i => !STATE.attempts[i]) ?? (hasPass() ? extend() : null);
            }
            return ok({
                attemptId: q.id, isMatch, score, usedHint: hintUsed, matchStreak: isMatch ? 1 : 0, retry,
                outcome: q.outcome, futureCandles: q.future, futureIndicators: q.futureIndicators, explanation: q.explanation,
                pattern: { patternId: 1, name: '20일선 돌파 + 거래량 2배', stat: { windowMonths: 12, occurrences: 38, upCount: 21, downCount: 11, flatCount: 6 },
                    caseListLocked: !hasPass(), casePreview: hasPass() ? null : 3 },
                nextQuestionId: next, quota: quota(), totalScore: total(), streakDays: 3,
            });
        }],
        ['GET', '/api/v1/training/history', () => {
            if (!hasPass()) return sub403;
            return ok(Object.entries(STATE.attempts).filter(([, a]) => !a.isMatch).map(([id, a]) => ({
                questionId: Number(id), level: byId(id).level, patternName: '20일선 돌파 + 거래량 2배', answer: a.answer,
                isMatch: false, score: 0, answeredAt: a.at,
            })));
        }],
    ];
};
