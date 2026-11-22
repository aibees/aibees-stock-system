<template>
    <div class="qc">
        <div v-if="on.includes('MA') || on.includes('BOLLINGER')" class="qc-legend" aria-hidden="true">
            <template v-if="on.includes('MA')">
                <span><i class="ma5"></i>5일</span>
                <span><i class="ma20"></i>20일</span>
                <span><i class="ma60"></i>60일</span>
            </template>
            <span v-if="on.includes('BOLLINGER')"><i class="bb"></i>볼린저</span>
        </div>

        <svg class="qc-svg" :viewBox="`0 0 ${W} ${totalH}`" role="img" :aria-label="ariaLabel">
            <!-- 이후 구간(문제: 비워 둔 자리, 결과: 이어 그린 20봉) -->
            <rect :x="futureX" y="0" :width="W - R - futureX" :height="totalH" class="qc-future-bg" :class="{ shown: revealed }" />
            <line :x1="futureX" :x2="futureX" y1="0" :y2="totalH" class="qc-boundary" />
            <text v-if="!revealed" :x="(futureX + W - R) / 2" :y="MAIN_H / 2 + 5" text-anchor="middle" class="qc-q">?</text>
            <text v-if="!revealed" :x="(futureX + W - R) / 2" :y="MAIN_H / 2 + 22" text-anchor="middle" class="qc-q-sub">20일 뒤</text>

            <!-- 본 차트 -->
            <g>
                <line v-for="t in yTicks" :key="`g${t.v}`" :x1="L" :x2="W - R" :y1="t.y" :y2="t.y" class="qc-grid" />
                <text v-for="t in yTicks" :key="`t${t.v}`" :x="W - R + 4" :y="t.y + 3.5" class="qc-axis">{{ t.label }}</text>
                <line v-if="revealed" :x1="L" :x2="W - R" :y1="y(100)" :y2="y(100)" class="qc-base" />

                <g v-if="on.includes('BOLLINGER')" class="qc-bb">
                    <polygon v-if="bbBand" :points="bbBand" class="band" />
                    <polyline :points="line(series.bb.upper)" />
                    <polyline :points="line(series.bb.lower)" />
                    <template v-if="revealed">
                        <polyline :points="line(series.bb.upper, y, true)" class="fadein" />
                        <polyline :points="line(series.bb.lower, y, true)" class="fadein" />
                    </template>
                </g>

                <g v-for="(b, i) in bars" :key="i" :class="['qc-c', b.cls, { fut: b.fut }]" :style="b.fut ? { animationDelay: `${b.k * STEP_MS}ms` } : null">
                    <line :x1="b.x" :x2="b.x" :y1="b.yh" :y2="b.yl" />
                    <rect :x="b.x - bw / 2" :y="b.top" :width="bw" :height="b.h" />
                </g>

                <g v-if="on.includes('MA')" class="qc-ma">
                    <template v-for="k in ['60', '20', '5']" :key="`ma${k}`">
                        <polyline :points="line(series.ma[k])" :class="`ma${k}`" />
                        <polyline v-if="revealed" :points="line(series.ma[k], y, true)" :class="`ma${k}`" class="fadein" />
                    </template>
                </g>
            </g>

            <!-- 거래량 -->
            <g v-if="on.includes('VOLUME')" :transform="`translate(0 ${panelTop.VOLUME})`">
                <line :x1="L" :x2="W - R" :y1="VOL_H" :y2="VOL_H" class="qc-grid" />
                <text :x="W - R + 4" y="9" class="qc-axis">거래량</text>
                <rect v-for="(b, i) in volBars" :key="`v${i}`" :class="['qc-v', b.cls, { fut: b.fut }]"
                    :style="b.fut ? { animationDelay: `${b.k * STEP_MS}ms` } : null"
                    :x="b.x - bw / 2" :y="b.y" :width="bw" :height="b.h" />
            </g>

            <!-- RSI -->
            <g v-if="on.includes('RSI')" :transform="`translate(0 ${panelTop.RSI})`">
                <rect :x="L" :y="ry(70)" :width="W - R - L" :height="ry(30) - ry(70)" class="qc-rsi-zone" />
                <line :x1="L" :x2="W - R" :y1="ry(70)" :y2="ry(70)" class="qc-grid" />
                <line :x1="L" :x2="W - R" :y1="ry(30)" :y2="ry(30)" class="qc-grid" />
                <text :x="W - R + 4" :y="ry(70) + 3.5" class="qc-axis">70</text>
                <text :x="W - R + 4" :y="ry(30) + 3.5" class="qc-axis">30</text>
                <text :x="L + 2" y="9" class="qc-axis">RSI</text>
                <polyline :points="line(series.rsi, ry)" class="qc-rsi" />
                <polyline v-if="revealed" :points="line(series.rsi, ry, true)" class="qc-rsi fadein" />
            </g>

            <!-- MACD -->
            <g v-if="on.includes('MACD')" :transform="`translate(0 ${panelTop.MACD})`">
                <line :x1="L" :x2="W - R" :y1="my(0)" :y2="my(0)" class="qc-grid" />
                <text :x="W - R + 4" :y="my(0) + 3.5" class="qc-axis">0</text>
                <text :x="L + 2" y="9" class="qc-axis">MACD</text>
                <rect v-for="(b, i) in histBars" :key="`h${i}`" :class="['qc-h', b.cls, { fut: b.fut }]"
                    :style="b.fut ? { animationDelay: `${b.k * STEP_MS}ms` } : null"
                    :x="b.x - bw / 2" :y="b.y" :width="bw" :height="b.h" />
                <polyline :points="line(series.macd.macd, my)" class="qc-macd" />
                <polyline :points="line(series.macd.signal, my)" class="qc-signal" />
                <template v-if="revealed">
                    <polyline :points="line(series.macd.macd, my, true)" class="qc-macd fadein" />
                    <polyline :points="line(series.macd.signal, my, true)" class="qc-signal fadein" />
                </template>
            </g>
        </svg>
    </div>
</template>

<script setup>
/**
 * 차트 퀴즈 차트. 서버가 계산해 둔 값을 그리기만 한다(지표 계산 없음).
 *  - 오른쪽 20봉 자리는 처음부터 비워 둔다. 결과(future 있음)가 오면 그 자리에 왼쪽부터 순서대로 그린다(약 700ms).
 *    prefers-reduced-motion 이면 CSS 가 애니메이션을 끄고 바로 보인다.
 *  - 지표를 모두 끄면 캔들만 남는다(아래 패널이 없어져도 높이만 줄어든다).
 */
const props = defineProps({
    candles: { type: Array, required: true },
    indicators: { type: Object, default: () => ({}) },
    future: { type: Array, default: null },
    futureIndicators: { type: Object, default: null },
    on: { type: Array, default: () => ['MA'] },
});

const W = 358, L = 4, R = 30;
const MAIN_H = 220, VOL_H = 44, SUB_H = 56, GAP = 10;
const FUTURE_SLOTS = 20;
const STEP_MS = 35;               // 20봉 × 35ms ≈ 700ms

const revealed = computed(() => Array.isArray(props.future) && props.future.length > 0);
const past = computed(() => props.candles ?? []);
const all = computed(() => (revealed.value ? [...past.value, ...props.future] : past.value));
const slots = computed(() => past.value.length + FUTURE_SLOTS);
const slotW = computed(() => (W - L - R) / Math.max(1, slots.value));
const bw = computed(() => Math.max(1, slotW.value * 0.62));
const xAt = (i) => L + slotW.value * (i + 0.5);
const futureX = computed(() => L + slotW.value * past.value.length);

/* 지표 배열(과거 + 결과 뒤 미래)을 한 줄로 */
const cat = (a, b) => [...(a ?? []), ...(revealed.value ? (b ?? []) : [])];
const series = computed(() => {
    const p = props.indicators ?? {}, f = props.futureIndicators ?? {};
    return {
        ma: Object.fromEntries(['5', '20', '60'].map(k => [k, cat(p.ma?.[k], f.ma?.[k])])),
        bb: { upper: cat(p.bollinger?.upper, f.bollinger?.upper), lower: cat(p.bollinger?.lower, f.bollinger?.lower) },
        rsi: cat(p.rsi14, f.rsi14),
        macd: {
            macd: cat(p.macd?.macd, f.macd?.macd),
            signal: cat(p.macd?.signal, f.macd?.signal),
            hist: cat(p.macd?.hist, f.macd?.hist),
        },
    };
});

/* 세로 범위: 캔들(+ 켜 둔 가격 지표) */
const range = computed(() => {
    let hi = -Infinity, lo = Infinity;
    const take = (v) => { if (v != null && Number.isFinite(v)) { hi = Math.max(hi, v); lo = Math.min(lo, v); } };
    all.value.forEach(c => { take(c.h); take(c.l); });
    if (props.on.includes('MA')) Object.values(series.value.ma).forEach(a => a.forEach(take));
    if (props.on.includes('BOLLINGER')) { series.value.bb.upper.forEach(take); series.value.bb.lower.forEach(take); }
    if (!Number.isFinite(hi)) return { hi: 101, lo: 99 };
    const pad = (hi - lo) * 0.06 || 1;
    return { hi: hi + pad, lo: lo - pad };
});
const TOP = 8, BOT = 6;
const y = (v) => TOP + (range.value.hi - v) / (range.value.hi - range.value.lo) * (MAIN_H - TOP - BOT);

const yTicks = computed(() => {
    const { hi, lo } = range.value;
    const raw = (hi - lo) / 4;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) ?? raw;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push({ v, y: y(v), label: Number(v.toFixed(1)).toString() });
    return out;
});

const candleCls = (c) => (c.c > c.o ? 'up' : c.c < c.o ? 'down' : 'flat');
const bars = computed(() => all.value.map((c, i) => {
    const top = Math.min(y(c.o), y(c.c));
    const fut = i >= past.value.length;
    return { x: xAt(i), yh: y(c.h), yl: y(c.l), top, h: Math.max(1, Math.abs(y(c.o) - y(c.c))), cls: candleCls(c), fut, k: i - past.value.length };
}));

/** 선 좌표. fut=false 는 과거 구간(기준일까지), true 는 기준일부터 이후 구간(결과 때 따로 그려 나중에 보인다) */
const line = (arr, fy = y, fut = false) => {
    const n = past.value.length;
    return arr.map((v, i) => {
        if (fut ? i < n - 1 : i >= n) return null;
        return v == null || !Number.isFinite(v) ? null : `${xAt(i).toFixed(1)},${fy(v).toFixed(1)}`;
    }).filter(Boolean).join(' ');
};
const bbBand = computed(() => {
    const u = series.value.bb.upper, d = series.value.bb.lower;
    const n = past.value.length;
    const up = u.map((v, i) => (v == null || i >= n ? null : `${xAt(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean);
    const dn = d.map((v, i) => (v == null || i >= n ? null : `${xAt(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).reverse();
    return up.length && dn.length ? [...up, ...dn].join(' ') : '';
});

/* 아래 패널 배치 */
const PANELS = [['VOLUME', VOL_H], ['RSI', SUB_H], ['MACD', SUB_H]];
const panelTop = computed(() => {
    let top = MAIN_H;
    const out = {};
    PANELS.forEach(([k, h]) => { if (props.on.includes(k)) { out[k] = top + GAP; top += GAP + h; } });
    out.end = top;
    return out;
});
const totalH = computed(() => panelTop.value.end);

const volBars = computed(() => {
    const vmax = Math.max(1, ...all.value.map(c => c.v ?? 0));
    return all.value.map((c, i) => {
        const h = ((c.v ?? 0) / vmax) * (VOL_H - 12);
        return { x: xAt(i), y: VOL_H - h, h, cls: candleCls(c), fut: i >= past.value.length, k: i - past.value.length };
    });
});

const ry = (v) => 4 + (100 - v) / 100 * (SUB_H - 8);

const macdRange = computed(() => {
    const vals = [...series.value.macd.macd, ...series.value.macd.signal, ...series.value.macd.hist].filter(v => v != null && Number.isFinite(v));
    const m = Math.max(0.01, ...vals.map(Math.abs));
    return m * 1.1;
});
const my = (v) => SUB_H / 2 - (v / macdRange.value) * (SUB_H / 2 - 4);
const histBars = computed(() => series.value.macd.hist.map((v, i) => {
    if (v == null || !Number.isFinite(v)) return null;
    const y0 = my(0), y1 = my(v);
    return { x: xAt(i), y: Math.min(y0, y1), h: Math.max(0.5, Math.abs(y1 - y0)), cls: v >= 0 ? 'up' : 'down', fut: i >= past.value.length, k: i - past.value.length };
}).filter(Boolean));

const ariaLabel = computed(() => {
    const n = past.value.length;
    if (!revealed.value) return `최근 ${n}일 차트. 마지막 종가를 100으로 맞췄어요.`;
    const last = props.future[props.future.length - 1];
    return `최근 ${n}일 차트와 이후 ${props.future.length}일. 20일 뒤 종가 ${last?.c}.`;
});
</script>

<style scoped lang="scss">
.qc { width: 100%; }
.qc-legend {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    span { display: inline-flex; align-items: center; gap: 5px; }
    i { width: 12px; height: 2px; border-radius: 1px; display: inline-block; }
    .ma5 { background: var(--ma5); }
    .ma20 { background: var(--ma20); }
    .ma60 { background: var(--ma60); }
    .bb { height: 6px; background: rgba(138, 123, 200, .18); border: 1px solid rgba(138, 123, 200, .55); box-sizing: border-box; }
}
.qc-svg { display: block; width: 100%; height: auto; overflow: visible; }
.qc-future-bg { fill: #FBF8F1; &.shown { fill: #F3EDDD; } }
.qc-boundary { stroke: #CBB173; stroke-width: 1; stroke-dasharray: 3 3; }
.qc-q { font-size: 20px; font-weight: 800; fill: #CBB173; }
.qc-q-sub { font-size: 10px; font-weight: 600; fill: var(--text-faint); }
.qc-grid { stroke: var(--line-soft); stroke-width: 1; }
.qc-base { stroke: var(--text-faint); stroke-width: .8; stroke-dasharray: 2 3; }
.qc-axis { font-size: 9px; fill: var(--text-faint); font-variant-numeric: tabular-nums; }

.qc-c {
    line { stroke-width: 1; }
    &.up { line { stroke: var(--up-chart); } rect { fill: var(--up-chart); } }
    &.down { line { stroke: var(--down-chart); } rect { fill: var(--down-chart); } }
    &.flat { line { stroke: var(--flat); } rect { fill: var(--flat); } }
}
.qc-v, .qc-h {
    &.up { fill: var(--up-line); }
    &.down { fill: var(--down-line); }
    &.flat { fill: var(--flat-line); }
}
.qc-ma polyline, .qc-rsi, .qc-macd, .qc-signal, .qc-bb polyline { fill: none; stroke-width: 1.3; stroke-linejoin: round; stroke-linecap: round; }
.qc-ma .ma5 { stroke: var(--ma5); }
.qc-ma .ma20 { stroke: var(--ma20); }
.qc-ma .ma60 { stroke: var(--ma60); }
.qc-bb polyline { stroke: rgba(138, 123, 200, .55); stroke-width: 1; }
.qc-bb .band { fill: rgba(138, 123, 200, .08); }
.qc-rsi { stroke: var(--ma60); }
.qc-rsi-zone { fill: rgba(239, 234, 220, .45); }
.qc-macd { stroke: var(--ma20); }
.qc-signal { stroke: var(--ma5); }

/* 결과: 이후 20봉을 왼쪽부터 차례로 */
.fut { opacity: 0; animation: qc-in .18s ease-out forwards; transform-box: fill-box; transform-origin: bottom; }
.fadein { animation: qc-fade .3s ease-out .7s both; }
@keyframes qc-in { from { opacity: 0; transform: scaleY(.4); } to { opacity: 1; transform: none; } }
@keyframes qc-fade { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
    .fut, .fadein { animation: none; opacity: 1; transform: none; }
}
</style>
