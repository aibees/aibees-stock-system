<template>
    <div class="day-candle">
        <svg v-if="ok" :viewBox="`0 0 ${W} ${H}`" role="img"
            :aria-label="`시가 ${fmt(open)} 고가 ${fmt(high)} 저가 ${fmt(low)} ${closeLabel} ${fmt(close)}`">
            <!-- 꼬리(고가~저가) + 몸통(시가~종가) -->
            <line :x1="CX" :x2="CX" :y1="yOf(high)" :y2="yOf(low)" :stroke="color" stroke-width="2" stroke-linecap="round" />
            <rect :x="CX - 14" :y="bodyTop" width="28" :height="bodyH" rx="3" :fill="color" />

            <!-- 기준선 + 라벨: 가격 위치에 맞추되 라벨끼리 겹치면 위아래로 벌린다 -->
            <g v-for="l in labels" :key="l.key">
                <line :x1="CX + 18" :x2="LX - 6" :y1="l.y" :y2="l.ty - 4" stroke="#E3D3A8" stroke-width="1" />
                <text :x="LX" :y="l.ty" class="lab">{{ l.name }}</text>
                <text :x="W" :y="l.ty" class="val" :class="l.cls" text-anchor="end">{{ fmt(l.v) }}</text>
            </g>
        </svg>
        <p v-if="volume !== undefined && volume !== null" class="vol">거래량 <b>{{ fmt(volume) }}</b></p>
    </div>
</template>

<script setup>
/**
 * 하루치 봉(시/고/저/종)을 봉 모양으로 보여준다. 장중에는 종가 자리가 현재가다.
 * 가격 위치(세로)는 실제 값에 비례하고, 한국식 색(상승 빨강 · 하락 파랑)을 쓴다.
 */
const props = defineProps({
    open: { type: [Number, String], default: null },
    high: { type: [Number, String], default: null },
    low: { type: [Number, String], default: null },
    close: { type: [Number, String], default: null },
    volume: { type: [Number, String], default: null },
    closeLabel: { type: String, default: '종가' },
});

const W = 320, H = 132, CX = 38, LX = 96, PAD = 12, GAP = 22;

const n = (v) => (v === null || v === undefined || v === '' || Number.isNaN(Number(v)) ? null : Number(v));
const open = computed(() => n(props.open));
const high = computed(() => n(props.high));
const low = computed(() => n(props.low));
const close = computed(() => n(props.close));
const ok = computed(() => [open, high, low, close].every(r => r.value !== null));

const fmt = (v) => Number(v).toLocaleString();
const up = computed(() => close.value >= open.value);
const color = computed(() => (close.value === open.value ? '#8A7A68' : up.value ? '#C8282A' : '#1F5BD1'));

// 값 → y (고가가 위). 고가=저가면 가운데.
const yOf = (v) => {
    const span = high.value - low.value;
    if (!span) return H / 2;
    return PAD + ((high.value - v) / span) * (H - PAD * 2);
};
const bodyTop = computed(() => Math.min(yOf(open.value), yOf(close.value)));
const bodyH = computed(() => Math.max(3, Math.abs(yOf(open.value) - yOf(close.value))));

const labels = computed(() => {
    const items = [
        { key: 'h', name: '고가', v: high.value, cls: 'up' },
        { key: 'o', name: '시가', v: open.value, cls: '' },
        { key: 'c', name: props.closeLabel, v: close.value, cls: 'strong' },
        { key: 'l', name: '저가', v: low.value, cls: 'down' },
    ].map(i => ({ ...i, y: yOf(i.v), ty: yOf(i.v) + 4 }));

    // y 순으로 정렬해 최소 간격(GAP)을 확보 — 위에서 아래로 밀고, 넘치면 아래에서 위로 되민다.
    const sorted = [...items].sort((a, b) => a.y - b.y || (a.key === 'h' ? -1 : 0));
    for (let i = 1; i < sorted.length; i++) {
        if (sorted[i].ty - sorted[i - 1].ty < GAP) sorted[i].ty = sorted[i - 1].ty + GAP;
    }
    const maxTy = H - 2;
    if (sorted[sorted.length - 1].ty > maxTy) {
        sorted[sorted.length - 1].ty = maxTy;
        for (let i = sorted.length - 2; i >= 0; i--) {
            if (sorted[i + 1].ty - sorted[i].ty < GAP) sorted[i].ty = sorted[i + 1].ty - GAP;
        }
    }
    return sorted;
});
</script>

<style scoped lang="scss">
.day-candle {
    background: #fff;
    border: 1px solid #EFE2BC;
    border-radius: 10px;
    padding: 10px 14px 8px;
    font-variant-numeric: tabular-nums;
}
svg { display: block; width: 100%; height: auto; max-height: 150px; }
.lab { font-size: 11px; fill: #6B5B4E; font-weight: 600; }
.val { font-size: 13px; fill: #2B1D14; font-weight: 600; }
.val.up { fill: #C8282A; }
.val.down { fill: #1F5BD1; }
.val.strong { font-weight: 700; }
.vol {
    margin: 6px 0 0;
    padding-top: 8px;
    border-top: 1px solid #F3EAD2;
    font-size: 12px;
    color: #6B5B4E;
    display: flex;
    justify-content: space-between;
    b { font-size: 13px; color: #2B1D14; }
}
</style>
