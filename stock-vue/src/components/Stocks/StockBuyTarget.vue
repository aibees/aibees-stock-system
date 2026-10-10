<template>
    <div id="stock-buy-target">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">
            <section class="head-desc">
                <div class="head-actions">
                    <div class="date-picker-trigger" @click="openDatePicker">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="16" y1="2" x2="16" y2="6"></line>
                            <line x1="8" y1="2" x2="8" y2="6"></line>
                            <line x1="3" y1="10" x2="21" y2="10"></line>
                        </svg>
                        <span class="date-value">{{ dateLabel }}</span>
                        <input type="date" ref="dateInput" class="hidden-input" v-model="selectedDate"
                            @change="handleDateChange" />
                    </div>
                </div>
            </section>

            <!-- ── 정렬 (홈과 동일: 기준 select + 방향 버튼) ── -->
            <div v-if="!isLoading && resultData.length > 0" class="list-head">
                <h2>추천 종목 <span class="count">{{ sortedData.length }}</span></h2>
                <div class="list-tools">
                    <button type="button" class="dir-btn" @click="toggleSortDir"
                        :aria-label="`정렬 방향: ${sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel}`"
                        :title="sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"
                            :style="{ transform: sortDir === 'desc' ? 'rotate(180deg)' : 'none' }" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"></path></svg>
                    </button>
                </div>
            </div>
            <!-- 정렬 기준: 가로로 넘기는 칩(방향은 위 ↑ 버튼) -->
            <SortChips v-if="!isLoading && resultData.length > 0" v-model="sortKey" :options="SORT_OPTIONS" @change="onSortKeyChange" />

            <section class="buy-target reco">
                <!-- 열 머리글: 아래 줄과 같은 칸 나눔(종목 | 7개 조건 | 현재가 | 봉) -->
                <div v-if="!isLoading && sortedData.length" class="reco-cols" aria-hidden="true">
                    <span class="c-who"></span>
                    <span class="c-conds">
                        <span v-for="c in CONDITION_COLUMNS" :key="c.label" class="c-head">{{ c.head }}</span>
                    </span>
                    <span class="c-px">{{ priceLabel }}</span>
                    <span class="c-candle"></span>
                </div>

                <div v-if="!isLoading && sortedData.length" class="reco-list">
                    <div v-for="(r, idx) in rows" :key="r.item.stock_code ?? idx" class="reco-item">
                        <button type="button" class="reco-row" :class="{ open: expandedCode === r.item.stock_code }"
                            :aria-expanded="expandedCode === r.item.stock_code ? 'true' : 'false'"
                            @click="toggleRow(r.item.stock_code)">
                            <span class="who">
                                <span class="name-line">
                                    <span class="rank">{{ String(rankNumber(idx)).padStart(2, '0') }}</span>
                                    <span class="name">{{ r.item.stock_name }}</span>
                                </span>
                                <span class="code">{{ r.item.stock_code }}</span>
                            </span>
                            <!-- 7개 조건 충족 여부 — 열 머리글과 같은 순서 -->
                            <span class="conds" :aria-label="`조건 ${r.summary.pass}/${r.summary.total} 충족`">
                                <span v-for="c in r.summary.rows" :key="c.key" class="cond" :class="{ on: c.pass }"
                                    :title="`${c.label}: ${c.pass ? '충족' : '미충족'}`">{{ c.pass ? '✓' : '–' }}</span>
                            </span>
                            <span class="px">
                                <span class="price">{{ formatNumber(r.item.close) }}</span>
                                <span class="chg" :class="r.chg.cls">
                                    <span class="chg-full">{{ r.chg.text }}</span>
                                    <span class="chg-short">{{ r.chgShort }}</span>
                                </span>
                            </span>
                            <DayCandle mini class="candle" :open="r.item.open" :high="r.item.high" :low="r.item.low"
                                :close="r.item.close" :close-label="priceLabel" />
                        </button>

                        <div v-if="expandedCode === r.item.stock_code" class="reco-detail">
                            <!-- 조건 목록(홈과 같은 모양): 거래량 두 줄은 실제 수치 -->
                            <ul class="cs-list">
                                <li v-for="c in r.summary.rows" :key="c.key" class="cs-row" :class="{ off: !c.pass }">
                                    <span class="cs-mark" aria-hidden="true">{{ c.pass ? '✓' : '–' }}</span>
                                    <span class="cs-label">{{ c.label }}</span>
                                    <span class="cs-value">{{ c.value }}</span>
                                </li>
                            </ul>
                            <!-- 점수가 아직 없으면(장 마감 후 산출) 칸 자체를 숨긴다 -->
                            <div v-if="hasValue(r.item.score)" class="score-line">종합 점수 <b>{{ numOrNull(r.item.score) }}</b> / 100</div>

                            <div class="rd-actions">
                                <button type="button" class="btn-outline strong" @click="goToStockInfo(r.item.stock_code, r.item.stock_name)">AI 분석</button>
                                <button type="button" class="btn-outline" @click="toggleChart(r.item.stock_code)">
                                    {{ expandedCharts.has(r.item.stock_code) ? '차트 접기' : '차트' }}
                                </button>
                            </div>

                            <!-- 간이 차트: 최근 120영업일 봉차트 + 20/60/120일선 -->
                            <div v-if="expandedCharts.has(r.item.stock_code) && r.item.chart_data && r.item.chart_data.length" class="mini-chart">
                                <div class="mini-chart-head">
                                    <div class="mini-legend">
                                        <span class="leg-item" style="--c:#efa55b">MA20</span>
                                        <span class="leg-item" style="--c:#8bb400">MA60</span>
                                        <span class="leg-item" style="--c:#01b6f3">MA120</span>
                                    </div>
                                    <button type="button" class="mini-chart-detail" @click="goToChart(r.item.stock_code)">자세히보기 ›</button>
                                </div>
                                <div class="mini-chart-canvas">
                                    <CandlestickChart :chartData="buyTargetCandleData(r.item)" :extraOptions="miniCandleOptions" />
                                </div>
                            </div>
                        </div>
                    </div>

                </div>

                <div v-else-if="isLoading" class="reco-list">
                    <div class="skeleton-row" v-for="n in 4" :key="n"></div>
                </div>

                <div v-else class="empty-box">
                    <p>분석된 데이터가 없습니다. 날짜를 변경해 보세요.</p>
                </div>
            </section>
        </div>
    </div>
</template>

<script setup>
import CandlestickChart from '../common/comp/CandlestickChart.vue';
import { buyTargetCandleData, miniCandleOptions } from '@scripts/miniCandle.js';
import aibeesApi from '@scripts/aibeesApi.js';
import {
    numOrNull, formatNumber, hasValue, changeInfo, conditionSummary, CONDITION_COLUMNS,
    kstNowParts, isMarketOpenNow, weekdayKo, toYmdString, getLatestBatchDate,
} from '@scripts/stockSignals.js';

const router = useRouter();
const title = ref('매수추천');

const goToStockInfo = (stock_code, stock_name) => {
    // ymd: 상세 화면이 같은 날짜의 매수타겟 행(근거·재무·조건)을 찾는 데 쓴다.
    router.push({ path: '/stock/info', query: { stock_code, stock_name, ymd: selectedDate.value.replaceAll('-', '') } });
};
const goToChart = (stock_code) => {
    router.push({ path: '/stock/chart', query: { code: stock_code } });
};
const resultData = ref([]);
const isLoading = ref(true);

/* ── 기준일: 가장 최신 배치 데이터가 있는 날(KST) / 장중 여부는 홈과 같은 규칙 ── */
const nowKst = ref(kstNowParts());
let clock = null;
const selectedDate = ref(getLatestBatchDate());
const dateInput = ref(null);

const todayDash = computed(() => toYmdString(nowKst.value.year, nowKst.value.month, nowKst.value.day));
const marketState = computed(() =>
    selectedDate.value === todayDash.value && isMarketOpenNow(nowKst.value) ? 'live' : 'closed');
const priceLabel = computed(() => (marketState.value === 'live' ? '현재가' : '종가'));
const dateLabel = computed(() => {
    const [y, m, d] = selectedDate.value.split('-');
    return `${y}.${m}.${d} (${weekdayKo(selectedDate.value)})`;
});

onMounted(async () => {
    clock = setInterval(() => { nowKst.value = kstNowParts(); }, 30 * 1000);
    await getStockMainData();
});
onBeforeUnmount(() => clearInterval(clock));

const getStockMainData = async () => {
    isLoading.value = true;
    try {
        const searchParam = { 'ymd': selectedDate.value.replaceAll('-', '') };
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target', { params: searchParam });

        if (data.data.length == 0) {
            resultData.value = [];
        } else {
            resultData.value = data.data;
        }
    } catch (e) {
        console.error(e);
    }
    finally {
        isLoading.value = false;
    }
};

const handleDateChange = () => getStockMainData();
const openDatePicker = () => dateInput.value?.showPicker();

/* ══════════════ 매수타겟 정렬 ══════════════
 * 조회는 하루치 전체를 한 번에 받아오므로 클라이언트에서 정렬한다(재조회 없음).
 *
 * 규칙은 worker(trade_worker/repository.py _ORDER_FIELDS)와 맞춘다:
 *   · 필드별 기본 방향 — rank_no 는 작을수록 상위(asc), score/volume 은 클수록 상위(desc)
 *   · 값이 없는(null) 종목은 정렬 방향과 무관하게 항상 뒤
 *   · 전부 동점이면 stock_code 로 최종 결정 (매 조회마다 순서가 흔들리지 않도록)
 */
const SORT_OPTIONS = [
    { key: 'composite_rank_no', label: '종합 순위(신규)', dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'rank_no',     label: '추천순위',     dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'score',       label: '점수',         dir: 'desc', ascLabel: '낮은 점수 먼저', descLabel: '높은 점수 먼저' },
    { key: 'volume',      label: '거래량',       dir: 'desc', ascLabel: '적은 순',        descLabel: '많은 순' },
    { key: 'shape_proba', label: '급등패턴 순위', dir: 'desc', ascLabel: '낮은 확률 먼저', descLabel: '높은 확률 먼저' },
];

// 2026-09 세션 후속: watch 게이트와 병행하는 2단계(top10→모멘텀 재정렬) 방식이 실전
// 시뮬레이션에서 재현성 있게 우수해 기본 정렬을 composite_rank_no 로 승격.
const sortKey = ref('composite_rank_no');
const sortDir = ref('asc');

const currentSort = computed(
    () => SORT_OPTIONS.find(o => o.key === sortKey.value) ?? SORT_OPTIONS[0]);

// select 의 v-model 이 sortKey 를 이미 바꿔 놓은 뒤에 불린다. 기준을 바꾸면 그 필드의 기본 방향으로 되돌린다.
// (거래량을 고르고 '적은 순'이 남아 있으면 의도와 반대 결과가 나온다)
const onSortKeyChange = () => {
    sortDir.value = SORT_OPTIONS.find(o => o.key === sortKey.value)?.dir ?? 'desc';
};
const toggleSortDir = () => { sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'; };

// 카드 번호: 정렬 기준의 "기본 방향"일 때만 1위부터 매기고, 방향을 뒤집으면
// 목록을 새로 매기는 게 아니라 같은 순위를 거꾸로 보여준다(마지막 번호부터 역순).
const rankNumber = (index) => (
    sortDir.value === currentSort.value.dir ? index + 1 : sortedData.value.length - index
);

const sortNum = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
};

const sortedData = computed(() => {
    const key = sortKey.value;
    const desc = sortDir.value === 'desc';
    return [...resultData.value].sort((a, b) => {
        const va = sortNum(a[key]);
        const vb = sortNum(b[key]);
        if (va === null && vb === null) return 0;
        if (va === null) return 1;      // null 은 방향 무관 항상 뒤
        if (vb === null) return -1;
        if (va !== vb) return desc ? vb - va : va - vb;
        return String(a.stock_code ?? '').localeCompare(String(b.stock_code ?? ''));
    });
});

// 좁은 화면용 등락: 기호 + 퍼센트만(절대값은 PC 폭에서만 보인다)
const shortChange = (chg) => {
    if (chg.pct === null) return '';
    const mark = chg.dir > 0 ? '▲' : (chg.dir < 0 ? '▼' : '–');
    return `${mark}${Math.abs(chg.pct).toFixed(2)}%`;
};

const rows = computed(() =>
    sortedData.value.map(item => {
        const chg = changeInfo(item);
        return { item, chg, chgShort: shortChange(chg), summary: conditionSummary(item) };
    }));

/* ── 아코디언: 한 번에 하나만 펼침 ── */
const expandedCode = ref(null);
const toggleRow = (code) => { expandedCode.value = expandedCode.value === code ? null : code; };
watch([sortKey, sortDir, selectedDate], () => { expandedCode.value = null; });

/* ── 매수타겟 카드 간이차트 (최근 120영업일 봉차트 + 5/20/60/120일선) ──
 * 기본 숨김 — "차트보기" 버튼으로 종목별 개별 토글. ChartStock.vue(전체 차트 페이지)와
 * 동일한 CandlestickChart 컴포넌트·색상 배색을 재사용해 일관성을 맞춘다.
 */
const expandedCharts = ref(new Set());
const toggleChart = (code) => {
    const next = new Set(expandedCharts.value);
    next.has(code) ? next.delete(code) : next.add(code);
    expandedCharts.value = next;
};

</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰 (홈과 동일)
$bg:       #FFFBEA;
$card:     #FFFFFF;
$line:     #EFE2BC;
$line-2:   #EAD9A6;
$brown:    #7A4423;
$ink:      #2B1D14;
$sub:      #6B5B4E;
$sub-2:    #7A6B5D;
$up:       #C8282A;
$down:     #1F5BD1;
$amber:    #A0662F;
$gray-700: #5C3118;
$gray-300: #EAD9A6;
$white:    #fff;
$blue:     #7A4423;

#stock-buy-target {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 720px;
    margin: 0 auto;
    padding: 16px 16px 24px;
}

.head-desc { display: flex; margin-bottom: 12px; }
/* ── Head Actions ── */
.head-actions {
    display: flex;
    align-items: center;
    gap: 10px;

    @media (max-width: 600px) {
        width: 100%;
    }
}

/* ── Date Picker ── */
.date-picker-trigger {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0 14px;
    min-height: 44px;
    border-radius: 14px;
    border: 1px solid $gray-300;
    background: $white;
    color: $gray-700;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: border-color .15s;

    &:hover { border-color: $blue; }

    .date-value { color: $blue; }

    .hidden-input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
    }
}

/* ── 정렬 (홈과 동일) ── */
.list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    h2 { margin: 0; font-size: 18px; font-weight: 700; }
    .count { color: $amber; }
}
.list-tools { display: flex; align-items: center; gap: 4px; }
.dir-btn {
    width: 40px;
    height: 40px;
    border: 0;
    border-radius: 20px;
    background: #F6EBC8;
    color: #5C3118;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

/* ── 컴팩트 리스트: 카드 없이 페이지 배경 위에 구분선으로만 나열 (홈과 동일) ── */
.reco-list {
    border-top: 1px solid $line;
    display: flex;
    flex-direction: column;
}
.reco-item { border-bottom: 1px solid $line; }

/* 줄 칸 나눔: 종목 | 7개 조건 | 현재가 | 작은 봉. 머리글(.reco-cols)도 같은 값을 쓴다. */
.reco {
    --cond-w: 22px;          // 조건 한 칸
    --px-w: 60px;            // 현재가 칸(좁은 화면: 등락은 퍼센트만)
    --candle-w: 10px;
    --gap: 6px;
    @media (min-width: 640px) {
        --cond-w: 40px;
        --px-w: 116px;       // 넓은 화면: 등락 절대값까지
        --gap: 14px;
    }
}
.reco-row, .reco-cols {
    display: grid;
    grid-template-columns: minmax(0, 1fr) calc(var(--cond-w) * 7) var(--px-w) var(--candle-w);
    column-gap: var(--gap);
    align-items: center;
}

.reco-cols {
    padding: 0 0 6px;
    font-size: 9px;
    font-weight: 600;
    color: $sub;
    .c-conds { display: grid; grid-template-columns: repeat(7, var(--cond-w)); }
    .c-head { text-align: center; white-space: nowrap; letter-spacing: -.5px; }
    .c-px { text-align: right; }
    @media (min-width: 640px) { font-size: 12px; }
}

.reco-row {
    width: 100%;
    border: 0;
    background: transparent;
    padding: 14px 0;
    text-align: left;
    cursor: pointer;
    color: $ink;
    font-family: inherit;

    .rank { font-family: 'Do Hyeon', 'Pretendard', sans-serif; font-size: 17px; line-height: 1; color: #A0662F; flex-shrink: 0; }
    .who { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .name-line { display: flex; align-items: baseline; gap: 5px; min-width: 0; }    // 순위는 종목명 줄 안에
    // 좁은 칸이라 자르지 않고 최대 두 줄로 감싼다(한글 종목명은 띄어쓰기가 없어 글자 단위로 넘긴다)
    .name {
        font-size: 14px;
        font-weight: 600;
        line-height: 1.3;
        letter-spacing: -.2px;
        min-width: 0;
        overflow-wrap: anywhere;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .code { font-size: 11px; color: $sub-2; }

    .conds { display: grid; grid-template-columns: repeat(7, var(--cond-w)); }
    .cond {
        text-align: center;
        font-size: 13px;
        font-weight: 700;
        line-height: 1;
        color: #C9BCA8;              // 미충족: 옅은 –
        &.on { color: $up; }         // 충족: ✓
    }

    .px { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; min-width: 0; }
    .price { font-size: 15px; font-weight: 700; }
    .candle { justify-self: end; }
}

// 등락: 색뿐 아니라 ▲/▼ 기호를 함께 쓴다(넓은 화면은 절대값까지)
.chg {
    font-size: 12px;
    .chg-full { display: none; }
    @media (min-width: 640px) {
        font-size: 13px;
        .chg-full { display: inline; }
        .chg-short { display: none; }
    }
    font-weight: 600;
    white-space: nowrap;
    &.up   { color: $up; }
    &.down { color: $down; }
    &.flat { color: $sub; }
}

.reco-detail {
    padding: 0 0 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.score-line { font-size: 12px; color: $sub; b { color: $ink; } }

// 조건 목록 (홈과 같은 모양)
.cs-list { margin: 0; padding: 0; list-style: none; border-top: 1px solid $line; }
.cs-row {
    display: grid;
    grid-template-columns: 16px auto minmax(0, 1fr);
    align-items: baseline;
    column-gap: 6px;
    padding: 9px 0;
    border-bottom: 1px solid $line;
    font-size: 13px;

    .cs-mark { font-weight: 700; color: $up; }
    .cs-label { font-weight: 600; color: $ink; white-space: nowrap; }
    .cs-value {
        justify-self: end;
        text-align: right;
        font-size: 12px;
        color: $ink;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
    &.off { .cs-mark, .cs-label, .cs-value { color: $sub; font-weight: 400; } }
}

.rd-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.btn-outline {
    min-height: 44px;
    border-radius: 10px;
    border: 1px solid #E3D3A8;
    background: transparent;
    color: #4A3628;
    font-size: 14px;
    cursor: pointer;
    font-family: inherit;

    &.strong { border: 1.5px solid $brown; color: $brown; font-weight: 600; }
}

.more-btn {
    min-height: 52px;
    border: 0;
    background: transparent;
    color: $brown;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}

.skeleton-row { height: 72px; border-bottom: 1px solid $line; background: rgba(239, 226, 188, .35); animation: pulse 1.6s infinite ease-in-out; }
.empty-box { text-align: center; padding: 56px 0; color: $sub; font-size: 14px; }

/* ── 간이 차트 ── */
.mini-chart {
    width: 100%;
    box-sizing: border-box;

    .mini-chart-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
    .mini-legend { display: flex; gap: 8px; flex-wrap: wrap; }
    .leg-item {
        font-size: 11px;
        font-weight: 600;
        color: $sub;
        display: flex;
        align-items: center;
        gap: 3px;
        &::before { content: ''; display: inline-block; width: 10px; height: 2px; background: var(--c); }
    }
    .mini-chart-detail {
        flex-shrink: 0;
        min-height: 32px;
        padding: 0 10px;
        border: 1px solid #E3D3A8;
        border-radius: 8px;
        background: $card;
        color: $brown;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .mini-chart-canvas { width: 100%; height: 220px; }
}

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .9; }
}
</style>
