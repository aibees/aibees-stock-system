<template>
    <div id="chart-stocks">
        <Headers :prop_title="title" />

        <div class="contents">
            <!-- <section class="head-desc">
                <div class="head-left">
                    <h2>주식 차트</h2>
                    <p class="sub-text">캔들스틱 · 이동평균선</p>
                </div>
            </section> -->

            <!-- 검색 카드 -->
            <section class="search-card">
                <div class="search-row">
                    <SAutoInput
                        id="search-code"
                        label="종목"
                        type="text"
                        align="center"
                        v-model:code="searchParam.code"
                        v-model:name="searchParam.name"
                    />
                </div>
                <div class="date-row">
                    <div class="period-group">
                        <button
                            v-for="p in periods" :key="p.value"
                            class="period-btn"
                            :class="{ active: searchParam.period === p.value }"
                            @click="searchParam.period = p.value"
                        >{{ p.label }}</button>
                    </div>
                    <div class="date-field">
                        <span class="date-label">기준일자</span>
                        <input class="date-input" type="date" v-model="searchParam.to" />
                    </div>
                    <button class="search-btn" @click="fetchChart">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                            fill="none" stroke="currentColor" stroke-width="2.2"
                            stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                        </svg>
                        조회
                    </button>
                </div>
            </section>

            <!-- 차트 카드 -->
            <section class="chart-section">
                <div v-if="isLoading" class="chart-skeleton">
                    <div class="loading-bar"></div>
                    <span class="loading-label">차트 데이터를 불러오는 중...</span>
                </div>

                <div v-else-if="chartData" class="chart-card">
                    <div class="chart-header">
                        <div class="stock-title">
                            <span class="stock-name">{{ searchParam.name || searchParam.code }}</span>
                            <span class="stock-code">{{ searchParam.code }}</span>
                        </div>
                        <div class="legend">
                            <span class="leg-item" style="--c:#f38980">MA5</span>
                            <span class="leg-item" style="--c:#efa55b">MA20</span>
                            <span class="leg-item" style="--c:#d0fe48">MA60</span>
                            <span class="leg-item" style="--c:#01b6f3">MA120</span>
                            <span class="leg-item leg-dashed" style="--c:#a78bfa">BB</span>
                            <span class="leg-item leg-bar" style="--c:rgba(100,100,100,0.35)">Vol</span>
                        </div>
                    </div>
                    <div class="chart-scroll">
                        <div class="chart-wrap" :style="{ width: dynamicWidth }">
                            <CandlestickChart :chartData="chartData" :extraOptions="chartOptions" />
                        </div>
                    </div>
                </div>

                <div v-else class="empty-box">
                    <p>종목을 검색하면 차트가 표시됩니다.</p>
                </div>
            </section>
        </div>
    </div>
</template>

<script setup>
import Lnb from '../common/Lnb.vue';
import SAutoInput from '../common/comp/SAutoInput.vue';
import CandlestickChart from '../common/comp/CandlestickChart.vue';
import aibeesApi from '@scripts/aibeesApi.js';

const route = useRoute();
const title = '주식 차트';

const toDateStr = (d) => d.toISOString().slice(0, 10);
const today     = new Date();

const periods = [
    // { label: '1',     value: '1'     },
    // { label: '5',     value: '5'     },
    // { label: '30',    value: '30'    },
    // { label: '60',    value: '60'    },
    { label: 'Day',   value: 'day'   },
    { label: 'Week',  value: 'week'  },
    { label: 'Month', value: 'month' },
];

const searchParam = reactive({
    code:   '',
    name:   '',
    to:     toDateStr(today),
    period: 'day',
});

const chartData    = ref(null);
const chartOptions = ref(null);
const isLoading    = ref(false);
const slicedLength = ref(0);

onMounted(async () => {
    const code = route.query.code || '';
    if (code) {
        searchParam.code = code;
        await setStockInfo(code);
        await fetchChart();
    }
});

const setStockInfo = async (code) => {
    const { data } = await aibeesApi.get('/api/v1/stocks/id/' + code);
    searchParam.code = data.data.stock_code;
    searchParam.name = data.data.stock_name;
};

const fetchChart = async () => {
    if (!searchParam.code) return;
    isLoading.value  = true;
    chartData.value  = null;

    try {
        const params = {
            stock_code: searchParam.code,
            end_date:   searchParam.to,
            period:     searchParam.period,
        }
        const { data } = await aibeesApi.get('/api/v1/charts/stock', { params });

        const all = data.data;

        const volume = all.volume || [];
        const rate   = all.rate   || [];

        // rate를 ohcl 각 항목에 병합 → tooltip에서 context.raw.rate로 접근
        const ohcl = (all.ohcl || []).map((c, i) => ({ ...c, rate: rate[i] ?? null }));
        slicedLength.value = ohcl.length;

        // y2 max를 실제 최대값의 5배로 → 볼륨 바가 하단 20%에만 표시
        const maxVol = Math.max(...volume.map(v => (typeof v === 'object' ? v.y : v) || 0), 1);
        chartOptions.value = {
            scales: {
                y2: {
                    position: 'right',
                    display: false,
                    beginAtZero: true,
                    max: maxVol * 5,
                    grid: { display: false },
                },
            },
        };

        // 상승/하락 기준으로 볼륨 바 색상
        const volColors = ohcl.map(c =>
            c.o <= c.c ? 'rgba(197,19,0,0.25)' : 'rgba(3,116,141,0.25)'
        );

        chartData.value = {
            datasets: [
                {
                    label: 'Candle',
                    data:  ohcl,
                    color: { up: '#c51300', down: '#03748d', unchanged: '#999999' }
                },
                { label: 'MA5',      data: all.ma5      || [], borderColor: '#f38980', type: 'line', pointRadius: 0 },
                { label: 'MA20',     data: all.ma20     || [], borderColor: '#efa55b', type: 'line', pointRadius: 0 },
                { label: 'MA60',     data: all.ma60     || [], borderColor: '#d0fe48', type: 'line', pointRadius: 0 },
                { label: 'MA120',    data: all.ma120    || [], borderColor: '#01b6f3', type: 'line', pointRadius: 0 },
                { label: 'BB Upper', data: all.bb_upper || [], borderColor: '#a78bfa', borderDash: [4, 3], type: 'line', pointRadius: 0 },
                { label: 'BB Mid',   data: all.bb_mid   || [], borderColor: '#818cf8', borderDash: [4, 3], type: 'line', pointRadius: 0 },
                { label: 'BB Lower', data: all.bb_lower || [], borderColor: '#a78bfa', borderDash: [4, 3], type: 'line', pointRadius: 0 },
                {
                    label:           'Volume',
                    data:            volume,
                    type:            'bar',
                    yAxisID:         'y2',
                    backgroundColor: volColors,
                    borderWidth:     0,
                    barPercentage:    0.4,
                    categoryPercentage: 0.5,
                    maxBarThickness: 6,
                },
            ]
        };
    } catch (e) {
        console.error(e);
    } finally {
        isLoading.value = false;
    }
};

const dynamicWidth = computed(() => {
    const px = window.innerWidth < 768 ? 10 : 20;
    return Math.max(slicedLength.value * px, 400) + 'px';
});
</script>

<style scoped lang="scss">
$white:    #ffffff;
$gray-50:  #f8f9fa;
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-400: #909090;
$gray-500: #6b6b6b;
$gray-700: #333333;
$gray-900: #111111;
$blue:     #1971c2;
$navy:     #1c3d6e;

#chart-stocks {
    min-height: 100vh;
    background: $white;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 900px;
    margin: 0 auto;
    padding: 24px 16px 100px;
}

/* ── 헤더 ── */
.head-desc {
    margin-bottom: 16px;

    h2 {
        font-size: 1.3rem;
        font-weight: 700;
        margin: 0;
        color: $gray-900;
    }

    .sub-text {
        font-size: 0.8rem;
        color: $gray-500;
        margin: 3px 0 0;
    }
}

/* ── 검색 카드 ── */
.search-card {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.75rem;
    padding: 14px 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
    margin-bottom: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;

    /* SAutoInput 오버라이드 */
    :deep(.auto-complete-container) { margin: 0; width: 100%; }

    :deep(.search-bar) {
        width: 100% !important;
        box-sizing: border-box;
        margin: 0 !important;
        background: $white;
        border: 1.5px solid $gray-200;
        border-radius: 0.6rem;
        padding: 6px 6px 6px 12px;
        box-shadow: none;
        transition: border-color .15s;

        &:focus-within {
            border-color: $blue;
            box-shadow: 0 0 0 3px rgba(25,113,194,.08);
        }
    }

    :deep(.search-bar .search-icon) { font-size: 0.95rem; margin-right: 8px; }

    :deep(.search-bar input) {
        color: $gray-900;
        font-size: 0.92rem;
        background: transparent;
        &::placeholder { color: $gray-400; }
    }

    :deep(.search-bar .search-btn) {
        background: $navy;
        color: $white;
        border-radius: 0.45rem;
        padding: 8px 16px;
        font-size: 0.85rem;
        font-weight: 700;
        font-family: inherit;
        white-space: nowrap;
        &:hover  { background: $blue; }
        &:active { transform: scale(0.97); }
    }

    :deep(.suggestion-div) {
        background: $white;
        border: 1px solid $gray-200;
        border-radius: 0.6rem;
        box-shadow: 0 8px 24px rgba(0,0,0,.1);
    }

    :deep(.suggestion-header) {
        background: $gray-50;
        border-bottom: 1px solid $gray-100;
        .item { color: $gray-500; font-size: 0.73rem; font-weight: 700; }
    }

    :deep(.list-item) {
        .s_code { color: $gray-400; }
        .s_name { color: $gray-900; }
        .s_type { color: $gray-400; }
        &:hover { background: $gray-50; }
    }
}

/* ── 날짜 행 ── */
.date-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

/* ── Period 버튼 그룹 ── */
.period-group {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
}

.period-btn {
    padding: 6px 11px;
    border: 1.5px solid $gray-200;
    border-radius: 0.45rem;
    background: $white;
    color: $gray-500;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: border-color .12s, background .12s, color .12s;

    &:hover { border-color: $blue; color: $blue; }

    &.active {
        background: $navy;
        border-color: $navy;
        color: $white;
    }
}

.date-field {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 140px;

    .date-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: $gray-500;
        white-space: nowrap;
        min-width: 24px;
    }

    .date-input {
        flex: 1;
        padding: 7px 10px;
        border: 1.5px solid $gray-200;
        border-radius: 0.6rem;
        font-size: 0.85rem;
        font-family: inherit;
        color: $gray-700;
        background: $white;
        outline: none;
        transition: border-color .15s;

        &:focus { border-color: $blue; box-shadow: 0 0 0 3px rgba(25,113,194,.08); }
    }
}

.date-sep {
    font-size: 0.9rem;
    color: $gray-400;
    flex-shrink: 0;
}

.search-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 18px;
    background: $navy;
    color: $white;
    border: none;
    border-radius: 0.6rem;
    font-size: 0.85rem;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    transition: background .15s, transform .1s;
    flex-shrink: 0;

    &:hover  { background: $blue; }
    &:active { transform: scale(0.97); }
}

/* ── 차트 카드 ── */
.chart-card {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.75rem;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);

    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid $gray-100;
        gap: 12px;
        flex-wrap: wrap;

        .stock-title {
            display: flex;
            align-items: baseline;
            gap: 8px;

            .stock-name {
                font-size: 1rem;
                font-weight: 700;
                color: $gray-900;
            }

            .stock-code {
                font-size: 0.75rem;
                color: $gray-500;
            }

        }

        .legend {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        .leg-item {
            font-size: 0.72rem;
            font-weight: 600;
            color: $gray-500;
            display: flex;
            align-items: center;
            gap: 5px;

            &::before {
                content: '';
                display: inline-block;
                width: 18px;
                height: 2px;
                background: var(--c);
                border-radius: 1px;
            }

            &.leg-dashed::before {
                background: none;
                border-top: 2px dashed var(--c);
            }

            &.leg-bar::before {
                width: 10px;
                height: 10px;
                border-radius: 2px;
                background: var(--c);
            }
        }
    }

    .chart-scroll {
        overflow-x: auto;
        padding: 16px;

        &::-webkit-scrollbar         { height: 4px; }
        &::-webkit-scrollbar-track   { background: $gray-50; }
        &::-webkit-scrollbar-thumb   { background: $gray-200; border-radius: 2px; }
    }

    .chart-wrap {
        min-width: 400px;
        height: 62vh;
    }
}

/* ── Loading ── */
.chart-skeleton {
    height: 62vh;
    background: $gray-50;
    border: 1px solid $gray-100;
    border-radius: 0.75rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    overflow: hidden;
    position: relative;
}

.loading-bar {
    width: 220px;
    height: 3px;
    background: $gray-100;
    border-radius: 2px;
    overflow: hidden;

    &::after {
        content: '';
        display: block;
        height: 100%;
        width: 40%;
        background: $navy;
        border-radius: 2px;
        animation: slide 1.2s ease-in-out infinite;
    }
}

.loading-label {
    font-size: 0.8rem;
    color: $gray-400;
}

@keyframes slide {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(650%); }
}

/* ── Empty ── */
.empty-box {
    text-align: center;
    padding: 72px 0;
    color: $gray-500;
    font-size: 0.88rem;
}

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .85; }
}

/* ── 모바일 ── */
@media (max-width: 480px) {
    .date-row    { flex-direction: column; align-items: stretch; }
    .period-group { justify-content: space-between; }
    .period-btn  { flex: 1; text-align: center; }
    .date-field  { min-width: unset; }
    .search-btn  { width: 100%; justify-content: center; }
    .legend      { display: none; }
}
</style>
