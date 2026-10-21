<template>
    <div class="lw-stock-chart">
        <!-- 상단 범례: 마우스(터치)가 가리키는 봉의 값, 벗어나면 마지막 봉 -->
        <div v-if="hover" class="lw-legend">
            <div class="lw-ohlc">
                <span class="lw-date">{{ hover.time }}</span>
                <span><em>시가</em>{{ fmt(hover.o) }}</span>
                <span><em>고가</em><b class="up">{{ fmt(hover.h) }}</b></span>
                <span><em>저가</em><b class="down">{{ fmt(hover.l) }}</b></span>
                <span><em>종가</em><b :class="hover.chgClass">{{ fmt(hover.c) }}</b></span>
                <span v-if="hover.chg != null" :class="hover.chgClass">{{ hover.chg > 0 ? '+' : '' }}{{ hover.chg.toFixed(2) }}%</span>
                <span v-if="hover.v != null"><em>거래량</em>{{ fmt(hover.v) }}</span>
            </div>
            <div class="lw-ma">
                <span v-for="m in maLines" :key="m.key" :style="{ '--c': m.color }">
                    <em>{{ m.label }}</em>{{ fmt(hover[m.key]) }}
                </span>
                <span v-if="rsiOn && hover.rsi != null" class="lw-rsi"><em>RSI</em>{{ hover.rsi.toFixed(1) }}</span>
            </div>
        </div>
        <div ref="el" class="lw-canvas"></div>
    </div>
</template>

<script setup>
// TradingView lightweight-charts(Apache 2.0) 기반 캔들 차트 — 휠/핀치 확대, 드래그 이동, 호버 시 상단 범례 갱신.
// 라이선스상 TradingView 출처 표시가 필요해 차트 안 attribution 로고는 끄지 않는다.
// data 는 /api/v1/charts/stock 응답 그대로({ ohcl, volume, ma5..., bb_*, analysis? }, x='YYYY-MM-DD').
// analysis(일봉 분석)는 chartAnalysis/layers.js 가 레이어별로 그린다 — layers 에 든 key 만 그린다.
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, CrosshairMode, LineStyle } from 'lightweight-charts'
import { drawAnalysis } from './chartAnalysis/layers.js'

const props = defineProps({
    data:        { type: Object, required: true },
    visibleBars: { type: Number, default: 120 },   // 처음 보여줄 최근 봉 수(나머지는 왼쪽으로 드래그/축소해서 본다)
    layers:      { type: Array, default: () => [] },   // 켜진 분석 레이어 key
    layerOptions:{ type: Object, default: () => ({}) }, // 레이어별 선택값(예: { elliott: 해석 index })
})

const UP   = '#C8282A'
const DOWN = '#1F5BD1'

const maLines = [
    { key: 'ma5',   label: 'MA5',   color: '#f38980' },
    { key: 'ma20',  label: 'MA20',  color: '#efa55b' },
    { key: 'ma60',  label: 'MA60',  color: '#8bb400' },
    { key: 'ma120', label: 'MA120', color: '#01b6f3' },
]
const bbLines = [
    { key: 'bb_upper', color: '#a78bfa' },
    { key: 'bb_mid',   color: '#818cf8' },
    { key: 'bb_lower', color: '#a78bfa' },
]

const el    = ref(null)
const hover = ref(null)
const rsiOn = ref(false)
let chart   = null
let byTime  = new Map()   // time → 범례용 값 묶음
let lastRow = null

const fmt = (v) => (v == null || Number.isNaN(v)) ? '-' : Math.round(v).toLocaleString('ko-KR')

// x/y 배열 → { time, value }, 값 없는 앞쪽 구간(이평선 워밍업)은 뺀다
const toLine = (arr) => (arr || [])
    .filter(p => p && p.y != null)
    .map(p => ({ time: p.x, value: Number(p.y) }))

const buildRows = (d) => {
    const vol = new Map((d.volume || []).map(p => [p.x, p.y]))
    const ma  = Object.fromEntries(maLines.map(m => [m.key, new Map((d[m.key] || []).map(p => [p.x, p.y]))]))
    const rsi = new Map((d.analysis?.rsi?.series || []).map(p => [p.x, p.y]))
    byTime = new Map()
    let prevClose = null
    for (const c of d.ohcl || []) {
        const chg = prevClose ? (c.c - prevClose) / prevClose * 100 : null
        const row = {
            time: c.x, o: c.o, h: c.h, l: c.l, c: c.c,
            v: vol.get(c.x) ?? null,
            chg,
            chgClass: chg == null || chg === 0 ? '' : chg > 0 ? 'up' : 'down',
        }
        for (const m of maLines) row[m.key] = ma[m.key].get(c.x) ?? null
        row.rsi = rsi.get(c.x) ?? null
        byTime.set(c.x, row)
        prevClose = c.c
        lastRow = row
    }
}

// keepRange: 레이어만 바꿔 다시 그릴 때 보던 확대·이동 위치를 유지한다
const render = (keepRange = false) => {
    const prevRange = keepRange ? chart?.timeScale().getVisibleLogicalRange() : null
    if (chart) { chart.remove(); chart = null }
    const d = props.data
    if (!d || !el.value) return
    buildRows(d)

    chart = createChart(el.value, {
        autoSize: true,
        layout: {
            background: { color: '#FFFFFF' },
            textColor: '#6B5B4E',
            fontFamily: "'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif",
        },
        grid: {
            vertLines: { visible: false },
            horzLines: { color: '#F4ECD6' },
        },
        crosshair: {
            mode: CrosshairMode.Normal,
            vertLine: { color: '#B9A58C', labelBackgroundColor: '#74462A' },
            horzLine: { color: '#B9A58C', labelBackgroundColor: '#74462A' },
        },
        rightPriceScale: { borderColor: '#EFE2BC', scaleMargins: { top: 0.08, bottom: 0.22 } },
        timeScale: { borderColor: '#EFE2BC', rightOffset: 4, minBarSpacing: 2 },
        localization: {
            locale: 'ko-KR',
            priceFormatter: (p) => Math.round(p).toLocaleString('ko-KR'),
            // 십자선 날짜 라벨: 기본값('22 6월 '26') 대신 YYYY-MM-DD
            timeFormatter: (t) => typeof t === 'string' ? t
                : typeof t === 'object' ? `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`
                : new Date(t * 1000).toISOString().slice(0, 10),
        },
    })

    // 거래량: 별도 오버레이 축으로 하단 18%만 쓴다
    const volSeries = chart.addSeries(HistogramSeries, {
        priceScaleId: 'vol',
        priceFormat: { type: 'volume' },
        lastValueVisible: false,
        priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    volSeries.setData((d.ohcl || []).map(c => ({
        time: c.x,
        value: byTime.get(c.x)?.v ?? 0,
        color: c.c >= c.o ? 'rgba(200,40,42,0.28)' : 'rgba(31,91,209,0.28)',
    })))

    for (const b of bbLines) {
        chart.addSeries(LineSeries, {
            color: b.color, lineWidth: 1, lineStyle: LineStyle.Dashed,
            lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
        }).setData(toLine(d[b.key]))
    }
    for (const m of maLines) {
        chart.addSeries(LineSeries, {
            color: m.color, lineWidth: 1.5,
            lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
        }).setData(toLine(d[m.key]))
    }

    // 캔들은 맨 마지막에 올려 선들 위에 그려지게 한다
    const candle = chart.addSeries(CandlestickSeries, {
        upColor: UP, downColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, borderVisible: false,
    })
    candle.setData((d.ohcl || []).map(c => ({ time: c.x, open: c.o, high: c.h, low: c.l, close: c.c })))

    const n = (d.ohcl || []).length
    const drawn = drawAnalysis({
        chart, candle, analysis: d.analysis, enabled: props.layers,
        times: (d.ohcl || []).map(c => c.x), options: props.layerOptions,
    })
    rsiOn.value = drawn.rsiOn

    if (prevRange) {
        chart.timeScale().setVisibleLogicalRange(prevRange)
    } else if (n > props.visibleBars || drawn.futureBars) {
        // 예상 경로가 있으면 오른쪽에 그 앞부분(최대 40봉)까지 보이게 둔다
        chart.timeScale().setVisibleLogicalRange({
            from: Math.max(n - props.visibleBars, 0), to: n + 4 + Math.min(drawn.futureBars, 40),
        })
    } else {
        chart.timeScale().fitContent()
    }

    hover.value = lastRow
    chart.subscribeCrosshairMove((p) => {
        const row = p.time ? byTime.get(p.time) : null
        hover.value = row || lastRow
    })
}

onMounted(() => render())
watch(() => props.data, () => nextTick(() => render()))
watch(() => [props.layers, props.layerOptions], () => nextTick(() => render(true)), { deep: true })
onBeforeUnmount(() => { chart?.remove(); chart = null })
</script>

<style scoped lang="scss">
.lw-stock-chart {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.lw-legend {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-bottom: 8px;
    font-size: 13px;
    color: #2B1D14;
    font-variant-numeric: tabular-nums;

    em {
        font-style: normal;
        color: #7A6B5D;
        margin-right: 4px;
    }
    b { font-weight: 700; }
    .up   { color: #C8282A; }
    .down { color: #1F5BD1; }
}

.lw-ohlc, .lw-ma {
    display: flex;
    flex-wrap: wrap;
    column-gap: 12px;
    row-gap: 2px;
}

.lw-date { font-weight: 600; color: #6B5B4E; }

.lw-ma .lw-rsi::before { background: #8E7CC3; }

.lw-ma {
    font-size: 12px;

    span {
        display: inline-flex;
        align-items: center;
        &::before {
            content: '';
            width: 12px;
            height: 2px;
            margin-right: 5px;
            background: var(--c);
        }
    }
}

.lw-canvas {
    flex: 1;
    min-height: 0;
}
</style>
