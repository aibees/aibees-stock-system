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

// 순매수 막대: 두께 BAR_PX, 외국인·기관 사이 BAR_GAP_PX. 좁은 화면에선 칸에 맞춰 줄어든다.
const BAR_PX = 24;
const BAR_GAP_PX = 2;
const CAT_PCT_MAX = 0.72;   // 날짜 칸에서 막대 묶음이 쓰는 최대 비율(나머지는 날짜 사이 여백)

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
                  backgroundColor: C_FRGN, borderRadius: 4, maxBarThickness: BAR_PX },
                { label: '기관', data: props.trend.map(t => eok(t.orgn_amt)), raw: props.trend.map(t => t.orgn_amt),
                  backgroundColor: C_ORGN, borderRadius: 4, maxBarThickness: BAR_PX },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            datasets: { bar: { categoryPercentage: CAT_PCT_MAX, barPercentage: 0.96 } },   // 실제 값은 fitBars 가 너비에 맞춰 정한다
            onResize: () => setTimeout(fitBars, 0),   // 리사이즈 직후 Chart.js 가 레이아웃을 다시 잡은 다음에 맞춘다
            scales: { x: xScale, y: yScale(v => (Math.abs(v) >= 10000 ? `${(v / 10000).toLocaleString()}조` : `${v.toLocaleString()}억`)) },
            plugins: {
                legend: { display: false },
                tooltip: { ...tooltipBase, callbacks: { label: (i) => ` ${i.dataset.label} ${formatNetAmt(i.dataset.raw[i.dataIndex])}` } },
            },
        },
    });
    fitBars();
};

/* 막대 간격을 화면 너비와 무관하게 유지한다.
 *   Chart.js 는 막대 자리를 '날짜 칸 × 비율'로 잡고 두께만 maxBarThickness 로 자른다. 그래서 PC 처럼 칸이 넓으면
 *   두께는 24px 에서 멈추는데 두 막대의 자리는 계속 벌어져 외국인·기관 사이가 20px 넘게 뜬다.
 *   → 실제 칸 너비를 보고, 묶음 폭이 (두께×2 + 틈) 이 되도록 비율을 다시 계산한다. */
const fitBars = () => {
    const area = barChart?.chartArea;
    const n = barChart?.data.labels.length;
    if (!area || !n) return;
    // 막대 한 개의 자리(slot) = 두께 + 틈. Chart.js 는 slot 안에서 두께 = slot × barPercentage 로 가운데 놓으므로
    // 이웃한 외국인·기관 막대 사이 틈 = slot − 두께.
    const catW = (area.right - area.left) / n;
    const groupW = (BAR_PX + BAR_GAP_PX) * 2;
    const wide = groupW / catW < CAT_PCT_MAX;
    const slot = wide ? BAR_PX + BAR_GAP_PX : (catW * CAT_PCT_MAX) / 2;
    const bar = barChart.options.datasets.bar;
    const next = {
        categoryPercentage: wide ? groupW / catW : CAT_PCT_MAX,
        barPercentage: 1 - BAR_GAP_PX / slot,
    };
    if (Math.abs(bar.categoryPercentage - next.categoryPercentage) < 1e-3
        && Math.abs(bar.barPercentage - next.barPercentage) < 1e-3) return;
    Object.assign(bar, next);
    barChart.update('none');
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
