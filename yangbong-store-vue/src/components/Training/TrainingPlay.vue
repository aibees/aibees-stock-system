<template>
    <div class="tp">
        <!-- 캔들 조립: 네 가격을 움직여 캔들이 만들어지는 모습을 본다 -->
        <svg v-if="name === 'candle-build'" class="tp-chart" viewBox="0 0 340 200" role="img"
            :aria-label="`시가 ${cd.o}, 종가 ${cd.c}, 고가 ${cd.h}, 저가 ${cd.l}으로 만든 ${cd.kind}`">
            <g v-for="row in cd.rows" :key="row.name" class="cb-line">
                <line :x1="6" :y1="row.y" :x2="224" :y2="row.y" />
                <text :x="232" :y="row.y + 4">{{ row.name }} {{ row.price }}</text>
            </g>
            <g :class="cd.kind === '음봉' ? 'down' : cd.kind === '양봉' ? 'up' : 'doji'">
                <line :x1="115" :y1="cd.yh" :x2="115" :y2="cd.yl" class="wick" />
                <rect :x="97" :y="Math.min(cd.yo, cd.yc)" width="36" :height="Math.max(2, Math.abs(cd.yo - cd.yc))" rx="2" />
            </g>
        </svg>

        <!-- 이동평균선·볼린저밴드·거래량·MACD: 가상 시세 위에 지표를 그린다 -->
        <svg v-else-if="v" class="tp-chart" :viewBox="`0 0 ${W} ${v.height}`" role="img" :aria-label="v.label">
            <polygon v-if="v.band" :points="v.band" class="band" />
            <g v-if="v.bandLines">
                <polyline :points="v.bandLines.up" class="bb-edge" />
                <polyline :points="v.bandLines.low" class="bb-edge" />
            </g>
            <g v-for="(k, i) in v.candles" :key="i" :class="k.up ? 'up' : 'down'">
                <line :x1="k.x" :y1="k.yh" :x2="k.x" :y2="k.yl" class="wick" />
                <rect :x="k.x - v.w / 2" :y="Math.min(k.yo, k.yc)" :width="v.w" :height="Math.max(1, Math.abs(k.yo - k.yc))" />
            </g>
            <g v-for="(ln, i) in v.lines" :key="`l${i}`" :class="`ln ln${i}`">
                <polyline :points="ln.pts" />
                <text :x="PAD + plotW + 4" :y="ln.endY + 4">{{ ln.label }}</text>
            </g>
            <g v-for="(m, i) in v.marks" :key="`m${i}`" :class="m.golden ? 'mk gold' : 'mk dead'">
                <circle :cx="m.x" :cy="m.y" r="4.5" />
            </g>
            <g v-if="v.vol">
                <line :x1="PAD" :y1="v.vol.base" :x2="PAD + plotW" :y2="v.vol.base" class="axis" />
                <rect v-for="(b, i) in v.vol.bars" :key="`v${i}`" class="vbar" :class="[b.up ? 'up' : 'down', { last: b.last }]"
                    :x="b.x - v.w / 2" :y="b.y" :width="v.w" :height="Math.max(0, v.vol.base - b.y)" />
                <line :x1="PAD" :y1="v.vol.avgY" :x2="PAD + plotW" :y2="v.vol.avgY" class="avg" />
                <text :x="PAD + plotW + 4" :y="v.vol.avgY + 4" class="avg-t">20일 평균</text>
                <text :x="PAD" :y="v.vol.top - 4" class="axis-t">거래량</text>
            </g>
            <g v-if="v.lower">
                <line :x1="PAD" :y1="v.lower.zeroY" :x2="PAD + plotW" :y2="v.lower.zeroY" class="axis" />
                <rect v-for="(b, i) in v.lower.hist" :key="`h${i}`" class="hbar" :class="b.pos ? 'up' : 'down'"
                    :x="b.x - v.w / 2" :y="b.y" :width="v.w" :height="b.h" />
                <polyline :points="v.lower.macd" class="ln ln0 raw" />
                <polyline :points="v.lower.signal" class="ln ln1 raw" />
                <text :x="PAD + plotW + 4" :y="v.lower.macdEnd + 4" class="lt0">MACD</text>
                <text :x="PAD + plotW + 4" :y="v.lower.signalEnd + 4" class="lt1">시그널</text>
                <text :x="PAD" :y="v.lower.top - 4" class="axis-t">MACD</text>
            </g>
        </svg>

        <div class="tp-controls">
            <div v-for="c in controls" :key="c.key" class="tp-row">
                <label :for="`tp-${name}-${c.key}`">{{ c.label }}</label>
                <input :id="`tp-${name}-${c.key}`" v-model.number="s[c.key]" type="range" :min="c.min" :max="c.max" :step="c.step" />
                <output>{{ c.fmt(eff[c.key] ?? s[c.key]) }}</output>
            </div>
        </div>
        <p class="tp-read" aria-live="polite">{{ readout }}</p>
        <p class="tp-fine">슬라이더를 움직여 보세요. 차트는 설명을 위해 만든 가상 시세입니다.</p>
    </div>
</template>

<script setup>
/**
 * 트레이닝 인터랙티브 블록. lesson 본문에서 { "play": name } 으로 쓴다.
 * name: candle-build | ma | bb | volume | macd. 시세는 고정 시드의 가상 시세라 실제 종목이 아니다.
 */
const props = defineProps({ name: { type: String, required: true } });

const W = 340;
const PAD = 6;
const RIGHT = 56;
const plotW = W - PAD - RIGHT;

const rng = (seed) => () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

/* ── 가상 시세: 올랐다 내렸다 하는 70일 ── */
const N = 70;
const SERIES = (() => {
    const r = rng(21);
    const closes = [];
    for (let i = 0; i < N; i++) closes.push(100 + 11 * Math.sin(i / 8.5) + i * 0.12 + (r() - 0.5) * 3.2);
    const candles = closes.map((c, i) => {
        const o = (i ? closes[i - 1] : c) * (1 + (r() - 0.5) * 0.008);
        return { o, c, h: Math.max(o, c) * (1 + r() * 0.01), l: Math.min(o, c) * (1 - r() * 0.01) };
    });
    const vols = closes.map((c, i) => 100 * (0.7 + r() * 0.6) * (1 + Math.min(1.2, Math.abs(c - (closes[i - 1] ?? c)) * 0.25)));
    return { closes, candles, vols };
})();

const sma = (arr, p) => arr.map((_, i) => (i + 1 < p ? null : arr.slice(i + 1 - p, i + 1).reduce((a, b) => a + b, 0) / p));
const ema = (arr, p) => {
    const a = 2 / (p + 1);
    const out = [];
    arr.forEach((x, i) => out.push(i ? a * x + (1 - a) * out[i - 1] : x));
    return out;
};
const stdev = (arr, p) => arr.map((_, i) => {
    if (i + 1 < p) return null;
    const w = arr.slice(i + 1 - p, i + 1);
    const m = w.reduce((a, b) => a + b, 0) / p;
    return Math.sqrt(w.reduce((a, b) => a + (b - m) ** 2, 0) / p);
});

/* ── 조절값 ── */
const s = reactive({ o: 96, c: 108, h: 112, l: 92, short: 5, long: 20, period: 20, k: 2, mult: 3, fast: 12, slow: 26 });
const days = (n) => `${n}일`;
const CONTROLS = {
    'candle-build': [
        { key: 'o', label: '시가', min: 80, max: 120, step: 1, fmt: (n) => n },
        { key: 'c', label: '종가', min: 80, max: 120, step: 1, fmt: (n) => n },
        { key: 'h', label: '고가', min: 80, max: 120, step: 1, fmt: (n) => n },
        { key: 'l', label: '저가', min: 80, max: 120, step: 1, fmt: (n) => n },
    ],
    ma: [
        { key: 'short', label: '짧은 선', min: 2, max: 20, step: 1, fmt: days },
        { key: 'long', label: '긴 선', min: 10, max: 60, step: 1, fmt: days },
    ],
    bb: [
        { key: 'period', label: '기간', min: 10, max: 40, step: 5, fmt: days },
        { key: 'k', label: '띠 폭', min: 1, max: 3, step: 0.5, fmt: (n) => `표준편차 ${n}배` },
    ],
    volume: [
        { key: 'mult', label: '오늘 거래량', min: 0.5, max: 6, step: 0.1, fmt: (n) => `평균의 ${Number(n).toFixed(1)}배` },
    ],
    macd: [
        { key: 'fast', label: '짧은 기간', min: 5, max: 20, step: 1, fmt: days },
        { key: 'slow', label: '긴 기간', min: 15, max: 40, step: 1, fmt: days },
    ],
};
const controls = computed(() => CONTROLS[props.name] ?? []);

// 서로 어긋나면 안 되는 값은 보정해서 쓴다(고가 ≥ 시가·종가, 짧은 선 < 긴 선).
const eff = computed(() => ({
    h: Math.max(s.h, s.o, s.c),
    l: Math.min(s.l, s.o, s.c),
    long: Math.max(s.long, s.short + 1),
    slow: Math.max(s.slow, s.fast + 1),
}));
watch(() => [s.o, s.c, s.h, s.l], () => { s.h = eff.value.h; s.l = eff.value.l; });
watch(() => [s.short, s.long], () => { s.long = eff.value.long; });
watch(() => [s.fast, s.slow], () => { s.slow = eff.value.slow; });

/* ── 캔들 조립 ── */
const cd = computed(() => {
    const { o, c } = s;
    const h = eff.value.h, l = eff.value.l;
    const y = (p) => 14 + (120 - p) / 40 * 160;
    const kind = Math.abs(c - o) <= 1 ? '도지' : c > o ? '양봉' : '음봉';
    return {
        o, c, h, l, kind,
        yo: y(o), yc: y(c), yh: y(h), yl: y(l),
        rows: [['고가', h], ['종가', c], ['시가', o], ['저가', l]].map(([name, price]) => ({ name, price, y: y(price) })),
    };
});

/* ── 지표 차트 ── */
const v = computed(() => {
    if (props.name === 'candle-build') return null;
    const { candles: cs, closes, vols } = SERIES;
    const hasVol = props.name === 'volume';
    const hasLower = props.name === 'macd';
    const priceTop = 8;
    const priceH = hasLower ? 110 : hasVol ? 120 : 160;
    const lowerTop = priceTop + priceH + 18;
    const subH = hasVol ? 50 : 60;
    const height = hasVol || hasLower ? lowerTop + subH + 6 : priceTop + priceH + 8;

    const slot = plotW / N;
    const xOf = (i) => PAD + slot * (i + 0.5);
    const w = Math.max(2, slot * 0.62);

    // 지표 계산
    let lines = [], band = null, bandLines = null, marks = [], lower = null, vol = null, readout = '', label = '';
    let extra = [];
    const crossings = (a, b) => {
        let g = 0, d = 0;
        const list = [];
        for (let i = 1; i < N; i++) {
            if (a[i] == null || b[i] == null || a[i - 1] == null || b[i - 1] == null) continue;
            if (a[i - 1] <= b[i - 1] && a[i] > b[i]) { g++; list.push({ i, golden: true }); }
            else if (a[i - 1] >= b[i - 1] && a[i] < b[i]) { d++; list.push({ i, golden: false }); }
        }
        return { g, d, list };
    };
    let cross = null, shortMa, longMa, mid, up, low, macdLine, sig;

    if (props.name === 'ma') {
        shortMa = sma(closes, s.short);
        longMa = sma(closes, eff.value.long);
        cross = crossings(shortMa, longMa);
        extra = [...shortMa, ...longMa].filter(x => x != null);
    } else if (props.name === 'bb') {
        const p = s.period;
        mid = sma(closes, p);
        const sd = stdev(closes, p);
        up = mid.map((m, i) => (m == null ? null : m + s.k * sd[i]));
        low = mid.map((m, i) => (m == null ? null : m - s.k * sd[i]));
        extra = [...up, ...low].filter(x => x != null);
    } else if (props.name === 'macd') {
        const ef = ema(closes, s.fast), es = ema(closes, eff.value.slow);
        macdLine = ef.map((x, i) => x - es[i]);
        sig = ema(macdLine, 9);
        cross = crossings(macdLine, sig);
    }

    const lo = Math.min(...cs.map(k => k.l), ...extra);
    const hi = Math.max(...cs.map(k => k.h), ...extra);
    const span = (hi - lo) || 1;
    const yOf = (p) => priceTop + (hi - p) / span * priceH;
    const pts = (arr) => arr.map((q, i) => (q == null ? null : `${xOf(i).toFixed(1)},${yOf(q).toFixed(1)}`)).filter(Boolean).join(' ');
    const lastIdx = (arr) => arr.reduce((acc, q, i) => (q == null ? acc : i), 0);

    const candles = cs.map((k, i) => ({ x: xOf(i), up: k.c >= k.o, yo: yOf(k.o), yc: yOf(k.c), yh: yOf(k.h), yl: yOf(k.l) }));

    if (props.name === 'ma') {
        const ends = [yOf(shortMa.at(-1)), yOf(longMa.at(-1))];
        if (Math.abs(ends[0] - ends[1]) < 12) { const m = (ends[0] + ends[1]) / 2; ends[0] = m - 6; ends[1] = m + 6; }
        lines = [
            { pts: pts(shortMa), label: `${s.short}일선`, endY: ends[0] },
            { pts: pts(longMa), label: `${eff.value.long}일선`, endY: ends[1] },
        ];
        marks = cross.list.map(m => ({ x: xOf(m.i), y: yOf(longMa[m.i]), golden: m.golden }));
        readout = `${s.short}일선이 ${eff.value.long}일선을 위로 뚫은 횟수(골든크로스) ${cross.g}번, 아래로 뚫은 횟수(데드크로스) ${cross.d}번. 짧은 선일수록 가격을 빨리 따라가 신호가 잦고, 긴 선일수록 느리지만 신호가 적습니다.`;
        label = `${s.short}일 이동평균선과 ${eff.value.long}일 이동평균선이 만나는 예시 차트`;
    }
    if (props.name === 'bb') {
        const idx = mid.map((m, i) => (m == null ? null : i)).filter(i => i != null);
        const top = idx.map(i => `${xOf(i).toFixed(1)},${yOf(up[i]).toFixed(1)}`);
        const bot = idx.slice().reverse().map(i => `${xOf(i).toFixed(1)},${yOf(low[i]).toFixed(1)}`);
        band = [...top, ...bot].join(' ');
        bandLines = { up: pts(up), low: pts(low) };
        lines = [{ pts: pts(mid), label: '중심선', endY: yOf(mid.at(-1)) }];
        const inside = idx.filter(i => closes[i] <= up[i] && closes[i] >= low[i]).length;
        const widthPct = (up.at(-1) - low.at(-1)) / mid.at(-1) * 100;
        readout = `표준편차 ${s.k}배로 그리면 종가가 띠 안에 있던 날이 ${Math.round(inside / idx.length * 100)}%입니다. 마지막 날 띠의 폭은 중심선의 ${widthPct.toFixed(0)}%예요. 띠를 넓힐수록 더 많은 날이 안에 들어옵니다.`;
        label = `${s.period}일 볼린저밴드(표준편차 ${s.k}배) 예시 차트`;
    }
    if (hasVol) {
        const last = N - 1;
        const prev20 = vols.slice(last - 20, last);
        const avg = prev20.reduce((a, b) => a + b, 0) / 20;
        const todayVol = avg * s.mult;
        const all = [...vols.slice(0, last), todayVol];
        const vmax = Math.max(...all, avg * 6.2);
        const base = lowerTop + subH;
        const vy = (q) => base - q / vmax * subH;
        vol = {
            top: lowerTop, base, avgY: vy(avg),
            bars: all.map((q, i) => ({ x: xOf(i), y: vy(q), up: candles[i].up, last: i === last })),
        };
        const m = s.mult;
        const word = m >= 2 ? '평소보다 크게 늘었습니다' : m >= 1.3 ? '평소보다 조금 많습니다' : m >= 0.7 ? '평소 수준입니다' : '평소보다 적습니다';
        readout = `오늘 거래량은 최근 20일 평균의 ${m.toFixed(1)}배로, ${word}. 가격이 크게 움직인 날 이 숫자가 클수록 움직임에 무게가 실립니다.`;
        label = `오늘 거래량이 최근 20일 평균의 ${m.toFixed(1)}배인 예시 차트`;
    }
    if (hasLower) {
        const hist = macdLine.map((x, i) => x - sig[i]);
        const maxAbs = Math.max(...macdLine.map(Math.abs), ...sig.map(Math.abs), ...hist.map(Math.abs), 0.01);
        const zeroY = lowerTop + subH / 2;
        const ly = (q) => zeroY - q / maxAbs * (subH / 2);
        const lp = (arr) => arr.map((q, i) => `${xOf(i).toFixed(1)},${ly(q).toFixed(1)}`).join(' ');
        lower = {
            top: lowerTop, zeroY,
            hist: hist.map((q, i) => ({ x: xOf(i), pos: q >= 0, y: Math.min(ly(q), zeroY), h: Math.abs(ly(q) - zeroY) })),
            macd: lp(macdLine), signal: lp(sig),
            macdEnd: ly(macdLine.at(-1)), signalEnd: ly(sig.at(-1)),
        };
        if (Math.abs(lower.macdEnd - lower.signalEnd) < 12) { const m = (lower.macdEnd + lower.signalEnd) / 2; lower.macdEnd = m - 6; lower.signalEnd = m + 6; }
        marks = cross.list.map(m => ({ x: xOf(m.i), y: ly(macdLine[m.i]), golden: m.golden }));
        readout = `MACD선이 시그널선을 위로 뚫은 신호 ${cross.g}번, 아래로 뚫은 신호 ${cross.d}번. 기간을 줄이면 신호가 빨라지지만 잦은 거짓 신호도 늘어납니다.`;
        label = `${s.fast}일과 ${eff.value.slow}일 기준 MACD 예시 차트`;
    }
    return { height, candles, w, lines, band, bandLines, marks, vol, lower, readout, label };
});

const readout = computed(() => {
    if (props.name === 'candle-build') {
        const c = cd.value;
        const body = Math.abs(c.c - c.o), up = c.h - Math.max(c.o, c.c), dn = Math.min(c.o, c.c) - c.l;
        const kindText = c.kind === '양봉' ? '종가가 시가보다 높아 양봉입니다.' : c.kind === '음봉' ? '종가가 시가보다 낮아 음봉입니다.' : '시가와 종가가 거의 같아 도지입니다.';
        return `${kindText} 몸통 ${body}, 위꼬리 ${up}, 아래꼬리 ${dn}. 몸통은 시가와 종가 사이, 꼬리는 고가·저가까지입니다.`;
    }
    return v.value?.readout ?? '';
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.tp { margin: 8px 0 18px; padding: 14px 0 10px; border-top: 1px solid $line-soft; border-bottom: 1px solid $line-soft; }
.tp-chart { display: block; width: 100%; height: auto; max-width: 420px; margin: 0 auto; overflow: visible; }

.up rect, rect.up { fill: $up; }
.down rect, rect.down { fill: $down; }
.up .wick { stroke: $up; }
.down .wick { stroke: $down; }
.doji rect { fill: $ink; }
.doji .wick { stroke: $ink; }
.wick { stroke-width: 1.2; }
.vbar { opacity: .5; &.last { opacity: 1; } }
.hbar { opacity: .5; }

text { font-family: $font-body; font-size: 11px; fill: $sub; }
.cb-line line { stroke: $sub-2; stroke-width: 1; stroke-dasharray: 4 3; }
.cb-line text { fill: $ink; font-size: 12px; font-variant-numeric: tabular-nums; }

.ln polyline { fill: none; stroke-width: 1.8; stroke-linejoin: round; }
.ln.raw { fill: none; stroke-width: 1.5; }
.ln0 polyline, polyline.ln0 { stroke: #D9822B; }
.ln1 polyline, polyline.ln1 { stroke: #6A4C93; }
.ln0 text, .lt0 { fill: #B5651D; font-weight: 700; }
.ln1 text, .lt1 { fill: #6A4C93; font-weight: 700; }
.ln text { paint-order: stroke; stroke: #fff; stroke-width: 3px; }

.band { fill: $honey-300; opacity: .35; }
.bb-edge { fill: none; stroke: #D9822B; stroke-width: 1.2; }

.mk circle { stroke: #fff; stroke-width: 1.4; }
.mk.gold circle { fill: $up; }
.mk.dead circle { fill: $down; }

.axis { stroke: $sub-2; stroke-width: 1; }
.axis-t { font-size: 10px; fill: $sub-2; }
.avg { stroke: $sub; stroke-width: 1; stroke-dasharray: 3 3; }
.avg-t { font-size: 10px; fill: $sub; }

.tp-controls { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.tp-row {
    display: grid; grid-template-columns: 4.5em 1fr 8.5em; align-items: center; gap: 10px;
    label { font-size: .88rem; font-weight: 700; color: $brown-ink; }
    output { font-size: .85rem; color: $sub-ink; text-align: right; font-variant-numeric: tabular-nums; }
    input[type='range'] { width: 100%; min-height: 32px; accent-color: $amber-700; }
}
.tp-read { margin: 10px 0 0; padding: 10px 12px; border-radius: 10px; background: $honey-50; font-size: .9rem; line-height: 1.65; color: $ink; word-break: keep-all; }
.tp-fine { margin: 8px 0 0; font-size: .74rem; color: $sub-2; }
</style>
