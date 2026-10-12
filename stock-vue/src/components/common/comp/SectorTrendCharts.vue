<template>
    <div class="sector-trend">
        <!-- ① 누적 등락률: 업종 vs 시장 전체 (같은 % 축) -->
        <div class="chart-block">
            <div class="chart-head">
                <span class="chart-title">{{ days.length }}일 누적 등락률</span>
                <span class="legend">
                    <span class="lg"><i class="sw line" :style="{ background: C_SECTOR }"></i>{{ sectorName }}</span>
                    <span class="lg"><i class="sw dash"></i>{{ marketLabel }} 전체</span>
                </span>
            </div>
            <div class="canvas-wrap" role="img" :aria-label="lineAria"><canvas ref="lineRef"></canvas></div>
        </div>

        <!-- ② 일별 순매수: 외국인 · 기관 (억원) — 등락률과 단위가 달라 차트를 나눈다(이중 축 금지) -->
        <div class="chart-block">
            <div class="chart-head">
                <span class="chart-title">일별 순매수</span>
                <span class="legend">
                    <span class="lg"><i class="sw box" :style="{ background: C_FRGN }"></i>외국인</span>
                    <span class="lg"><i class="sw box" :style="{ background: C_ORGN }"></i>기관</span>
                </span>
            </div>
            <div class="canvas-wrap" role="img" :aria-label="barAria"><canvas ref="barRef"></canvas></div>
        </div>
    </div>
</template>

<script setup>
/**
 * 업종 펼침의 5영업일 추이 (StockSector.vue).
 *   trend / marketTrend : [{ymd, chg_rate, cum_rate, frgn_amt, orgn_amt}] (순매수 = 백만원)
 *   baseYmd             : 누적 0% 기준일 — 선의 첫 점으로 넣는다.
 * 색: 시리즈 색은 dataviz 검증 통과 조합(주황 #C2621B · 보라 #6B5BB5, 흰 배경 6개 검사 PASS).
 *     등락 빨강/파랑은 앱에서 '상승/하락' 뜻이라 시리즈 색으로 쓰지 않는다.
 */
import { Chart, registerables } from 'chart.js';
import { formatNetAmt, shortYmd } from '@scripts/marketFormat.js';
Chart.register(...registerables);

const props = defineProps({
    sectorName: { type: String, default: '' },
    market: { type: String, default: 'KOSPI' },
    baseYmd: { type: String, default: null },
    trend: { type: Array, default: () => [] },
    marketTrend: { type: Array, default: () => [] },
});

const C_SECTOR = '#7A4423';   // 단일 주 시리즈 — 브랜드 잉크
const C_MARKET = '#A89A8A';   // 비교 기준선(점선, 중립 회색)
const C_FRGN = '#C2621B';
const C_ORGN = '#6B5BB5';
const C_GRID = '#F3EAD2';
const C_ZERO = '#D9C9A3';
const C_TICK = '#7A6B5D';

const lineRef = ref(null);
const barRef = ref(null);
let lineChart = null;
let barChart = null;

const marketLabel = computed(() => (props.market === 'KOSPI' ? '코스피' : '코스닥'));
const days = computed(() => props.trend.map(t => t.ymd));
const pct = (v) => (v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(2)}%`);
const eok = (mil) => (mil == null ? null : Math.round(mil / 100));   // 백만원 → 억원(막대 높이)

const lineAria = computed(() => {
    const last = props.trend.at(-1)?.cum_rate, mk = props.marketTrend.at(-1)?.cum_rate;
    return `${props.sectorName} ${days.value.length}일 누적 ${pct(last)}, ${marketLabel.value} 전체 ${pct(mk)}`;
});
const barAria = computed(() => props.trend
    .map(t => `${shortYmd(t.ymd)} 외국인 ${formatNetAmt(t.frgn_amt)} 기관 ${formatNetAmt(t.orgn_amt)}`).join(', '));

// 축·격자는 옅게, 0 선만 조금 진하게
const yScale = (fmt) => ({
    grid: { color: (c) => (c.tick.value === 0 ? C_ZERO : C_GRID), drawBorder: false },
    ticks: { color: C_TICK, font: { size: 10 }, maxTicksLimit: 4, callback: fmt },
});
const xScale = { grid: { display: false, drawBorder: false }, ticks: { color: C_TICK, font: { size: 10 } } };
const tooltipBase = { displayColors: true, boxWidth: 8, boxHeight: 8, padding: 8, titleFont: { size: 11 }, bodyFont: { size: 11 } };

const render = () => {
    lineChart?.destroy();
    barChart?.destroy();
    if (!lineRef.value || !barRef.value || !props.trend.length) return;

    // ── ① 누적 등락률 ── 기준일 0% 에서 시작
    const labels = [props.baseYmd, ...days.value].map(d => (d ? shortYmd(d) : ''));
    const series = (rows) => [0, ...rows.map(t => t.cum_rate)];
    lineChart = new Chart(lineRef.value.getContext('2d'), {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: props.sectorName, data: series(props.trend), borderColor: C_SECTOR, backgroundColor: C_SECTOR,
                  borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, pointBorderColor: '#fff', pointBorderWidth: 2, tension: 0 },
                { label: `${marketLabel.value} 전체`, data: series(props.marketTrend), borderColor: C_MARKET, backgroundColor: C_MARKET,
                  borderWidth: 2, borderDash: [4, 4], pointRadius: 0, pointHoverRadius: 5, tension: 0 },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            layout: { padding: { right: 8 } },
            scales: { x: xScale, y: yScale(v => `${v}%`) },
            plugins: {
                legend: { display: false },
                tooltip: { ...tooltipBase, callbacks: { label: (i) => ` ${i.dataset.label} ${pct(i.raw)}` } },
            },
        },
    });

    // ── ② 일별 순매수(억원) ──
    barChart = new Chart(barRef.value.getContext('2d'), {
        type: 'bar',
        data: {
            labels: days.value.map(shortYmd),
            datasets: [
                { label: '외국인', data: props.trend.map(t => eok(t.frgn_amt)), raw: props.trend.map(t => t.frgn_amt),
                  backgroundColor: C_FRGN, borderRadius: 4, maxBarThickness: 14 },
                { label: '기관', data: props.trend.map(t => eok(t.orgn_amt)), raw: props.trend.map(t => t.orgn_amt),
                  backgroundColor: C_ORGN, borderRadius: 4, maxBarThickness: 14 },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            datasets: { bar: { categoryPercentage: 0.6, barPercentage: 0.85 } },   // 막대 사이 틈
            scales: { x: xScale, y: yScale(v => (Math.abs(v) >= 10000 ? `${(v / 10000).toLocaleString()}조` : `${v.toLocaleString()}억`)) },
            plugins: {
                legend: { display: false },
                tooltip: { ...tooltipBase, callbacks: { label: (i) => ` ${i.dataset.label} ${formatNetAmt(i.dataset.raw[i.dataIndex])}` } },
            },
        },
    });
};

onMounted(render);
watch(() => [props.trend, props.marketTrend], render, { deep: true });
onBeforeUnmount(() => { lineChart?.destroy(); barChart?.destroy(); });
</script>

<style scoped lang="scss">
.sector-trend { display: flex; flex-direction: column; gap: 16px; padding: 12px 0 14px; border-bottom: 1px solid #F3EAD2; }
.chart-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
}
.chart-title { font-size: 12px; font-weight: 700; color: #2B1D14; }
.legend { display: flex; gap: 10px; font-size: 11px; color: #6B5B4E; white-space: nowrap; }
.lg { display: inline-flex; align-items: center; gap: 4px; }
.sw { display: inline-block; flex-shrink: 0; }
.sw.line { width: 12px; height: 2px; }
.sw.dash { width: 12px; height: 0; border-top: 2px dashed #A89A8A; }
.sw.box { width: 8px; height: 8px; border-radius: 2px; }
.canvas-wrap { position: relative; height: 140px; }
</style>
