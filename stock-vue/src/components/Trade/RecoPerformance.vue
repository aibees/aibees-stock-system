<template>
    <div id="reco-performance">
        <Headers :prop_title="title" />

        <div class="contents">

            <section class="head-desc">
                <div class="head-left">
                    <h2>추천 성과 추적</h2>
                    <p class="sub-text">
                        매수추천이 나온 뒤 <b>어디까지 올랐고 어디까지 빠졌는지</b>를 추천 건별로 봅니다.
                        같은 종목이 여러 번 추천됐으면 추천일마다 따로 나옵니다.
                    </p>
                </div>
            </section>

            <!-- ── 조회 조건 ── -->
            <section class="card">
                <div class="run-form">
                    <div class="rf-field">
                        <span>추천 기간</span>
                        <div class="seg">
                            <button v-for="d in [30, 60, 90, 180]" :key="d" type="button"
                                :class="{ on: form.days === d }" @click="form.days = d">{{ d }}일</button>
                        </div>
                    </div>
                    <label class="rf-field">
                        <span>관측 기간</span>
                        <select v-model.number="form.horizon">
                            <option :value="0">추천 후 전체</option>
                            <option :value="5">5거래일</option>
                            <option :value="10">10거래일</option>
                            <option :value="20">20거래일</option>
                            <option :value="60">60거래일</option>
                        </select>
                    </label>
                    <label class="rf-field">
                        <span>변곡점 민감도</span>
                        <select v-model.number="form.zigzag">
                            <option :value="0">사용 안 함</option>
                            <option :value="3">3% (촘촘)</option>
                            <option :value="5">5%</option>
                            <option :value="10">10% (큰 흐름)</option>
                        </select>
                    </label>
                    <button class="btn-run" :disabled="isLoading" @click="fetchData">
                        {{ isLoading ? '계산 중…' : '조회' }}
                    </button>
                </div>
                <p class="run-note">
                    기준가는 <b>추천일 종가</b>입니다. 추천은 장 마감 후 나오므로 관측 구간은
                    <b>다음 거래일부터</b>입니다.
                </p>
            </section>

            <template v-if="result">
                <section v-if="!result.ok" class="card empty-card"><p>{{ result.message }}</p></section>

                <template v-else>
                    <!-- ── 요약 ── -->
                    <section class="card sum-card">
                        <header class="card-head"><h3>요약</h3>
                            <span class="hint-text">추천 {{ result.summary.count }}건 · {{ result.summary.codes }}종목</span>
                        </header>
                        <div class="stat-grid">
                            <div class="stat"><span>평균 최고</span><b class="up">+{{ result.summary.avg_max_high_pct }}%</b></div>
                            <div class="stat"><span>평균 최저</span><b class="down">{{ result.summary.avg_min_low_pct }}%</b></div>
                            <div class="stat"><span>평균 현재</span>
                                <b :class="pnlClass(result.summary.avg_last_pct)">{{ sign(result.summary.avg_last_pct) }}%</b></div>
                            <div class="stat"><span>최고 기록</span><b class="up">+{{ result.summary.best }}%</b></div>
                            <div class="stat"><span>최저 기록</span><b class="down">{{ result.summary.worst }}%</b></div>
                        </div>

                        <div class="hit-row">
                            <span class="hit-label">추천 후 한 번이라도 도달한 비율</span>
                            <div class="hit-bars">
                                <div v-for="h in hitList" :key="h.k" class="hit-item">
                                    <span class="hi-k">+{{ h.k }}%</span>
                                    <div class="hi-bar"><i :style="{ width: h.v + '%' }"></i></div>
                                    <span class="hi-v">{{ h.v }}%</span>
                                </div>
                            </div>
                        </div>
                        <p class="hit-note">
                            익절 목표를 정할 때 참고하세요. 예를 들어 +30% 도달률이 낮다면
                            익절선이 너무 높아 대부분 트레일링/타임스탑으로 나가고 있다는 뜻입니다.
                        </p>
                    </section>

                    <!-- ── 표 ── -->
                    <section class="card">
                        <header class="card-head">
                            <h3>추천 건별</h3>
                            <div class="sort-chips">
                                <button v-for="s in SORTS" :key="s.key" type="button"
                                    :class="['sort-chip', { on: sortKey === s.key }]"
                                    @click="setSort(s.key)">{{ s.label }}</button>
                            </div>
                        </header>

                        <div class="table-wrap">
                            <table class="perf-table">
                                <thead>
                                    <tr>
                                        <th class="tc">추천일</th>
                                        <th>종목</th>
                                        <th class="tr">기준가</th>
                                        <th class="tr">최고</th>
                                        <th class="tc">도달</th>
                                        <th class="tr">최저</th>
                                        <th class="tc">도달</th>
                                        <th class="tr">현재</th>
                                        <th class="tc">봉</th>
                                        <th v-if="form.zigzag > 0" class="tc">변곡</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <template v-for="(r, i) in sortedRows" :key="r.ymd + r.stock_code">
                                        <tr :class="{ open: openKey === r.ymd + r.stock_code }"
                                            @click="toggle(r)">
                                            <td class="tc dt">{{ r.reco_date.slice(5) }}</td>
                                            <td class="name-cell">
                                                <b>{{ r.stock_name }}</b><i>{{ r.stock_code }}</i>
                                            </td>
                                            <td class="tr num">{{ num(r.base_close) }}</td>
                                            <td class="tr num up"><b>+{{ r.max_high_pct }}%</b></td>
                                            <td class="tc sm">{{ r.max_high_date.slice(5) }}<i>{{ r.max_high_bars }}봉</i></td>
                                            <td class="tr num down">{{ r.min_low_pct }}%</td>
                                            <td class="tc sm">{{ r.min_low_date.slice(5) }}<i>{{ r.min_low_bars }}봉</i></td>
                                            <td class="tr num" :class="pnlClass(r.last_pct)">{{ sign(r.last_pct) }}%</td>
                                            <td class="tc num sm">{{ r.observed_bars }}</td>
                                            <td v-if="form.zigzag > 0" class="tc">
                                                <span class="pv-badge" v-if="r.pivot_count">{{ r.pivot_count }}</span>
                                                <span v-else class="sm">-</span>
                                            </td>
                                        </tr>
                                        <!-- 변곡점 상세 -->
                                        <tr v-if="openKey === r.ymd + r.stock_code" class="detail-row">
                                            <td :colspan="form.zigzag > 0 ? 10 : 9">
                                                <div v-if="!r.pivots || !r.pivots.length" class="pv-empty">
                                                    변곡점이 없습니다 (임계 {{ form.zigzag }}% 이상 반전 없음).
                                                </div>
                                                <div v-else class="pv-line">
                                                    <div class="pv-start">
                                                        <span class="pv-date">{{ r.reco_date.slice(5) }}</span>
                                                        <span class="pv-kind base">추천</span>
                                                        <span class="pv-price">{{ num(r.base_close) }}</span>
                                                    </div>
                                                    <template v-for="(p, pi) in r.pivots" :key="pi">
                                                        <span class="pv-arrow">→</span>
                                                        <div class="pv-node" :class="p.kind">
                                                            <span class="pv-date">{{ p.date.slice(5) }}</span>
                                                            <span class="pv-kind" :class="p.kind">
                                                                {{ p.kind === 'high' ? '고점' : '저점' }}
                                                            </span>
                                                            <span class="pv-price">{{ num(p.price) }}</span>
                                                            <span class="pv-pct" :class="pnlClass(p.pct_from_base)">
                                                                {{ sign(p.pct_from_base) }}%
                                                            </span>
                                                        </div>
                                                    </template>
                                                </div>
                                            </td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                        <p class="log-note">
                            행을 누르면 변곡점 흐름이 펼쳐집니다. % 는 모두 추천일 종가 기준입니다.
                        </p>
                    </section>
                </template>
            </template>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('추천 성과');

const form = reactive({ days: 60, horizon: 0, zigzag: 5 });
const result = ref(null);
const isLoading = ref(false);
const openKey = ref('');

const SORTS = [
    { key: 'max_high_pct', label: '최고 상승', dir: 'desc' },
    { key: 'min_low_pct', label: '최대 하락', dir: 'asc' },
    { key: 'last_pct', label: '현재 수익', dir: 'desc' },
    { key: 'reco_date', label: '최근 추천', dir: 'desc' },
];
const sortKey = ref('max_high_pct');
const sortDir = ref('desc');

const setSort = (k) => {
    if (sortKey.value === k) { sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'; return; }
    sortKey.value = k;
    sortDir.value = SORTS.find(s => s.key === k)?.dir ?? 'desc';
};

const sortedRows = computed(() => {
    const rows = result.value?.rows ?? [];
    const k = sortKey.value, desc = sortDir.value === 'desc';
    return [...rows].sort((a, b) => {
        const va = a[k], vb = b[k];
        if (typeof va === 'string') return desc ? vb.localeCompare(va) : va.localeCompare(vb);
        return desc ? vb - va : va - vb;
    });
});

const hitList = computed(() => {
    const s = result.value?.summary ?? {};
    return [5, 10, 20, 30].map(k => ({ k, v: s[`hit_${k}`] ?? 0 }));
});

const toggle = (r) => {
    const key = r.ymd + r.stock_code;
    openKey.value = openKey.value === key ? '' : key;
};

const fetchData = async () => {
    isLoading.value = true;
    openKey.value = '';
    try {
        const { data } = await aibeesApi.get('/api/v1/strategy/reco-performance', {
            params: { days: form.days, horizon: form.horizon, zigzag: form.zigzag },
        });
        result.value = data.data;
    } catch (e) {
        console.error('[RecoPerformance] 조회 실패', e);
        result.value = { ok: false, message: '조회에 실패했습니다.' };
    } finally {
        isLoading.value = false;
    }
};

onMounted(fetchData);

const num = (v) => (v === null || v === undefined ? '-' : Math.round(Number(v)).toLocaleString());
const sign = (v) => (Number(v) > 0 ? '+' : '') + v;
const pnlClass = (v) => (Number(v) > 0 ? 'up' : Number(v) < 0 ? 'down' : '');
</script>

<style scoped>
#reco-performance { min-height: 100vh; background: #f4f6f9; }
.contents { max-width: 1120px; margin: 0 auto; padding: 16px 14px 96px; box-sizing: border-box; }

.head-desc { padding: 8px 4px 16px; }
.head-desc h2 { margin: 0; text-align: start; font-size: 1.25rem; font-weight: 700; color: #1f2329; }
.head-desc .sub-text { margin: 6px 0 0; font-size: 0.85rem; color: #6b7280; line-height: 1.45; }

.card {
    background: #fff; border: 1px solid #e5e9ef; border-radius: 14px;
    padding: 16px; margin-bottom: 14px;
}
.card-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 10px; flex-wrap: wrap; margin-bottom: 12px;
}
.card-head h3 { margin: 0; font-size: 0.98rem; font-weight: 700; color: #1f2329; }
.hint-text { font-size: 0.72rem; color: #adb5bd; }

/* 조회 조건 */
.run-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px; }
.rf-field { display: flex; flex-direction: column; gap: 5px; }
.rf-field > span { font-size: 0.72rem; font-weight: 600; color: #868e96; }
.rf-field select {
    height: 34px; padding: 0 10px; border: 1px solid #dee2e6;
    border-radius: 8px; font-size: 0.8rem; color: #1f2329; background: #fff;
}
.seg { display: flex; gap: 4px; }
.seg button {
    height: 34px; padding: 0 13px; border: 1px solid #dee2e6; border-radius: 8px;
    background: #fff; color: #868e96; font-size: 0.76rem; font-weight: 600; cursor: pointer;
}
.seg button.on { border-color: #1971c2; background: #e7f0fd; color: #1971c2; }

.btn-run {
    height: 34px; padding: 0 22px; margin-left: auto; border: none; border-radius: 8px;
    background: #1971c2; color: #fff; font-size: 0.82rem; font-weight: 700; cursor: pointer;
}
.btn-run:disabled { background: #ced4da; cursor: not-allowed; }
.run-note { margin: 11px 0 0; font-size: 0.72rem; color: #868e96; line-height: 1.5; }

/* 요약 */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 7px; }
.stat { display: flex; flex-direction: column; gap: 3px; padding: 9px 11px; border-radius: 9px; background: #f8f9fb; }
.stat span { font-size: 0.7rem; color: #868e96; }
.stat b { font-size: 0.95rem; color: #1f2329; }

.hit-row { margin-top: 14px; padding-top: 13px; border-top: 1px solid #f1f3f5; }
.hit-label { display: block; margin-bottom: 9px; font-size: 0.74rem; font-weight: 700; color: #495057; }
.hit-bars { display: flex; flex-direction: column; gap: 6px; }
.hit-item { display: flex; align-items: center; gap: 9px; }
.hi-k { width: 42px; font-size: 0.74rem; font-weight: 600; color: #6b7280; text-align: right; }
.hi-bar { flex: 1; height: 15px; background: #f1f3f5; border-radius: 999px; overflow: hidden; }
.hi-bar i { display: block; height: 100%; background: linear-gradient(90deg, #4dabf7, #1971c2); border-radius: 999px; }
.hi-v { width: 46px; font-size: 0.74rem; font-weight: 700; color: #1971c2; }
.hit-note { margin: 10px 0 0; font-size: 0.71rem; color: #868e96; line-height: 1.5; }

/* 정렬 칩 */
.sort-chips { display: flex; gap: 4px; flex-wrap: wrap; }
.sort-chip {
    padding: 5px 11px; border: 1px solid #dee2e6; border-radius: 999px; background: #fff;
    color: #868e96; font-size: 0.74rem; font-weight: 600; cursor: pointer; white-space: nowrap;
}
.sort-chip.on { border-color: #1971c2; background: #e7f0fd; color: #1971c2; }

/* 표 */
.table-wrap { overflow-x: auto; }
.perf-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; white-space: nowrap; }
.perf-table th {
    padding: 8px; background: #f8f9fb; border-bottom: 1px solid #e5e9ef;
    color: #868e96; font-weight: 600; text-align: left;
}
.perf-table tbody tr { cursor: pointer; }
.perf-table tbody tr:hover td { background: #f8fbff; }
.perf-table tbody tr.open td { background: #eef6ff; }
.perf-table td { padding: 9px 8px; border-bottom: 1px solid #f1f3f5; color: #343a40; }
.perf-table .tr { text-align: right; }
.perf-table .tc { text-align: center; }
.perf-table .num { font-variant-numeric: tabular-nums; }
.perf-table .sm { font-size: 0.68rem; color: #868e96; }
.perf-table .sm i { display: block; font-style: normal; font-size: 0.64rem; color: #adb5bd; }
.perf-table .dt { font-size: 0.72rem; color: #6b7280; }

.name-cell b { display: block; font-weight: 600; color: #1f2329; }
.name-cell i { font-style: normal; font-size: 0.68rem; color: #adb5bd; }

.pv-badge {
    display: inline-block; min-width: 18px; padding: 1px 6px; border-radius: 999px;
    background: #e7f0fd; color: #1971c2; font-size: 0.68rem; font-weight: 700;
}

/* 변곡점 상세 */
.detail-row td { background: #f8fbff !important; padding: 12px 10px !important; white-space: normal; }
.pv-empty { font-size: 0.75rem; color: #868e96; }
.pv-line { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
.pv-start, .pv-node {
    display: inline-flex; flex-direction: column; align-items: center; gap: 1px;
    padding: 6px 11px; border-radius: 9px; background: #fff; border: 1px solid #e5e9ef;
}
.pv-node.high { border-color: #ffc9c9; background: #fff5f5; }
.pv-node.low { border-color: #a5d8ff; background: #f1f8ff; }
.pv-date { font-size: 0.66rem; color: #adb5bd; }
.pv-kind { font-size: 0.68rem; font-weight: 700; color: #868e96; }
.pv-kind.high { color: #e03131; }
.pv-kind.low { color: #1971c2; }
.pv-kind.base { color: #495057; }
.pv-price { font-size: 0.76rem; font-weight: 700; color: #1f2329; font-variant-numeric: tabular-nums; }
.pv-pct { font-size: 0.7rem; font-weight: 600; }
.pv-arrow { color: #ced4da; font-size: 0.8rem; }

.up { color: #e03131; }
.down { color: #1971c2; }

.log-note { margin: 10px 0 0; font-size: 0.71rem; color: #868e96; }
.empty-card { text-align: center; color: #868e96; font-size: 0.82rem; padding: 22px 0; }
.empty-card p { margin: 0; }

@media (max-width: 620px) { .btn-run { margin-left: 0; width: 100%; } }
</style>
