<template>
    <!-- 목록 줄 안에 들어가는 최근 N개 봉(라벨·축 없이 꼬리+몸통만). 맨 오른쪽이 가장 최근 봉 -->
    <svg class="mini-candles" :viewBox="`0 0 ${width} ${H}`" :style="{ width: `${width}px` }" role="img"
        :aria-label="ariaLabel">
        <g v-for="(b, i) in shapes" :key="i">
            <line :x1="b.cx" :x2="b.cx" :y1="b.yHigh" :y2="b.yLow" :stroke="b.color" stroke-width="1.2" stroke-linecap="round" />
            <rect :x="b.cx - BW / 2" :y="b.bodyTop" :width="BW" :height="b.bodyH" rx="1" :fill="b.color" />
        </g>
    </svg>
</template>

<script setup>
/**
 * 최근 N개 일봉 미니 차트 (매수추천 목록 줄).
 * DayCandle mini 는 그날 봉 1개를 그날 고가~저가 비율로 그리지만, 여기서는 N개 봉 전체의
 * 최고가~최저가를 한 기준으로 써서 봉끼리 위치·크기를 비교할 수 있다. 색은 앱 공통(상승 빨강 · 하락 파랑).
 *
 * bars: [{ open, high, low, close }] — 오래된 것 → 최근 순. 값이 빠진 봉은 건너뛴다.
 */
const props = defineProps({
    bars: { type: Array, default: () => [] },
});

const H = 40, PAD = 2;      // DayCandle mini 와 같은 높이
const BW = 4, STEP = 7;     // 몸통 폭 / 봉 간격(중심 간 거리)

const num = (v) => (v === null || v === undefined || v === '' || Number.isNaN(Number(v)) ? null : Number(v));

const valid = computed(() => props.bars
    .map(b => ({ o: num(b.open), h: num(b.high), l: num(b.low), c: num(b.close) }))
    .filter(b => b.o !== null && b.h !== null && b.l !== null && b.c !== null));

const width = computed(() => Math.max(1, valid.value.length) * STEP - (STEP - BW) + 2);

const shapes = computed(() => {
    const bars = valid.value;
    if (!bars.length) return [];
    const hi = Math.max(...bars.map(b => b.h));
    const lo = Math.min(...bars.map(b => b.l));
    const span = hi - lo;
    const y = (v) => (span ? PAD + ((hi - v) / span) * (H - PAD * 2) : H / 2);
    return bars.map((b, i) => {
        const top = Math.min(y(b.o), y(b.c));
        return {
            cx: 1 + BW / 2 + i * STEP,
            yHigh: y(b.h),
            yLow: y(b.l),
            bodyTop: top,
            bodyH: Math.max(1.2, Math.abs(y(b.o) - y(b.c))),
            color: b.c === b.o ? '#8A7A68' : b.c > b.o ? '#C8282A' : '#1F5BD1',
        };
    });
});

const ariaLabel = computed(() => {
    const bars = valid.value;
    if (!bars.length) return '봉 정보 없음';
    const ups = bars.filter(b => b.c > b.o).length;
    return `최근 ${bars.length}일 봉: 양봉 ${ups}개, 음봉 ${bars.filter(b => b.c < b.o).length}개`;
});
</script>

<style scoped>
.mini-candles { display: block; height: 40px; }
</style>
