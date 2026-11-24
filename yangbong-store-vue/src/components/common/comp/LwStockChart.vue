<template>
    <div class="lw-stock-chart">
        <!-- 상단 범례: 마우스(터치)가 가리키는 봉의 값, 벗어나면 마지막 봉 -->
        <!-- 쉬운 보기: 짚은 봉을 한 줄 문장으로 풀어서 보여준다 -->
        <div v-if="hover && simple" class="lw-simple-legend">
            <span class="lw-date">{{ hover.time }}</span>
            <span>종가 <b :class="hover.chgClass">{{ fmt(hover.c) }}원</b></span>
            <span v-if="hover.chg != null" :class="hover.chgClass">{{ hover.chg > 0 ? '+' : '' }}{{ hover.chg.toFixed(2) }}%</span>
            <span v-if="showVolume && hover.volRatio != null" class="lw-vol-note">거래량 평소의 {{ hover.volRatio.toFixed(1) }}배</span>
        </div>
        <div v-else-if="hover" class="lw-legend">
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
                <span v-for="m in activeMa" :key="m.key" :style="{ '--c': m.color }">
                    <em>{{ m.label }}</em>{{ fmt(hover[m.key]) }}
                </span>
                <span v-if="rsiOn && hover.rsi != null" class="lw-rsi"><em>RSI</em>{{ hover.rsi.toFixed(1) }}</span>
            </div>
        </div>
        <div class="lw-plot">
            <div ref="el" class="lw-canvas"></div>
            <!-- 쉬운 보기: 가격축 대신 보이는 구간의 최고·최저·현재가를 차트 위에 얹는다 -->
            <span v-for="m in marks" :key="m.key" class="lw-mark" :class="m.cls" :style="{ top: m.y + 'px' }">{{ m.text }}</span>
        </div>
    </div>
</template>

<script setup>
// TradingView lightweight-charts(Apache 2.0) 기반 캔들 차트 — 휠/핀치 확대, 드래그 이동, 호버 시 상단 범례 갱신.
// 라이선스(Apache 2.0 + NOTICE)는 "NOTICE 문구 + tradingview.com 링크를 앱 안 페이지에 두는 것"을 요구하고,
// 이를 이미 지키면 차트 안 로고(attributionLogo)는 꺼도 된다고 라이브러리 문서가 밝힌다.
// 그 문구·링크는 고객지원 > 오픈소스 라이선스(scripts/data/licenses.js)에 있다 — 그 항목을 지우면 로고를 다시 켜야 한다.
// data 는 /api/v1/charts/stock 응답 그대로({ ohcl, volume, ma5..., bb_*, analysis? }, x='YYYY-MM-DD').
// analysis(일봉 분석)는 chartAnalysis/layers.js 가 레이어별로 그린다 — layers 에 든 key 만 그린다.
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, CrosshairMode, LineStyle } from 'lightweight-charts'
import { drawAnalysis } from './chartAnalysis/layers.js'

const props = defineProps({
    data:        { type: Object, required: true },
    visibleBars: { type: Number, default: 120 },   // 처음 보여줄 최근 봉 수(나머지는 왼쪽으로 드래그/축소해서 본다)
    layers:      { type: Array, default: () => [] },   // 켜진 분석 레이어 key
    layerOptions:{ type: Object, default: () => ({}) }, // 레이어별 선택값(예: { elliott: 해석 index })
    // 'pro' = 기존 화면 그대로, 'simple' = 초보자용(캔들 + 고른 지표만, 범례는 한 줄 문장)
    mode:        { type: String, default: 'pro' },
    indicators:  { type: Array, default: () => ['volume'] },  // simple 에서 켤 지표: volume | ma5 | ma20 | ma60 | ma120 | bb
})

const simple     = computed(() => props.mode === 'simple')
const showVolume = computed(() => !simple.value || props.indicators.includes('volume'))
const MA_PERIOD  = { ma5: 5, ma20: 20, ma60: 60, ma120: 120 }

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
const marks = ref([])   // 쉬운 보기 오버레이 라벨 [{ key, y, text, cls }]
const hover = ref(null)
const rsiOn = ref(false)
let chart   = null
let byTime  = new Map()   // time → 범례용 값 묶음
let lastRow = null

// 가격축 눈금용: 71,000 → 7.1만, 392,000 → 39.2만, 1,250,000 → 125만. 1만 미만은 그대로
const shortPrice = (p) => {
    const a = Math.abs(p)
    if (a < 10000) return Math.round(p).toLocaleString('ko-KR')
    const m = p / 10000
    return `${(a >= 100000 ? Math.round(m) : Math.round(m * 10) / 10).toLocaleString('ko-KR')}만`
}

const fmt = (v) => (v == null || Number.isNaN(v)) ? '-' : Math.round(v).toLocaleString('ko-KR')

// x/y 배열 → { time, value }, 값 없는 앞쪽 구간(이평선 워밍업)은 뺀다
const toLine = (arr) => (arr || [])
    .filter(p => p && p.y != null)
    .map(p => ({ time: p.x, value: Number(p.y) }))

// 서버가 이평선을 안 줘도(목업 등) 종가로 직접 계산한다
const calcMa = (ohcl, p) => (ohcl || []).map((c, i, a) => {
    if (i + 1 < p) return null
    let sum = 0
    for (let k = i + 1 - p; k <= i; k++) sum += a[k].c
    return { x: c.x, y: sum / p }
}).filter(Boolean)
// 볼린저밴드(20일, 2σ) 폴백 — 서버가 bb_upper/bb_mid/bb_lower 를 안 줄 때만
const bbOf = (d, key) => {
    if (d[key] && d[key].length) return d[key]
    const o = d.ohcl || [], p = 20
    return o.map((c, i) => {
        if (i + 1 < p) return null
        const w = o.slice(i + 1 - p, i + 1).map(k => k.c)
        const mid = w.reduce((a, b) => a + b, 0) / p
        const sd = Math.sqrt(w.reduce((a, b) => a + (b - mid) ** 2, 0) / p)
        return { x: c.x, y: key === 'bb_upper' ? mid + 2 * sd : key === 'bb_lower' ? mid - 2 * sd : mid }
    }).filter(Boolean)
}
const maOf = (d, key) => (d[key] && d[key].length) ? d[key] : calcMa(d.ohcl, MA_PERIOD[key])

// 화면에 그릴 이평선(쉬운 보기에서는 고른 것만)
const activeMa = computed(() => simple.value ? maLines.filter(m => props.indicators.includes(m.key)) : maLines)

const buildRows = (d) => {
    const vol = new Map((d.volume || []).map(p => [p.x, p.y]))
    const ma  = Object.fromEntries(maLines.map(m => [m.key, new Map(maOf(d, m.key).map(p => [p.x, p.y]))]))
    const volArr = (d.ohcl || []).map(c => vol.get(c.x) ?? 0)
    const rsi = new Map((d.analysis?.rsi?.series || []).map(p => [p.x, p.y]))
    byTime = new Map()
    let prevClose = null
    let idx = -1
    for (const c of d.ohcl || []) {
        idx++
        const chg = prevClose ? (c.c - prevClose) / prevClose * 100 : null
        const row = {
            time: c.x, o: c.o, h: c.h, l: c.l, c: c.c,
            v: vol.get(c.x) ?? null,
            // 직전 20일 평균 거래량 대비 몇 배인지(쉬운 보기 문장용)
            volRatio: idx >= 20 ? (() => { const a = volArr.slice(idx - 20, idx).reduce((x, y) => x + y, 0) / 20; return a > 0 ? volArr[idx] / a : null })() : null,
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
            fontSize: simple.value ? 12 : 11,
            attributionLogo: false,
            fontFamily: "'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif",
        },
        grid: {
            vertLines: { visible: false },
            // 쉬운 보기는 가격 눈금 오버레이가 가로선을 함께 그린다
            horzLines: { color: '#F4ECD6', visible: !simple.value },
        },
        crosshair: {
            mode: CrosshairMode.Normal,
            vertLine: { color: '#B9A58C', labelBackgroundColor: '#74462A' },
            horzLine: { color: '#B9A58C', labelBackgroundColor: '#74462A' },
        },
        // 쉬운 보기: 눈금은 짧게(7.1만) 줄이고 테두리·눈금선을 없애 가격축이 차지하는 폭을 줄인다
        rightPriceScale: {
            borderColor: '#EFE2BC', scaleMargins: { top: 0.08, bottom: simple.value ? 0.2 : 0.22 },
            // 가격축을 없애 차트 폭을 넓힌다. 가격은 아래 최고·현재·최저 라벨과 위 범례 문장으로 읽는다
            ...(simple.value ? { visible: false } : {}),
        },
        timeScale: { borderColor: '#EFE2BC', rightOffset: 4, minBarSpacing: 2 },
        localization: {
            locale: 'ko-KR',
            priceFormatter: (p) => Math.round(p).toLocaleString('ko-KR'),
            // 눈금 라벨만 만 단위로 줄인다(십자선·현재가 라벨은 위 priceFormatter 의 정확한 값)
            ...(simple.value ? { tickmarksPriceFormatter: (prices) => prices.map(shortPrice) } : {}),
            // 십자선 날짜 라벨: 기본값('22 6월 '26') 대신 YYYY-MM-DD
            timeFormatter: (t) => typeof t === 'string' ? t
                : typeof t === 'object' ? `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`
                : new Date(t * 1000).toISOString().slice(0, 10),
        },
    })

    // 거래량: 별도 오버레이 축으로 하단 18%만 쓴다
    if (showVolume.value) {
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
    }

    for (const b of (simple.value && !props.indicators.includes('bb') ? [] : bbLines)) {
        chart.addSeries(LineSeries, {
            color: b.color, lineWidth: 1, lineStyle: LineStyle.Dashed,
            lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
        }).setData(toLine(bbOf(d, b.key)))
    }
    for (const m of activeMa.value) {
        chart.addSeries(LineSeries, {
            color: m.color, lineWidth: simple.value ? 2 : 1.5,
            lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
        }).setData(toLine(maOf(d, m.key)))
    }

    // 캔들은 맨 마지막에 올려 선들 위에 그려지게 한다
    const candle = chart.addSeries(CandlestickSeries, {
        upColor: UP, downColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, borderVisible: false,
        // 쉬운 보기: 현재가 라벨이 가격축 폭을 넓히므로 끈다(종가는 위 범례 문장에 나온다)
        lastValueVisible: !simple.value,
    })
    candle.setData((d.ohcl || []).map(c => ({ time: c.x, open: c.o, high: c.h, low: c.l, close: c.c })))

    const n = (d.ohcl || []).length

    // 쉬운 보기: 가격축 폭을 따로 잡지 않고, 가격 눈금과 현재가를 차트 안쪽(오른쪽)에 얹는다.
    // 확대·이동하면 보이는 가격 범위에 맞춰 눈금이 다시 계산된다.
    if (simple.value && n) {
        const last = d.ohcl[n - 1].c
        const up = last >= (d.ohcl[n - 2]?.c ?? last)
        // 현재가 점선만 차트에 그리고, 글자는 아래 오버레이로 얹는다
        candle.createPriceLine({ price: last, color: up ? UP : DOWN, lineWidth: 1,
            lineStyle: LineStyle.Dotted, lineVisible: true, axisLabelVisible: false, title: '' })
        const drawMarks = () => {
            if (!chart || !el.value) return
            const paneH = el.value.clientHeight - 28            // 아래 날짜축 높이는 뺀다
            const usable = paneH * (showVolume.value ? 0.8 : 0.95)   // 거래량 막대 영역 위까지만 눈금을 둔다
            const pTop = candle.coordinateToPrice(0), pBot = candle.coordinateToPrice(paneH)
            if (pTop == null || pBot == null || pTop <= pBot) { marks.value = []; return }
            // 1·2·5 × 10ⁿ 단위. 범위에 거래량 영역이 섞여 있어 눈금이 보이는 곳엔 5~6개 정도 나온다
            const raw = (pTop - pBot) / 8, mag = 10 ** Math.floor(Math.log10(raw))
            const step = ([1, 2, 5, 10].find(m => m * mag >= raw) ?? 10) * mag
            const out = []
            for (let v = Math.ceil(pBot / step) * step; v <= pTop; v += step) {
                const y = candle.priceToCoordinate(v)
                if (y != null && y > 10 && y < usable) out.push({ key: `t${v}`, y: Math.round(y), text: fmt(v), cls: 'tick' })
            }
            const yl = candle.priceToCoordinate(last)
            if (yl != null) out.push({ key: 'last', y: Math.round(yl), text: fmt(last), cls: `last ${up ? 'up' : 'down'}` })
            marks.value = out
        }
        // 범위가 바뀐 뒤 세로 자동 맞춤이 끝나야 좌표가 맞아서 한 프레임 늦춘다
        chart.timeScale().subscribeVisibleLogicalRangeChange(() => requestAnimationFrame(drawMarks))
        requestAnimationFrame(drawMarks)
    } else {
        marks.value = []
    }

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
// 값이 실제로 바뀔 때만 다시 그린다(새 종목을 받으면 data 쪽 watch 가 이미 그리므로 같은 레이어면 건너뜀)
watch(() => JSON.stringify([props.layers, props.layerOptions, props.mode, props.indicators]), () => nextTick(() => render(true)))
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

.lw-simple-legend {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    column-gap: 12px;
    padding-bottom: 8px;
    font-size: 14px;
    color: #2B1D14;
    font-variant-numeric: tabular-nums;
    .up   { color: #C8282A; }
    .down { color: #1F5BD1; }
    b { font-weight: 700; }
    .lw-vol-note { color: #7A6B5D; font-size: 13px; }
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

.lw-plot {
    position: relative;
    flex: 1;
    min-height: 0;
}

.lw-canvas { height: 100%; }

// 가격 라벨: 오른쪽 끝, 점선/캔들 위에 살짝 얹는다(터치를 막지 않게 pointer-events 없음)
.lw-mark {
    position: absolute;
    right: 6px;
    z-index: 5;
    transform: translateY(-100%);
    padding: 1px 6px;
    border-radius: 6px;
    background: rgba(255, 255, 255, .82);
    color: #6B5B4E;
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    line-height: 1.3;
    pointer-events: none;
    // 가격 눈금: 가로 보조선 + 오른쪽 숫자(보조선 바로 위)
    &.tick {
        left: 0;
        right: 0;
        padding: 0 8px 1px 0;
        border-radius: 0;
        border-bottom: 1px solid #F3EBD6;
        background: none;
        color: #A39482;
        font-weight: 500;
        text-align: right;
        z-index: 1;
    }
    // 현재가: 등락색 칩
    &.last { z-index: 6; color: #fff; transform: translateY(-50%); background: #C8282A; }
    &.last.down { background: #1F5BD1; }
    &.up   { color: #C8282A; }
    &.down { color: #1F5BD1; }
    &.last.up, &.last.down { color: #fff; }
}
</style>
