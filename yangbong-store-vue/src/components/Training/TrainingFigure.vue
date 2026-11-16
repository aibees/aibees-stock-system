<template>
    <!-- 캔들 구조: 양봉·음봉 하나씩, 네 가격과 몸통·꼬리 이름 -->
    <svg v-if="name === 'candle'" class="tf" viewBox="0 0 320 206" role="img"
        aria-label="양봉과 음봉의 구조. 몸통은 시가와 종가 사이, 꼬리는 고가와 저가까지">
        <g class="up">
            <line x1="92" y1="18" x2="92" y2="172" class="wick" />
            <rect x="74" y="58" width="36" height="72" rx="2" />
        </g>
        <g class="lbl">
            <text x="62" y="40" text-anchor="end">위꼬리</text>
            <text x="62" y="98" text-anchor="end">몸통</text>
            <text x="62" y="155" text-anchor="end">아래꼬리</text>
            <line x1="96" y1="18" x2="118" y2="18" class="lead" /><text x="122" y="22">고가</text>
            <line x1="112" y1="58" x2="118" y2="58" class="lead" /><text x="122" y="62">종가</text>
            <line x1="112" y1="130" x2="118" y2="130" class="lead" /><text x="122" y="134">시가</text>
            <line x1="96" y1="172" x2="118" y2="172" class="lead" /><text x="122" y="176">저가</text>
        </g>
        <g class="down">
            <line x1="226" y1="28" x2="226" y2="166" class="wick" />
            <rect x="208" y="52" width="36" height="70" rx="2" />
        </g>
        <g class="lbl">
            <line x1="230" y1="28" x2="252" y2="28" class="lead" /><text x="256" y="32">고가</text>
            <line x1="246" y1="52" x2="252" y2="52" class="lead" /><text x="256" y="56">시가</text>
            <line x1="246" y1="122" x2="252" y2="122" class="lead" /><text x="256" y="126">종가</text>
            <line x1="230" y1="166" x2="252" y2="166" class="lead" /><text x="256" y="170">저가</text>
        </g>
        <text x="92" y="200" text-anchor="middle" class="cap up-t">양봉</text>
        <text x="226" y="200" text-anchor="middle" class="cap down-t">음봉</text>
    </svg>

    <!-- 양봉·음봉·도지 비교 -->
    <svg v-else-if="name === 'bull-bear'" class="tf" viewBox="0 0 320 178" role="img"
        aria-label="양봉은 종가가 시가보다 높고, 음봉은 낮고, 도지는 거의 같다">
        <g class="up">
            <line x1="60" y1="14" x2="60" y2="128" class="wick" />
            <rect x="44" y="28" width="32" height="84" rx="2" />
        </g>
        <g class="down">
            <line x1="160" y1="14" x2="160" y2="128" class="wick" />
            <rect x="144" y="30" width="32" height="80" rx="2" />
        </g>
        <g class="doji">
            <line x1="260" y1="22" x2="260" y2="120" class="wick" />
            <rect x="244" y="69" width="32" height="3" />
        </g>
        <text x="60" y="152" text-anchor="middle" class="cap up-t">양봉</text>
        <text x="160" y="152" text-anchor="middle" class="cap down-t">음봉</text>
        <text x="260" y="152" text-anchor="middle" class="cap">도지</text>
        <g class="lbl small">
            <text x="60" y="170" text-anchor="middle">종가 &gt; 시가</text>
            <text x="160" y="170" text-anchor="middle">종가 &lt; 시가</text>
            <text x="260" y="170" text-anchor="middle">종가 ≈ 시가</text>
        </g>
    </svg>

    <!-- 예시 차트(거래량·이동평균선·지지/저항): 정해진 모양의 가상 시세로 그린다. 실제 종목이 아니다. -->
    <svg v-else-if="chart" class="tf" :viewBox="`0 0 ${W} ${chart.height}`" role="img" :aria-label="chart.label">
        <g v-for="(ln, i) in chart.hlines" :key="`h${i}`" class="hline">
            <rect :x="PAD" :y="ln.y - 4" :width="plotW" height="8" class="band" />
            <line :x1="PAD" :y1="ln.y" :x2="PAD + plotW" :y2="ln.y" />
            <text :x="PAD + plotW + 4" :y="ln.y + 4">{{ ln.label }}</text>
        </g>
        <g v-for="(k, i) in chart.candles" :key="i" :class="k.up ? 'up' : 'down'">
            <line :x1="k.x" :y1="k.yh" :x2="k.x" :y2="k.yl" class="wick" />
            <rect :x="k.x - k.w / 2" :y="Math.min(k.yo, k.yc)" :width="k.w" :height="Math.max(1, Math.abs(k.yo - k.yc))" />
        </g>
        <g v-for="(m, i) in chart.lines" :key="`m${i}`" :class="`ma ma${i}`">
            <polyline :points="m.points" />
            <text :x="PAD + plotW + 4" :y="m.endY + 4">{{ m.label }}</text>
        </g>
        <g v-if="chart.mark" class="mark">
            <circle :cx="chart.mark.x" :cy="chart.mark.y" r="7" />
            <text :x="chart.mark.x" :y="chart.mark.y + 22" text-anchor="middle">{{ chart.mark.label }}</text>
        </g>
        <g v-if="chart.vol">
            <line :x1="PAD" :y1="chart.vol.base" :x2="PAD + plotW" :y2="chart.vol.base" class="axis" />
            <rect v-for="(b, i) in chart.vol.bars" :key="`v${i}`" :class="b.up ? 'up' : 'down'" class="vbar"
                :x="b.x - b.w / 2" :y="b.y" :width="b.w" :height="chart.vol.base - b.y" />
            <g v-if="chart.vol.avg" class="avg">
                <line :x1="PAD" :y1="chart.vol.avg.y" :x2="PAD + plotW" :y2="chart.vol.avg.y" />
                <text :x="PAD + plotW + 4" :y="chart.vol.avg.y + 4">20일 평균</text>
            </g>
            <text v-if="chart.vol.note" class="vnote" :x="chart.vol.note.x" :y="chart.vol.note.y" text-anchor="end">{{ chart.vol.note.text }}</text>
            <text :x="PAD" :y="chart.vol.top - 4" class="axis-t">거래량</text>
        </g>
    </svg>
</template>

<script setup>
/**
 * 트레이닝 본문 그림. name: candle | bull-bear | volume | ma | sr.
 * 예시 차트 세 개(volume·ma·sr)는 고정 시드의 가상 시세라 매번 같은 모양으로 그려진다(실제 종목 아님).
 * 그림을 늘리려면 여기에 name 하나와 시세 모양(SERIES)을 더하고 trainingLessons.json 에서 {figure: name} 으로 쓴다.
 */
const props = defineProps({ name: { type: String, required: true } });

const W = 340;
const PAD = 6;
const RIGHT = 62;            // 오른쪽 이름표 자리
const plotW = W - PAD - RIGHT;

// 고정 시드 난수(mulberry32) — 그림이 매번 같게 나오도록.
const rng = (seed) => () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/** 종가 흐름으로 시가·고가·저가를 만든다. opens 에 지정한 날은 그 시가를 쓴다. */
const toCandles = (closes, seed, opens = {}) => {
    const r = rng(seed);
    return closes.map((c, i) => {
        const prev = i ? closes[i - 1] : c * 0.996;
        const o = opens[i] ?? prev * (1 + (r() - 0.5) * 0.008);
        return { o, c, h: Math.max(o, c) * (1 + r() * 0.011), l: Math.min(o, c) * (1 - r() * 0.011) };
    });
};

const SERIES = {
    // 조용히 옆으로 가다가 하루 거래가 크게 붙으며 오른 뒤 이어서 오른다.
    volume: () => {
        const r = rng(7);
        const n = 28, jump = 20;
        const closes = [], vols = [];
        for (let i = 0; i < n; i++) {
            if (i < jump) closes.push(100 + Math.sin(i * 1.3) * 0.8 + (r() - 0.5) * 1.2);
            else if (i === jump) closes.push(108.5);
            else closes.push(108.5 + (i - jump) * 0.8 + (r() - 0.5) * 2);
            vols.push(i < jump ? 90 + r() * 50 : i === jump ? 560 : 190 + r() * 90);
        }
        return { candles: toCandles(closes, 11, { [jump]: closes[jump - 1] * 1.003 }), vols, jump };
    },
    // 내리다가 바닥을 찍고 오른다(5일선이 20일선을 아래에서 위로 뚫음).
    ma: () => {
        const r = rng(3);
        const closes = [];
        for (let i = 0; i < 50; i++) {
            const base = i < 24 ? 122 - i * 1.1 : 95.6 + (i - 24) * 1.2;
            closes.push(base + Math.sin(i * 0.9) * 1.5 + (r() - 0.5) * 1.6);
        }
        return { candles: toCandles(closes, 5) };
    },
    // 100~112 사이를 오가다(지지·저항) 저항선 가까이 올라온 뒤 거래량과 함께 112 를 넘어선다.
    sr: () => {
        const r = rng(9);
        const n = 50, brk = 44;
        const closes = [], vols = [];
        for (let i = 0; i < n; i++) {
            if (i < brk) closes.push(106 + 5.4 * Math.sin((i - 2) * (2 * Math.PI / 13)) + (r() - 0.5) * 1.2);
            else closes.push(114.5 + (i - brk) * 1.0 + (r() - 0.5) * 1.6);
            vols.push(i === brk ? 470 : i > brk ? 200 + r() * 70 : 90 + r() * 50);
        }
        return { candles: toCandles(closes, 13, { [brk]: closes[brk - 1] * 1.002 }), vols, levels: [100, 112] };
    },
};

const avg = (arr) => arr.reduce((a, b) => a + b, 0) / arr.length;
const movingAvg = (closes, p) => closes.map((_, i) => (i + 1 < p ? null : avg(closes.slice(i + 1 - p, i + 1))));

const chart = computed(() => {
    const make = SERIES[props.name];
    if (!make) return null;
    const s = make();
    const hasVol = !!s.vols;
    const priceTop = 10, priceH = hasVol ? 120 : 150;
    const volTop = priceTop + priceH + 26, volH = 50;
    const height = hasVol ? volTop + volH + 4 : priceTop + priceH + 30;

    const n = s.candles.length;
    const slot = plotW / n;
    const xOf = (i) => PAD + slot * (i + 0.5);
    const lo = Math.min(...s.candles.map(k => k.l), ...(s.levels ?? []));
    const hi = Math.max(...s.candles.map(k => k.h), ...(s.levels ?? []));
    const span = (hi - lo) || 1;
    const yOf = (p) => priceTop + (hi - p) / span * priceH;
    const w = Math.max(2, slot * 0.62);

    const candles = s.candles.map((k, i) => ({
        x: xOf(i), w, up: k.c >= k.o, yo: yOf(k.o), yc: yOf(k.c), yh: yOf(k.h), yl: yOf(k.l),
    }));

    const out = { height, candles, hlines: [], lines: [], mark: null, vol: null, label: '' };

    if (props.name === 'ma') {
        const closes = s.candles.map(k => k.c);
        const ma5 = movingAvg(closes, 5), ma20 = movingAvg(closes, 20);
        const line = (m, label) => {
            const pts = m.map((v, i) => (v == null ? null : `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`)).filter(Boolean);
            return { points: pts.join(' '), label, endY: yOf(m.at(-1)) };
        };
        out.lines = [line(ma5, '5일선'), line(ma20, '20일선')];
        // 바닥 뒤 처음으로 5일선이 20일선을 아래에서 위로 넘는 날
        const ci = closes.findIndex((_, i) => i > 24 && ma20[i - 1] != null
            && ma5[i - 1] <= ma20[i - 1] && ma5[i] > ma20[i]);
        if (ci > 0) out.mark = { x: xOf(ci), y: yOf(ma20[ci]), label: '골든크로스' };
        // 두 선의 이름표가 겹치지 않게 벌린다
        const [a, b] = out.lines;
        if (Math.abs(a.endY - b.endY) < 12) { const mid = (a.endY + b.endY) / 2; a.endY = mid - 6; b.endY = mid + 6; }
        out.label = '내리던 가격이 돌아서며 5일 이동평균선이 20일 이동평균선을 아래에서 위로 뚫는 예시 차트';
    }
    if (props.name === 'sr') {
        out.hlines = [{ y: yOf(s.levels[1]), label: '저항선' }, { y: yOf(s.levels[0]), label: '지지선' }];
        out.label = '같은 가격대에서 여러 번 멈췄다가 저항선을 거래량과 함께 넘어서는 예시 차트';
    }
    if (hasVol) {
        const vmax = Math.max(...s.vols);
        const base = volTop + volH;
        const vy = (v) => base - v / vmax * volH;
        out.vol = {
            top: volTop, base,
            bars: s.vols.map((v, i) => ({ x: xOf(i), w, up: candles[i].up, y: vy(v) })),
            avg: null, note: null,
        };
        const spike = s.jump ?? null;
        if (spike != null) {
            const a20 = avg(s.vols.slice(spike - 20, spike));
            out.vol.avg = { y: vy(a20) };
            out.vol.note = { x: xOf(spike) - w, y: vy(s.vols[spike]) + 10, text: `평소의 ${(s.vols[spike] / a20).toFixed(1)}배` };
            out.label = `조용하던 종목에 최근 20일 평균의 ${(s.vols[spike] / a20).toFixed(1)}배 거래가 붙으며 크게 오른 예시 차트`;
        }
    }
    return out;
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.tf { display: block; width: 100%; height: auto; max-width: 420px; margin: 0 auto; overflow: visible; }

.up rect, .up.vbar, rect.up { fill: $up; }
.down rect, .down.vbar, rect.down { fill: $down; }
.up .wick { stroke: $up; }
.down .wick { stroke: $down; }
.wick { stroke-width: 1.4; }
.doji rect { fill: $ink; }
.doji .wick { stroke: $ink; }
.vbar { opacity: .55; }

text { font-family: $font-body; font-size: 11px; fill: $sub; }
.lbl text { font-size: 12px; fill: $ink; }
.lbl.small text { font-size: 11px; fill: $sub-2; }
.lead { stroke: $sub-2; stroke-width: 1; }
.cap { font-size: 13px; font-weight: 700; fill: $ink; }
.up-t { fill: $up; }
.down-t { fill: $down; }

.ma polyline { fill: none; stroke-width: 1.8; stroke-linejoin: round; }
.ma0 polyline { stroke: #D9822B; }
.ma0 text { fill: #B5651D; font-weight: 700; }
.ma1 polyline { stroke: #6A4C93; }
.ma1 text { fill: #6A4C93; font-weight: 700; }
.mark circle { fill: none; stroke: $brown-ink; stroke-width: 1.6; }
.mark text { font-size: 11px; font-weight: 700; fill: $brown-ink; }
// 캔들 위에 겹치는 글자는 흰 테두리로 띄운다
.mark text, .vnote, .hline text, .ma text { paint-order: stroke; stroke: #fff; stroke-width: 3px; stroke-linejoin: round; }

.hline line { stroke: $brown; stroke-width: 1.2; stroke-dasharray: 5 3; }
.hline .band { fill: $yellow; opacity: .18; }
.hline text { font-size: 11px; font-weight: 700; fill: $brown-ink; }

.axis { stroke: $line-2; stroke-width: 1; }
.axis-t { font-size: 10px; fill: $sub-2; }
.avg line { stroke: $sub; stroke-width: 1; stroke-dasharray: 3 3; }
.avg text { font-size: 10px; fill: $sub; }
.vnote { font-size: 11px; font-weight: 700; fill: $brown-ink; }
</style>
