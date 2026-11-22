<template>
    <!-- 홈 '이번 주의 차트'(2026-11-22 회의 결정 3번): 전 주에 양봉상회가 고른 종목 1개의 차트 + 선정 시점 마커 + 신호 설명.
         수익률 같은 성과 숫자는 여기 없다. 선정 이후의 봉은 그대로 보여 준다(오르지 않은 경우도 같은 방식). -->
    <section v-if="data" class="sec weekly" aria-labelledby="weekly-title">
        <div class="sec-head">
            <h2 id="weekly-title">이번 주의 차트</h2>
            <span class="meta">{{ pickDateText }} 선정</span>
        </div>
        <p class="sec-sub">다른 사용자는 {{ data.stock_name }} 종목을 이럴 때 골랐어요.</p>

        <div class="w-card">
            <p class="w-name"><b>{{ data.stock_name }}</b><span>{{ data.stock_code }}</span></p>
            <svg class="w-chart" :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="ariaLabel">
                <g v-for="(b, i) in shapes" :key="i">
                    <line :x1="b.cx" :x2="b.cx" :y1="b.yHigh" :y2="b.yLow" :stroke="b.color" stroke-width="1.2" stroke-linecap="round" />
                    <rect :x="b.cx - BW / 2" :y="b.bodyTop" :width="BW" :height="b.bodyH" rx="1" :fill="b.color" />
                </g>
                <g v-if="marker">
                    <line :x1="marker.x" :x2="marker.x" y1="14" :y2="H" class="mk-line" />
                    <g :transform="`translate(${marker.labelX} 0)`">
                        <rect width="58" height="18" rx="9" class="mk-tag" />
                        <text x="29" y="13" text-anchor="middle" class="mk-text">선정 시점</text>
                    </g>
                </g>
            </svg>
            <p class="w-price">선정일 종가 <b>{{ priceText }}</b>원</p>
        </div>

        <ul class="w-lines">
            <li v-for="ln in data.lines" :key="ln">
                <span class="why-ic" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg></span>
                <span>{{ ln }}</span>
            </li>
        </ul>

        <button type="button" class="w-train" @click="router.push('/training')">이런 신호, 차트 보는 법 배우기</button>
        <p class="w-note">이 종목이 이후에 올랐는지와 관계없이, 그날 신호가 가장 선명했던 종목이에요. 수익을 보장하는 것이 아니에요.</p>
    </section>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { numOrNull, formatNumber } from '@scripts/stockSignals.js';

const router = useRouter();
const data = ref(null);

const load = async () => {
    try {
        const { data: res } = await aibeesApi.get('/api/v1/stocks/weekly-chart');
        const d = res?.data;
        data.value = d && Array.isArray(d.bars) && d.bars.length && Array.isArray(d.lines) && d.lines.length ? d : null;
    } catch (e) {
        data.value = null;   // 보조 블록 — 못 받으면 조용히 숨긴다
    }
};
onMounted(load);

const W = 320, H = 150, PAD = 6, TOP = 22;
const BW = 4;

const bars = computed(() => (data.value?.bars ?? [])
    .map(b => ({ date: b.date, o: numOrNull(b.open), h: numOrNull(b.high), l: numOrNull(b.low), c: numOrNull(b.close) }))
    .filter(b => b.o !== null && b.h !== null && b.l !== null && b.c !== null));

const step = computed(() => (bars.value.length > 1 ? (W - PAD * 2) / (bars.value.length - 1) : 0));
const shapes = computed(() => {
    const list = bars.value;
    if (!list.length) return [];
    const hi = Math.max(...list.map(b => b.h));
    const lo = Math.min(...list.map(b => b.l));
    const span = hi - lo;
    const y = (v) => (span ? TOP + ((hi - v) / span) * (H - TOP - PAD) : H / 2);
    return list.map((b, i) => {
        const top = Math.min(y(b.o), y(b.c));
        return {
            cx: PAD + i * step.value,
            yHigh: y(b.h), yLow: y(b.l), bodyTop: top,
            bodyH: Math.max(1.2, Math.abs(y(b.o) - y(b.c))),
            color: b.c === b.o ? '#8A7A68' : b.c > b.o ? '#E42939' : '#3182F6',
        };
    });
});
const markerIdx = computed(() => bars.value.findIndex(b => b.date === data.value?.marker_date));
const marker = computed(() => {
    const i = markerIdx.value;
    if (i < 0) return null;
    const x = PAD + i * step.value;
    return { x, labelX: Math.min(W - 58 - 2, Math.max(2, x - 29)) };
});

const pickDateText = computed(() => {
    const s = String(data.value?.ymd ?? '');
    return s.length === 8 ? `${Number(s.slice(4, 6))}/${Number(s.slice(6, 8))}` : '';
});
const priceText = computed(() => formatNumber(data.value?.close));
const ariaLabel = computed(() => `${data.value?.stock_name} 일봉 차트, ${pickDateText.value}에 선정`);
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.sec { background: $card; padding: $sec-pt $pad-x $sec-pb; }   // 2026-11-22 홈 간격 통일
.sec-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
    .meta { font-size: 13px; color: $sub; white-space: nowrap; }
}
.sec-sub { margin: 4px 0 0; font-size: 13px; color: $sub; }

.w-card {
    margin-top: $head-gap;
    padding: $card-pad;
    border-radius: $radius;
    background: $bg;
}
.w-name {
    margin: 0 0 6px;
    display: flex;
    align-items: baseline;
    gap: 8px;
    b { font-size: 16px; font-weight: 700; }
    span { font-size: 12px; color: $sub-2; }
}
.w-chart { display: block; width: 100%; height: auto; }
.mk-line { stroke: $amber-700; stroke-width: 1; stroke-dasharray: 3 3; }
.mk-tag { fill: $honey-300; }
.mk-text { fill: $honey-ink; font-size: 10px; font-weight: 700; }
.w-price { margin: 6px 0 0; font-size: 12px; color: $sub; b { color: $ink; } }

.w-lines {
    margin: 16px 0 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
    li {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 10px 12px;
        border-radius: 8px;
        background: $honey-strip;
        font-size: 14px;
        line-height: 1.45;
    }
}
.why-ic {
    flex: none;
    width: 18px;
    height: 18px;
    margin-top: 1px;
    border-radius: 9px;
    background: $honey-dot;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    svg { width: 12px; height: 12px; fill: none; stroke: $honey-ink; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }
}

.w-train {
    width: 100%;
    min-height: 48px;
    margin-top: 16px;
    border: 0;
    border-radius: $radius;
    background: $honey-300;
    color: $honey-ink;
    font: inherit;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
}
.w-note { margin: 12px 0 0; font-size: 12px; line-height: 1.5; color: $sub-2; }
</style>
