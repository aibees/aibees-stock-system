<template>
    <div id="chart-stocks">
        <BrandHeader :title="title" />

        <div class="contents">
            <!-- <section class="head-desc">
                <div class="head-left">
                    <h2>주식 차트</h2>
                    <p class="sub-text">캔들스틱 · 이동평균선</p>
                </div>
            </section> -->

            <!-- 검색 영역 (카드 없음) -->
            <section class="search-card">
                <div class="search-row">
                    <SAutoInput
                        id="search-code"
                        label="종목"
                        type="text"
                        align="center"
                        v-model:code="searchParam.code"
                        v-model:name="searchParam.name"
                        hide-search-btn
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
                        <input class="date-input" type="date" aria-label="기준일자" v-model="searchParam.to" />
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

            <!-- 차트 영역 (카드 없음) -->
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
                            <span class="leg-item" style="--c:#8bb400">MA60</span>
                            <span class="leg-item" style="--c:#01b6f3">MA120</span>
                            <span class="leg-item leg-dashed" style="--c:#a78bfa">BB</span>
                            <span class="leg-item leg-bar" style="--c:rgba(100,100,100,0.35)">Vol</span>
                        </div>
                    </div>
                    <!-- 시가총액(상장주식수 × 직전 영업일 종가) + 같은 날 투자자별 순매수. 순매수=빨강, 순매도=파랑 -->
                    <dl v-if="summary" class="stock-summary">
                        <div v-if="summary.marketCap != null">
                            <dt>시가총액</dt>
                            <dd>{{ formatEok(summary.marketCap) }}</dd>
                        </div>
                        <template v-if="summary.investor">
                            <div v-for="row in summary.investor.rows" :key="row.label">
                                <dt>{{ row.label }}</dt>
                                <dd :class="signClass(row.amt)">{{ formatNetAmt(row.amt) }}</dd>
                            </div>
                        </template>
                        <p v-if="summary.investor" class="summary-note">{{ summary.investor.dateLabel }} 종가·순매수 기준</p>
                    </dl>
                    <div class="chart-scroll" ref="chartScroll">
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
    // label 은 화면 표기, value 는 API 파라미터(/api/v1/charts/stock 의 period)라 바꾸지 않는다.
    { label: '일', value: 'day'   },
    { label: '주', value: 'week'  },
    { label: '월', value: 'month' },
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
const windowWidth  = ref(window.innerWidth);

const onResize = () => { windowWidth.value = window.innerWidth; };

onMounted(async () => {
    window.addEventListener('resize', onResize);

    const code = route.query.code || '';
    if (code) {
        searchParam.code = code;
        await setStockInfo(code);
        await fetchChart();
    }
});

onBeforeUnmount(() => {
    window.removeEventListener('resize', onResize);
});

const setStockInfo = async (code) => {
    const { data } = await aibeesApi.get('/api/v1/stocks/id/' + code);
    searchParam.code = data.data.stock_code;
    searchParam.name = data.data.stock_name;
    setSummary(data.data);
};

// ── 시가총액 · 전일 수급 ─────────────────────────────────────────────
// /stocks/id 응답: market_cap(억원, API 가 상장주식수 × investor.close_price 로 계산),
//                  investor{ ymd, close_price, prsn_amt, frgn_amt, orgn_amt(백만원) } — 배치가 매일 07:00/07:10 갱신
const summary = ref(null);

const setSummary = (d) => {
    if (!d) { summary.value = null; return; }
    const inv = d.investor;
    summary.value = {
        code: d.stock_code,
        marketCap: d.market_cap ?? null,
        investor: inv ? {
            dateLabel: `${Number(inv.ymd.slice(4, 6))}/${Number(inv.ymd.slice(6, 8))}`,
            rows: [
                { label: '외국인', amt: inv.frgn_amt },
                { label: '기관',   amt: inv.orgn_amt },
                { label: '개인',   amt: inv.prsn_amt },
            ].filter(r => r.amt != null),
        } : null,
    };
    if (summary.value.marketCap == null && !summary.value.investor) summary.value = null;
};

// 검색으로 종목을 바꾼 경우(마운트 때 setStockInfo 를 안 탄 경우)에만 다시 받는다
const loadSummary = async (code) => {
    if (summary.value?.code === code) return;
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/id/' + code);
        setSummary(data?.data);
    } catch {
        summary.value = null;   // 부가 정보라 실패해도 차트는 그대로
    }
};

// 억원 → "15조 6,973억" / "3,479억"
const formatEok = (eok) => {
    const v = Math.round(Math.abs(eok));
    const jo = Math.floor(v / 10000);
    const rest = v % 10000;
    if (jo === 0) return `${rest.toLocaleString()}억`;
    return rest ? `${jo.toLocaleString()}조 ${rest.toLocaleString()}억` : `${jo.toLocaleString()}조`;
};

// 순매수 대금(백만원) → "+3,479억" / "−4,800만". 1억 미만은 만원 단위
const formatNetAmt = (mil) => {
    if (!mil) return '0';
    const sign = mil > 0 ? '+' : '−';
    const eok = Math.abs(mil) / 100;
    const body = eok >= 1 ? formatEok(eok) : `${(Math.abs(mil) * 100).toLocaleString()}만`;
    return sign + body;
};

const signClass = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '');

const fetchChart = async () => {
    if (!searchParam.code) return;
    loadSummary(searchParam.code);
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
                    color: { up: '#C8282A', down: '#1F5BD1', unchanged: '#9A8C7E' }
                },
                { label: 'MA5',      data: all.ma5      || [], borderColor: '#f38980', type: 'line', pointRadius: 0 },
                { label: 'MA20',     data: all.ma20     || [], borderColor: '#efa55b', type: 'line', pointRadius: 0 },
                { label: 'MA60',     data: all.ma60     || [], borderColor: '#8bb400', type: 'line', pointRadius: 0 },
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
    const px = windowWidth.value < 768 ? 10 : 20;
    return Math.max(slicedLength.value * px, 400) + 'px';
});

// 차트가 화면보다 넓으면 가로 스크롤이 생긴다. 로드 직후엔 최근 봉(오른쪽 끝)이 보이게 맞춘다.
// .chart-scroll 은 로딩이 끝나야 렌더되므로 DOM 갱신(nextTick)과 레이아웃(rAF)을 기다린 뒤 이동한다.
const chartScroll = ref(null);
const scrollToLatest = async () => {
    await nextTick();
    requestAnimationFrame(() => {
        const el = chartScroll.value;
        if (el) el.scrollLeft = el.scrollWidth;
    });
};
watch([chartData, isLoading, dynamicWidth], () => {
    if (chartData.value && !isLoading.value) scrollToLatest();
});
</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰(홈·매수추천과 동일). 카드 없이 흰 배경 + 구분선.
// 캔들(상승/하락)은 앱 공통 등락색, 이동평균선·볼린저밴드는 데이터 구분용 색이라 <script> 쪽에 그대로 둔다.
$white:   #FFFFFF;
$line:    #EFE2BC;
$line-2:  #EAD9A6;
$chip:    #F6EBC8;
$hero:    #74462A;
$brown:   #7A4423;
$ink:     #2B1D14;
$sub:     #6B5B4E;
$sub-2:   #7A6B5D;
$cream:   #FFF8E1;

#chart-stocks {
    min-height: 100vh;
    background: $white;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 900px;
    margin: 0 auto;
    padding: 16px 16px 100px;
}

/* ── 검색 영역: 카드 대신 아래 구분선으로 차트와 나눈다 ── */
.search-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-bottom: 16px;
    border-bottom: 1px solid $line;

    /* SAutoInput 오버라이드(공용 컴포넌트라 이 화면에서만 덮어쓴다) */
    :deep(.auto-complete-container) { margin: 0; width: 100%; }

    :deep(.search-bar) {
        width: 100% !important;
        box-sizing: border-box;
        margin: 0 !important;
        min-height: 46px;
        background: $white;
        border: 1px solid $line-2;
        border-radius: 12px;
        padding: 2px 14px;
        box-shadow: none;
        transition: border-color .15s;

        &:focus-within { border-color: $brown; }
    }

    // 돋보기 이모지·검정 '종목' 배지는 이 화면 톤과 맞지 않아 숨긴다(placeholder 가 같은 뜻을 전한다)
    :deep(.search-bar .search-icon),
    :deep(.search-bar .label-badge) { display: none; }

    :deep(.search-bar input) {
        color: $ink;
        font-size: 16px;   // iOS 포커스 확대 방지
        text-align: left !important;
        background: transparent;
        &::placeholder { color: $sub-2; }
    }

    :deep(.suggestion-div) {
        background: $white;
        border: 1px solid $line-2;
        border-radius: 12px;
        box-shadow: 0 10px 24px rgba(74, 40, 20, .12);
    }

    :deep(.suggestion-header) {
        background: $white;
        border-bottom: 1px solid $line;
        .item { color: $sub; font-size: 12px; font-weight: 700; }
    }

    :deep(.list-item) {
        border-bottom: 1px solid $line;
        .s_code { color: $sub-2; }
        .s_name { color: $ink; }
        .s_type { color: $sub-2; }
        &:hover { background: rgba(239, 226, 188, .3); }
    }
}

/* ── 기간 · 기준일 · 조회 ── */
.date-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

// 일/주/월: 베이지 바탕의 세그먼트, 선택 항목만 갈색으로 채운다
.period-group {
    display: flex;
    gap: 2px;
    padding: 3px;
    background: $chip;
    border-radius: 10px;
}

.period-btn {
    min-width: 40px;
    min-height: 36px;
    padding: 0 10px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: $brown;
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: background .12s, color .12s;

    &.active { background: $hero; color: $cream; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 1px; }
}

.date-field {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 140px;

    .date-label {
        font-size: 13px;
        font-weight: 600;
        color: $sub;
        white-space: nowrap;
    }

    .date-input {
        flex: 1;
        min-height: 42px;
        padding: 0 10px;
        border: 1px solid $line-2;
        border-radius: 10px;
        font-size: 16px;
        font-family: inherit;
        color: $ink;
        background: $white;
        outline: none;
        transition: border-color .15s;

        &:focus { border-color: $brown; }
    }
}

.search-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 42px;
    padding: 0 18px;
    background: $hero;
    color: $cream;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;

    &:active { transform: scale(0.97); }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}

/* ── 차트: 카드 없이 제목 줄 + 차트 ── */
.chart-section { padding-top: 16px; }

.chart-card {
    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
        padding-bottom: 10px;

        .stock-title {
            display: flex;
            align-items: baseline;
            gap: 8px;

            .stock-name { font-size: 18px; font-weight: 700; color: $ink; }
            .stock-code { font-size: 13px; color: $sub-2; }
        }

        .legend {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
    }

    // 시가총액 · 전일 수급 — 칩 없이 한 줄 텍스트(라벨 + 값), 등락은 글자색으로만
    .stock-summary {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        column-gap: 16px;
        row-gap: 4px;
        margin: 0 0 10px;
        font-size: 13px;

        > div { display: flex; gap: 6px; }
        dt { color: $sub-2; }
        dd { margin: 0; font-weight: 600; color: $ink; }
        dd.up   { color: #C8282A; }
        dd.down { color: #1F5BD1; }

        .summary-note {
            flex-basis: 100%;
            margin: 0;
            font-size: 12px;
            color: $sub-2;
        }
    }

    .chart-header {

        .leg-item {
            font-size: 12px;
            font-weight: 600;
            color: $sub;
            display: flex;
            align-items: center;
            gap: 5px;

            &::before {
                content: '';
                display: inline-block;
                width: 16px;
                height: 2px;
                background: var(--c);
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
        padding: 4px 0 8px;

        &::-webkit-scrollbar       { height: 4px; }
        &::-webkit-scrollbar-track { background: transparent; }
        &::-webkit-scrollbar-thumb { background: $line-2; border-radius: 2px; }
    }

    .chart-wrap {
        min-width: 400px;
        height: 62vh;
    }
}

/* ── Loading ── */
.chart-skeleton {
    height: 62vh;
    background: rgba(239, 226, 188, .25);
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    overflow: hidden;
}

.loading-bar {
    width: 220px;
    height: 3px;
    background: $line;
    border-radius: 2px;
    overflow: hidden;

    &::after {
        content: '';
        display: block;
        height: 100%;
        width: 40%;
        background: $hero;
        animation: slide 1.2s ease-in-out infinite;
    }
}

.loading-label { font-size: 13px; color: $sub-2; }

@keyframes slide {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(650%); }
}

/* ── Empty ── */
.empty-box {
    text-align: center;
    padding: 72px 0;
    color: $sub;
    font-size: 14px;
}

/* ── 태블릿 / 좁은 화면 ── */
@media (max-width: 768px) {
    .legend { gap: 8px; }
    .leg-item { font-size: 11px; }
    .chart-wrap { height: 52vh; }
    .chart-skeleton { height: 52vh; }
}

/* ── 모바일 ── */
@media (max-width: 480px) {
    .contents { padding: 12px 16px 72px; }

    /* [일|주|월] [날짜] [조회] 를 한 줄에. 가변 폭은 날짜 칸 하나만 맡긴다. */
    .date-row     { flex-wrap: nowrap; gap: 6px; }
    .period-group { flex: none; }
    .period-btn   { min-width: 34px; padding: 0 6px; }

    /* min-width:0 이 핵심 — 기본값(auto)이면 date input 의 내재 폭이 행을 화면 밖으로 밀어낸다.
     * 라벨('기준일자')은 375px 에서 날짜 끝을 자르므로 숨긴다(접근성 이름은 aria-label). */
    .date-field   { flex: 1 1 0; min-width: 0; gap: 4px; }
    .date-label   { display: none; }
    .date-input   { flex: 1 1 0; min-width: 0; width: 100%; padding: 0 6px; }

    .search-btn   { padding: 0 12px; }
    .search-btn svg { display: none; }

    .chart-card .chart-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }
    .chart-card .chart-header .legend {
        width: 100%;
        overflow-x: auto;
        flex-wrap: nowrap;
        padding-bottom: 2px;
        -webkit-overflow-scrolling: touch;
        &::-webkit-scrollbar { height: 3px; }
    }
    .leg-item { white-space: nowrap; }

    .chart-card .chart-wrap { height: 46vh; min-width: 320px; }
    .chart-skeleton { height: 46vh; }
}

@media (max-width: 360px) {
    .period-btn { min-width: 30px; padding: 0 4px; font-size: 13px; }
}
</style>
