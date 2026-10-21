<template>
    <div v-if="sections.length" class="ca-summary">
        <!-- 추세 구조 + RSI/ATR -->
        <section v-if="show('structure') && a.structure" class="ca-sec">
            <h3>추세 구조</h3>
            <dl>
                <div><dt>일봉 구조</dt><dd :class="trendClass(a.structure.trend)">{{ a.structure.trend_label }}</dd></div>
                <div><dt>직전 고점</dt><dd>{{ fmt(a.structure.resistance.price) }} <small>{{ md(a.structure.resistance.date) }}</small></dd></div>
                <div><dt>직전 저점</dt><dd>{{ fmt(a.structure.support.price) }} <small>{{ md(a.structure.support.date) }}</small></dd></div>
                <div v-if="a.structure.pivot"><dt>구조 전환</dt><dd>{{ fmt(a.structure.pivot.price) }} <small>{{ a.structure.pivot.label }}</small></dd></div>
                <div v-if="show('rsi') && a.rsi"><dt>RSI(14) · ATR(14)</dt><dd>{{ a.rsi.last ?? '-' }} · {{ fmt(a.rsi.atr) }}</dd></div>
            </dl>
        </section>

        <!-- 피보나치 눌림/반등 타점 -->
        <section v-if="show('fib') && a.fib" class="ca-sec">
            <h3>피보나치 {{ a.fib.plan.side === 'buy' ? '눌림' : '반등' }}
                <span class="ca-status" :class="statusClass(a.fib.status)">{{ a.fib.status_label }}</span>
            </h3>
            <dl>
                <div><dt>기준 파동</dt><dd>{{ fmt(a.fib.from.price) }} → {{ fmt(a.fib.to.price) }} <small>{{ md(a.fib.from.date) }} ~ {{ md(a.fib.to.date) }}</small></dd></div>
                <div><dt>{{ sideLabel(a.fib.plan.side) }} 후보 구간</dt><dd>{{ fmt(a.fib.plan.zone[0]) }} – {{ fmt(a.fib.plan.zone[1]) }} <small>0.5–0.618</small></dd></div>
                <PlanRows :plan="a.fib.plan" />
                <div><dt>확장 목표</dt><dd>{{ fmt(a.fib.plan.target2) }} <small>1.272</small></dd></div>
                <div><dt>해석 무효</dt><dd>{{ fmt(a.fib.plan.invalid) }} <small>파동 시작점 {{ a.fib.plan.side === 'buy' ? '이탈' : '돌파' }}</small></dd></div>
                <div class="ca-levels"><dt>레벨</dt><dd>
                    <span v-for="lv in a.fib.levels" :key="lv.kind + lv.ratio">{{ lv.ratio }} {{ fmt(lv.price) }}</span>
                </dd></div>
            </dl>
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
                    <div><dt>{{ p.type === 'abcd' ? 'D 지점' : '넥라인' }}</dt><dd>{{ fmt(p.type === 'abcd' ? p.d : p.neckline) }} <small>{{ p.trigger }}</small></dd></div>
                    <PlanRows :plan="p.plan" />
                    <div v-if="p.plan.invalid != null"><dt>패턴 무효</dt><dd>{{ fmt(p.plan.invalid) }}</dd></div>
                </dl>
            </div>
        </section>

        <!-- RSI 다이버전스 -->
        <section v-if="show('divergence') && a.divergence?.length" class="ca-sec">
            <h3>RSI 다이버전스</h3>
            <dl>
                <div v-for="d in [...a.divergence].reverse()" :key="d.kind + d.to.date">
                    <dt :class="d.bias === 'bull' ? 'up' : 'down'">{{ d.label }}</dt>
                    <dd>{{ md(d.from.date) }} → {{ md(d.to.date) }} <small>RSI {{ d.from.rsi }} → {{ d.to.rsi }}{{ d.confirmed ? '' : ' · 진행 중' }}</small></dd>
                </div>
            </dl>
        </section>
    </div>
</template>

<script setup>
// /charts/stock 응답의 analysis 를 숫자 목록으로 보여 준다. 레이어 토글(layers)과 같은 ON/OFF 를 따른다.
const props = defineProps({
    analysis: { type: Object, default: null },
    layers:   { type: Array, default: () => [] },
})

const a = computed(() => props.analysis || {})
const show = (key) => props.layers.includes(key)
const sections = computed(() => ['structure', 'fib', 'pattern', 'divergence'].filter(k => show(k) && a.value[k] != null))

const fmt = (v) => (v == null || Number.isNaN(v)) ? '-' : Math.round(v).toLocaleString('ko-KR')
const md = (ymd) => (ymd || '').slice(5).replace('-', '.')
const sideLabel = (side) => side === 'buy' ? '매수' : '매도'
const trendClass = (t) => t === 'up' ? 'up' : t === 'down' ? 'down' : ''
const statusClass = (s) => ({
    'is-live': s === 'in_zone' || s === 'triggered',
    'is-dead': s === 'invalid' || s === 'stopped' || s === 'done',
})

// 진입 · 손절 · 목표 · 손익비 — 피보·패턴 공통
const PlanRows = (p) => {
    const plan = p.plan
    if (!plan) return null
    const side = sideLabel(plan.side)
    const row = (dt, dd, small) => h('div', [h('dt', dt), h('dd', [dd, small ? h('small', ' ' + small) : null])])
    return [
        row(`${side} 진입 가정`, fmt(plan.entry)),
        row('손절 기준', fmt(plan.stop), plan.loss_pct != null ? `-${plan.loss_pct}%` : ''),
        row('목표', fmt(plan.target), plan.gain_pct != null ? `+${plan.gain_pct}%` : ''),
        row('손익비', plan.rr != null ? `${plan.rr}배` : '-'),
    ]
}
PlanRows.props = ['plan']
</script>

<style scoped lang="scss">
$line: #EFE2BC;
$ink:  #2B1D14;
$sub:  #6B5B4E;
$sub-2:#7A6B5D;

.ca-summary {
    margin-top: 16px;
    border-top: 1px solid $line;
    font-size: 13px;
    color: $ink;
    font-variant-numeric: tabular-nums;
}

.ca-sec {
    padding: 14px 0;
    border-bottom: 1px solid $line;

    h3 {
        margin: 0 0 8px;
        font-size: 14px;
        font-weight: 700;
        display: flex;
        align-items: baseline;
        gap: 8px;
    }
}

dl { margin: 0; }
dl > div {
    display: flex;
    gap: 12px;
    padding: 3px 0;
}
dt {
    flex: 0 0 120px;
    color: $sub-2;
}
dd {
    margin: 0;
    font-weight: 600;
    small { font-weight: 400; color: $sub-2; margin-left: 4px; }
}

.ca-levels dd {
    display: flex;
    flex-wrap: wrap;
    column-gap: 12px;
    font-weight: 400;
    color: $sub;
}

.ca-status {
    font-size: 12px;
    font-weight: 500;
    color: $sub;
    &.is-live { color: #74462A; font-weight: 700; }
    &.is-dead { color: #A99B8C; }
}

.ca-pattern + .ca-pattern { margin-top: 10px; }
.ca-pattern-head {
    margin: 0 0 4px;
    display: flex;
    align-items: baseline;
    gap: 8px;
}

.up   { color: #C8282A; }
.down { color: #1F5BD1; }

@media (max-width: 480px) {
    dt { flex-basis: 96px; }
}
</style>
