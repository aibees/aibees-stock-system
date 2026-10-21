<template>
    <div v-if="sections.length" class="ca-summary">
        <!-- 엘리엇 파동: 후보 해석 목록(누르면 차트에 그 해석을 그린다) + 선택한 해석의 목표·확인·무효 -->
        <section v-if="show('elliott') && waves.length" class="ca-sec">
            <h3>엘리엇 파동</h3>
            <!-- 종합: 해석 라벨이 달라도 다음 움직임(상승/하락)으로 묶어 본다 -->
            <dl v-if="consensus" class="ca-consensus">
                <Row label="해석 종합" :value="consensus.label" :cls="consensusClass"
                    :note="`상승 기대 ${consensus.up_count}개 · 하락 기대 ${consensus.down_count}개`
                        + (consensus.up_share != null ? ` · 상승 비중 ${Math.round(consensus.up_share * 100)}%` : '')
                        + ` · 큰 추세 ${consensus.trend_label}`" />
            </dl>
            <ul class="ca-waves">
                <li v-for="(w, k) in waves" :key="w.title" :class="{ on: k === pickIndex }" @click="emit('pick', k)">
                    <div class="ca-wave-text">
                        <span class="ca-wave-title">{{ w.title }}</span>
                        <span class="ca-wave-meta">
                            {{ k === 0 ? '주요 해석' : `대안 ${k}` }} · {{ w.subtitle }} · 적합도 {{ w.score }}
                            <template v-if="w.bias"> · 다음 <b :class="w.bias === 'up' ? 'up' : 'down'">{{ w.bias === 'up' ? '상승' : '하락' }}</b></template>
                        </span>
                    </div>
                    <svg class="ca-spark" viewBox="0 0 60 20" preserveAspectRatio="none" aria-hidden="true">
                        <polyline :points="spark(w)" fill="none" stroke="currentColor" stroke-width="1.4" />
                    </svg>
                </li>
            </ul>
            <dl v-if="wave">
                <Row label="현재 파동" :value="`${wave.current}파`" :note="wave.points.map(p => p.label).join(' - ')" />
                <Row label="기본 목표" :value="fmt(wave.target.basic)" :note="wave.target.basic_label" />
                <Row label="확장 목표" :value="fmt(wave.target.extended)" :note="wave.target.extended_label" />
                <Row v-if="wave.confirm" label="다음 확인" :value="fmt(wave.confirm.price)" :note="wave.confirm.label" />
                <Row label="해석 무효" :value="fmt(wave.invalid.price)" :note="wave.invalid.label" />
                <Row v-for="x in wave.ratios" :key="x.label" :label="x.label" :value="String(x.value)"
                    :note="wave.scale === 'log' ? '로그 기준' : ''" />
            </dl>
        </section>

        <!-- 추세 구조 + RSI/ATR -->
        <section v-if="show('structure') && a.structure" class="ca-sec">
            <h3>추세 구조</h3>
            <dl>
                <Row label="일봉 구조" :value="a.structure.trend_label" :cls="trendClass(a.structure.trend)" />
                <Row label="직전 고점" :value="fmt(a.structure.resistance.price)" :sub="md(a.structure.resistance.date)" />
                <Row label="직전 저점" :value="fmt(a.structure.support.price)" :sub="md(a.structure.support.date)" />
                <Row v-if="a.structure.pivot" label="구조 전환" :value="fmt(a.structure.pivot.price)" :note="a.structure.pivot.label" />
                <template v-if="show('rsi') && a.rsi">
                    <Row label="RSI(14)" :value="a.rsi.last != null ? a.rsi.last.toFixed(1) : '-'" />
                    <Row label="ATR(14)" :value="fmt(a.rsi.atr)" />
                </template>
            </dl>
        </section>

        <!-- 피보나치 눌림/반등 타점 -->
        <section v-if="show('fib') && a.fib" class="ca-sec">
            <h3>
                <span>피보나치 {{ a.fib.plan.side === 'buy' ? '눌림' : '반등' }}</span>
                <span class="ca-status" :class="statusClass(a.fib.status)">{{ a.fib.status_label }}</span>
            </h3>
            <dl>
                <Row label="기준 파동" :value="`${fmt(a.fib.from.price)} → ${fmt(a.fib.to.price)}`"
                    :note="`${md(a.fib.from.date)} ~ ${md(a.fib.to.date)}`" />
                <Row :label="`${sideLabel(a.fib.plan.side)} 후보 구간`" :value="`${fmt(a.fib.plan.zone[0])} – ${fmt(a.fib.plan.zone[1])}`"
                    note="0.5 – 0.618 되돌림" />
                <PlanRows :plan="a.fib.plan" />
                <Row label="확장 목표" :value="fmt(a.fib.plan.target2)" note="1.272 확장" />
                <Row label="해석 무효" :value="fmt(a.fib.plan.invalid)" :note="`파동 시작점 ${a.fib.plan.side === 'buy' ? '이탈' : '돌파'}`" />
            </dl>
            <ul class="ca-levels">
                <li v-for="lv in a.fib.levels" :key="lv.kind + lv.ratio"><span>{{ lv.ratio }}</span><b>{{ fmt(lv.price) }}</b></li>
            </ul>
        </section>

        <!-- 차트 패턴 -->
        <section v-if="show('pattern') && a.pattern?.length" class="ca-sec">
            <h3>차트 패턴</h3>
            <div v-for="p in a.pattern" :key="p.type" class="ca-pattern">
                <p class="ca-pattern-head">
                    <b>{{ p.label }}</b>
                    <span class="ca-status" :class="statusClass(p.status)">{{ p.status_label }}</span>
                </p>
                <dl>
                    <Row :label="p.type === 'abcd' ? 'D 지점' : '넥라인'" :value="fmt(p.type === 'abcd' ? p.d : p.neckline)" :note="p.trigger" />
                    <PlanRows :plan="p.plan" />
                    <Row v-if="p.plan.invalid != null" label="패턴 무효" :value="fmt(p.plan.invalid)" />
                </dl>
            </div>
        </section>

        <!-- RSI 다이버전스 -->
        <section v-if="show('divergence') && a.divergence?.length" class="ca-sec">
            <h3>RSI 다이버전스</h3>
            <dl>
                <Row v-for="d in [...a.divergence].reverse()" :key="d.kind + d.to.date"
                    :label="d.label" :label-cls="d.bias === 'bull' ? 'up' : 'down'"
                    :value="`${md(d.from.date)} → ${md(d.to.date)}`"
                    :note="`RSI ${d.from.rsi} → ${d.to.rsi}${d.confirmed ? '' : ' · 진행 중'}`" />
            </dl>
        </section>
    </div>
</template>

<script setup>
// /charts/stock 응답의 analysis 를 숫자 목록으로 보여 준다. 레이어 토글(layers)과 같은 ON/OFF 를 따른다.
// 행 하나 = 왼쪽 라벨 · 오른쪽 숫자(줄바꿈 없음) + 아래 줄 설명. 좁은 폭에서도 설명이 숫자 사이로 끼어들지 않게.
const props = defineProps({
    analysis:  { type: Object, default: null },
    layers:    { type: Array, default: () => [] },
    pickIndex: { type: Number, default: 0 },   // 차트에 그린 엘리엇 해석
})
const emit = defineEmits(['pick'])

const a = computed(() => props.analysis || {})
const show = (key) => props.layers.includes(key)
const sections = computed(() => ['elliott', 'structure', 'fib', 'pattern', 'divergence'].filter(k => show(k) && a.value[k] != null))
const waves = computed(() => a.value.elliott?.items || [])
const consensus = computed(() => a.value.elliott?.consensus || null)
const consensusClass = computed(() => ({ '상승 우세': 'up', '하락 우세': 'down' })[consensus.value?.label] || '')
const wave = computed(() => waves.value[props.pickIndex] ?? waves.value[0] ?? null)

// 해석 모양 미리보기: 파동 꼭짓점 + 예상 경로를 60×20 에 맞춘다
const spark = (w) => {
    const ys = [...w.points.map(p => p.price), ...(w.projection || []).filter(p => p.bars > 0).map(p => p.price)]
    const lo = Math.min(...ys), hi = Math.max(...ys)
    const step = 60 / Math.max(ys.length - 1, 1)
    return ys.map((y, i) => `${(i * step).toFixed(1)},${(18 - (hi === lo ? 8 : (y - lo) / (hi - lo) * 16)).toFixed(1)}`).join(' ')
}

const fmt = (v) => (v == null || Number.isNaN(v)) ? '-' : Math.round(v).toLocaleString('ko-KR')
const md = (ymd) => (ymd || '').slice(5).replace('-', '.')
const sideLabel = (side) => side === 'buy' ? '매수' : '매도'
const trendClass = (t) => t === 'up' ? 'up' : t === 'down' ? 'down' : ''
const statusClass = (s) => ({
    'is-live': s === 'in_zone' || s === 'triggered',
    'is-dead': s === 'invalid' || s === 'stopped' || s === 'done',
})

// 한 행: label | value(sub) / note
const Row = (p) => h('div', { class: 'ca-row' }, [
    h('dt', { class: p.labelCls }, p.label),
    h('dd', { class: ['ca-val', p.cls] }, [p.value, p.sub ? h('small', p.sub) : null]),
    p.note ? h('dd', { class: 'ca-note' }, p.note) : null,
])
Row.props = ['label', 'value', 'sub', 'note', 'cls', 'labelCls']

// 진입 · 손절 · 목표 · 손익비 — 피보·패턴 공통
const PlanRows = (p) => {
    const plan = p.plan
    if (!plan) return null
    return [
        h(Row, { label: `${sideLabel(plan.side)} 진입 가정`, value: fmt(plan.entry) }),
        h(Row, { label: '손절 기준', value: fmt(plan.stop), sub: plan.loss_pct != null ? `-${plan.loss_pct}%` : '' }),
        h(Row, { label: '목표', value: fmt(plan.target), sub: plan.gain_pct != null ? `+${plan.gain_pct}%` : '' }),
        h(Row, { label: '손익비', value: plan.rr != null ? `${plan.rr}배` : '-' }),
    ]
}
PlanRows.props = ['plan']
</script>

<style scoped lang="scss">
$line:   #EFE2BC;
$line-2: #F4ECD6;
$ink:    #2B1D14;
$sub:    #6B5B4E;
$sub-2:  #7A6B5D;

.ca-summary {
    margin-top: 16px;
    border-top: 1px solid $line;
    font-size: 13px;
    line-height: 1.45;
    color: $ink;
    font-variant-numeric: tabular-nums;
}

.ca-sec {
    padding: 16px 0 12px;
    border-bottom: 1px solid $line;

    h3 {
        margin: 0 0 6px;
        font-size: 14px;
        font-weight: 700;
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
    }
}

dl { margin: 0; }

// 넓은 화면: 라벨과 숫자가 너무 멀어지지 않게 행을 두 칸으로 흘린다
@media (min-width: 640px) {
    dl {
        display: grid;
        grid-template-columns: 1fr 1fr;
        column-gap: 40px;
    }
}

// 라벨 | 숫자 를 한 줄에 고정하고, 설명은 그 아래 전체 폭으로
:deep(.ca-row) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 12px;
    padding: 6px 0;

    dt {
        color: $sub-2;
        min-width: 0;
    }
    .ca-val {
        margin: 0;
        font-weight: 600;
        text-align: right;
        white-space: nowrap;

        small {
            margin-left: 6px;
            font-size: 12px;
            font-weight: 400;
            color: $sub-2;
        }
    }
    .ca-note {
        grid-column: 1 / -1;
        margin: 2px 0 0;
        font-size: 12px;
        color: $sub-2;
    }
}

// 피보 레벨: "비율 … 가격" 짝을 칸 단위로 정렬
.ca-levels {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(124px, 1fr));
    column-gap: 20px;
    margin: 8px 0 0;
    padding: 8px 0 0;
    border-top: 1px solid $line-2;
    list-style: none;

    li {
        display: flex;
        justify-content: space-between;
        padding: 3px 0;
        font-size: 12px;
        color: $sub-2;
    }
    b { font-weight: 600; color: $sub; }
}

.ca-status {
    flex: none;
    font-size: 12px;
    font-weight: 500;
    color: $sub;
    &.is-live { color: #74462A; font-weight: 700; }
    &.is-dead { color: #A99B8C; }
}

.ca-pattern + .ca-pattern {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid $line-2;
}
.ca-pattern-head {
    margin: 0 0 2px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
}

.ca-consensus { margin-bottom: 4px; grid-template-columns: 1fr; }   // 넓은 화면에서도 한 칸 전체

// 해석 목록: 카드 없이 구분선 행. 제목 / 부가정보 두 줄 + 오른쪽 미니 차트. 선택은 글자색으로만
.ca-waves {
    margin: 0 0 8px;
    padding: 0;
    list-style: none;

    li {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid $line-2;
        color: $sub;
        cursor: pointer;
        &.on { color: #A8458A; .ca-wave-title { font-weight: 700; } }
    }
    .ca-wave-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
        flex: 1;
    }
    .ca-wave-title { color: inherit; font-weight: 600; }
    .ca-wave-meta { font-size: 12px; color: $sub-2; b { font-weight: 600; } }
    .ca-spark { width: 60px; height: 20px; flex: none; }
}

// Row(함수형) 안쪽에도 걸리도록 deep
:deep(.up)   { color: #C8282A; }
:deep(.down) { color: #1F5BD1; }
</style>
