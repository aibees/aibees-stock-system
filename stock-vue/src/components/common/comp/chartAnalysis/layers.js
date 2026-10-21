// 일봉 차트 분석 레이어 — /charts/stock 응답의 analysis.{모듈} 하나당 레이어 하나.
// 새 분석을 붙일 때는 서버 chart_analysis.MODULES 에 모듈을 추가하고 여기에 같은 key 로 draw 를 추가한다.
// draw(ctx, data): 시리즈·가격선·박스는 직접 그리고, 마커는 ctx.markers 에 모은다(시리즈당 마커 플러그인은 하나라).
import { LineSeries, LineStyle, createSeriesMarkers } from 'lightweight-charts'
import { ZonePrimitive } from './ZonePrimitive.js'

export const C = {
    buy:   '#C8282A',   // 매수 쪽(앱 공통 상승색)
    sell:  '#1F5BD1',   // 매도 쪽(앱 공통 하락색)
    swing: '#B9A58C',
    struct:'#9A6B4F',
    fib:   '#8E6FB5',
    rsi:   '#8E7CC3',
    pat:   '#7A4423',
}

// 두 점 이상을 잇는 보조선. 같은 날짜가 겹치면 뒤의 값만 남긴다(시간축은 엄격히 증가해야 한다)
const addLine = (ctx, points, opts = {}, pane = 0) => {
    const byTime = new Map()
    for (const p of points) if (p.time && p.value != null) byTime.set(p.time, p.value)
    const data = [...byTime].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([time, value]) => ({ time, value }))
    if (data.length < 2) return null
    const s = ctx.chart.addSeries(LineSeries, {
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
        autoscaleInfoProvider: () => null,   // 보조선 때문에 가격축이 늘어나지 않게
        ...opts,
    }, pane)
    s.setData(data)
    return s
}

const priceLine = (ctx, price, color, title, style = LineStyle.Dashed, axisLabelVisible = true) => {
    if (price == null) return
    ctx.candle.createPriceLine({ price, color, lineWidth: 1, lineStyle: style, axisLabelVisible, title })
}

const marker = (ctx, p, text, color) => {
    const high = p.kind === 'H'
    ctx.markers.push({
        time: p.date,
        position: high ? 'aboveBar' : 'belowBar',
        shape: high ? 'arrowDown' : 'arrowUp',
        color,
        text,
        size: 0.6,
    })
}

const zone = (ctx, from, lo, hi, side, label) => {
    const color = side === 'buy' ? C.buy : C.sell
    ctx.candle.attachPrimitive(new ZonePrimitive({
        from, top: hi, bottom: lo,
        fill: side === 'buy' ? 'rgba(200,40,42,0.07)' : 'rgba(31,91,209,0.07)',
        stroke: side === 'buy' ? 'rgba(200,40,42,0.35)' : 'rgba(31,91,209,0.35)',
        label, textColor: color,
    }))
}

// ── 레이어별 그리기 ───────────────────────────────────────────────

const drawSwing = (ctx, swings) => {
    addLine(ctx, swings.map(p => ({ time: p.date, value: p.price })), { color: C.swing })
}

const drawStructure = (ctx, s) => {
    if (!s) return
    priceLine(ctx, s.resistance?.price, C.struct, '직전 고점')
    priceLine(ctx, s.support?.price, C.struct, '직전 저점')
}

const drawFib = (ctx, f) => {
    if (!f) return
    addLine(ctx, [{ time: f.from.date, value: f.from.price }, { time: f.to.date, value: f.to.price }],
        { color: C.fib, lineStyle: LineStyle.Dashed })
    for (const lv of f.levels) {
        if (lv.ratio === 0.236 || lv.ratio === 1.618) continue   // 선이 너무 많아져서 화면에는 뺀다(요약에는 나온다)
        priceLine(ctx, lv.price, 'rgba(142,111,181,0.55)', String(lv.ratio), LineStyle.Dotted, false)
    }
    // 아직 유효한 타점(대기·구간 진입)일 때만 후보 박스를 그린다 — 손절 이탈·무효면 레벨선만 남긴다
    if ((f.status === 'waiting' || f.status === 'in_zone') && f.plan?.zone) {
        const [lo, hi] = f.plan.zone
        zone(ctx, f.to.date, lo, hi, f.plan.side, f.plan.side === 'buy' ? '매수 후보' : '매도 후보')
    }
}

const drawRsi = (ctx, r) => {
    if (!r?.series?.length) return
    const pane = 1
    const s = ctx.chart.addSeries(LineSeries, {
        color: C.rsi, lineWidth: 1.5,
        lastValueVisible: true, priceLineVisible: false, crosshairMarkerVisible: false,
        priceFormat: { type: 'custom', formatter: (v) => v.toFixed(0) },
    }, pane)
    s.setData(r.series.filter(p => p.y != null).map(p => ({ time: p.x, value: p.y })))
    for (const lv of [70, 30]) {
        s.createPriceLine({ price: lv, color: '#D9CBB0', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false })
    }
    ctx.chart.panes()[0]?.setStretchFactor(3)
    ctx.chart.panes()[pane]?.setStretchFactor(1)
    ctx.rsiPane = pane
}

const drawDivergence = (ctx, list) => {
    for (const d of list || []) {
        const color = d.bias === 'bull' ? C.buy : C.sell
        const style = { color, lineStyle: d.kind.startsWith('hidden') ? LineStyle.Dotted : LineStyle.Dashed }
        addLine(ctx, [{ time: d.from.date, value: d.from.price }, { time: d.to.date, value: d.to.price }], style)
        if (ctx.rsiPane != null) {
            addLine(ctx, [{ time: d.from.date, value: d.from.rsi }, { time: d.to.date, value: d.to.rsi }], style, ctx.rsiPane)
        }
        marker(ctx, { date: d.to.date, kind: d.bias === 'bull' ? 'L' : 'H' }, `RSI ${d.label}`, color)
    }
}

const drawPattern = (ctx, list) => {
    for (const p of list || []) {
        const side = p.plan?.side
        const color = side === 'buy' ? C.buy : C.sell
        addLine(ctx, p.points.map(pt => ({ time: pt.date, value: pt.price })), { color: C.pat, lineWidth: 2 })
        const last = p.points[p.points.length - 1]
        if (p.type === 'abcd') {
            p.points.forEach(pt => marker(ctx, pt, pt.label, C.pat))
            // C → D 투영(오늘 봉 위치에 D)
            addLine(ctx, [{ time: last.date, value: last.price }, { time: ctx.lastTime, value: p.d }],
                { color: C.pat, lineStyle: LineStyle.Dashed })
            priceLine(ctx, p.d, color, 'D')
        } else {
            marker(ctx, last, p.label, C.pat)
            addLine(ctx, [{ time: p.points[0].date, value: p.neckline }, { time: ctx.lastTime, value: p.neckline }],
                { color, lineStyle: LineStyle.Dashed })
        }
        if (p.status === 'triggered' || p.status === 'waiting' || p.status === 'forming') {
            priceLine(ctx, p.plan?.target, color, `${p.label} 목표`, LineStyle.LargeDashed)
        }
    }
}

// 순서가 곧 그리는 순서 — RSI 패널이 먼저 생겨야 다이버전스가 RSI 쪽에도 선을 긋는다
export const LAYERS = [
    { key: 'swing',      label: '스윙 고저점', draw: drawSwing },
    { key: 'structure',  label: '추세 구조',   draw: drawStructure },
    { key: 'fib',        label: '피보나치',     draw: drawFib },
    { key: 'rsi',        label: 'RSI(14)',     draw: drawRsi },
    { key: 'divergence', label: 'RSI 다이버전스', draw: drawDivergence },
    { key: 'pattern',    label: '차트 패턴',    draw: drawPattern },
]

/** analysis 중 켜진 레이어를 차트에 그린다. 레이어 하나가 실패해도 나머지는 그린다. */
export function drawAnalysis({ chart, candle, analysis, enabled, lastTime }) {
    if (!analysis) return { rsiOn: false }
    const ctx = { chart, candle, lastTime, markers: [], rsiPane: null }
    for (const layer of LAYERS) {
        if (!enabled.includes(layer.key) || analysis[layer.key] == null) continue
        try {
            layer.draw(ctx, analysis[layer.key])
        } catch (e) {
            console.warn(`[chart-analysis] ${layer.key} 그리기 실패`, e)
        }
    }
    if (ctx.markers.length) {
        ctx.markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
        createSeriesMarkers(candle, ctx.markers)
    }
    return { rsiOn: ctx.rsiPane != null }
}
