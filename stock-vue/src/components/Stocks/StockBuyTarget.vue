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
                    <label class="sort-btn">
                        <select v-model="sortKey" @change="onSortKeyChange" aria-label="정렬 기준">
                            <option v-for="o in SORT_OPTIONS" :key="o.key" :value="o.key">{{ o.label }}</option>
                        </select>
                        <span class="sort-text" aria-hidden="true">{{ currentSort.label }} ▾</span>
                    </label>
                    <button type="button" class="dir-btn" @click="toggleSortDir"
                        :aria-label="`정렬 방향: ${sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel}`"
                        :title="sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"
                            :style="{ transform: sortDir === 'desc' ? 'rotate(180deg)' : 'none' }" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"></path></svg>
                    </button>
                </div>
            </div>

            <section class="buy-target reco">
                <div v-if="!isLoading && sortedData.length" class="reco-list">
                    <div v-for="(r, idx) in rows" :key="r.item.stock_code ?? idx" class="reco-item">
                        <button type="button" class="reco-row" :class="{ open: expandedCode === r.item.stock_code }"
                            :aria-expanded="expandedCode === r.item.stock_code ? 'true' : 'false'"
                            @click="toggleRow(r.item.stock_code)">
                            <span class="rank">{{ String(rankNumber(idx)).padStart(2, '0') }}</span>
                            <span class="who">
                                <span class="name-line">
                                    <span class="name">{{ r.item.stock_name }}</span>
                                    <span class="code">{{ r.item.stock_code }}</span>
                                </span>
                                <span class="reason">{{ r.reason }}</span>
                            </span>
                            <span class="px">
                                <span class="price">{{ formatNumber(r.item.close) }}</span>
                                <span class="chg" :class="r.chg.cls">{{ r.chg.text }}</span>
                            </span>
                        </button>

                        <div v-if="expandedCode === r.item.stock_code" class="reco-detail">
                            <!-- 시/고/저/종 + 거래량 표 (장중에는 '종가' 대신 '현재가') -->
                            <DayCandle :open="r.item.open" :high="r.item.high" :low="r.item.low" :close="r.item.close"
                                :volume="r.item.volume" :close-label="priceLabel" />
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
import aibeesApi from '@scripts/aibeesApi.js';
import {
    numOrNull, formatNumber, hasValue, changeInfo, reasonLine,
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

const rows = computed(() =>
    sortedData.value.map(item => ({
        item,
        chg: changeInfo(item),
        reason: reasonLine(item),
    })));

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

const buyTargetCandleData = (item) => {
    const rows = item.chart_data || [];
    const toXY = (key) => rows.map(r => ({
        x: (r.date || '').slice(0, 10),
        y: r[key] != null ? Number(r[key]) : null,
    }));

    return {
        labels: rows.map(r => (r.date || '').slice(0, 10)),
        datasets: [
            {
                label: 'Candle',
                data: rows.map(r => ({
                    x: (r.date || '').slice(0, 10),
                    o: Number(r.open), h: Number(r.high), l: Number(r.low), c: Number(r.close),
                })),
                color: { up: '#c51300', down: '#03748d', unchanged: '#999999' },
            },
            { label: 'MA20',  data: toXY('ma20'),  borderColor: '#efa55b', type: 'line', pointRadius: 0 },
            { label: 'MA60',  data: toXY('ma60'),  borderColor: '#8bb400', type: 'line', pointRadius: 0 },
            { label: 'MA120', data: toXY('ma120'), borderColor: '#01b6f3', type: 'line', pointRadius: 0 },
        ],
    };
};

// 카드 내 미니 프리뷰용 — 줌/팬 비활성화, 범례는 커스텀 legend로 대체, 축은 최소화
const miniCandleOptions = {
    plugins: {
        legend: { display: false },
        zoom: {
            pan: { enabled: false },
            zoom: { wheel: { enabled: false }, pinch: { enabled: false } },
        },
    },
    scales: {
        // x축 display:false 를 바로 주면(Chart.js 3.9 + category 스케일) 범위(min/max) 계산 자체가
        // 깨져서 데이터가 거의 안 보이는 버그가 있다 — 축은 켜두고 눈금표시(ticks)만 숨긴다.
        x: { type: 'category', grid: { display: false }, ticks: { display: false } },
        y: { position: 'right', beginAtZero: false, ticks: { font: { size: 9 } } },
    },
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
    background: $bg;
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
.sort-btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    min-height: 40px;
    padding: 0 8px;
    font-size: 14px;
    color: #4A3628;

    select {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        opacity: 0;
        cursor: pointer;
        font-size: 16px;   // iOS 포커스 확대 방지
    }
}
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

/* ── 컴팩트 리스트 ── */
.reco-list {
    background: $card;
    border-radius: 18px;
    box-shadow: 0 1px 0 $line, 0 0 0 1px #F3EAD2;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
.reco-item { border-bottom: 1px solid #F5EEDA; }

.reco-row {
    width: 100%;
    border: 0;
    background: $card;
    padding: 16px;
    display: grid;
    grid-template-columns: 30px minmax(0, 1fr) auto;
    gap: 10px;
    align-items: start;
    text-align: left;
    cursor: pointer;
    color: $ink;
    font-family: inherit;

    &.open { background: #FFFDF5; }

    .rank { font-family: 'Do Hyeon', 'Pretendard', sans-serif; font-size: 20px; color: #A0662F; }
    .who { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .name-line { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 6px; min-width: 0; }
    .name { font-size: 16px; font-weight: 600; max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }
    .code { font-size: 12px; color: $sub-2; flex-shrink: 0; }
    .reason { font-size: 13px; color: $sub; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .px { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
    .price { font-size: 17px; font-weight: 700; }
}

// 등락: 색뿐 아니라 ▲/▼ 기호와 절대값을 함께 쓴다
.chg {
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    &.up   { color: $up; }
    &.down { color: $down; }
    &.flat { color: $sub; }
}

.reco-detail {
    padding: 4px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background: #FFFDF5;
}

.score-line { font-size: 12px; color: $sub; b { color: $ink; } }

// 시/고/저/종 + 거래량 표
.ohlc {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    background: $card;
    border: 1px solid $line;
    border-radius: 10px;
    overflow: hidden;

    th, td { padding: 8px 6px; text-align: right; font-size: 13px; border-bottom: 1px solid #F3EAD2; }
    thead th { font-size: 11px; font-weight: 600; color: $sub; background: #FFFDF5; }
    tbody td { font-weight: 600; }
    td.hi { color: $up; }
    td.lo { color: $down; }
    td.cl { color: $ink; font-weight: 700; }
    tr:last-child th, tr:last-child td { border-bottom: 0; }
    .vol th { font-size: 11px; font-weight: 600; color: $sub; text-align: left; padding-left: 10px; background: #FFFDF5; }
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
    background: $card;
    color: $brown;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}

.skeleton-row { height: 72px; border-bottom: 1px solid #F3EAD2; background: $card; animation: pulse 1.6s infinite ease-in-out; }
.empty-box { text-align: center; padding: 56px 0; color: $sub; font-size: 14px; }

.skeleton-row { height: 72px; border-bottom: 1px solid #F3EAD2; background: $card; animation: pulse 1.6s infinite ease-in-out; }
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
