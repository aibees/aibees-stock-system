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
                        <!-- 분석 레이어 표시 ON/OFF(일봉 + 서버가 계산한 모듈만 나온다) -->
                        <div v-if="availableLayers.length" class="layer-menu" ref="layerMenuEl">
                            <button class="layer-btn" :aria-expanded="layerMenuOpen" @click="layerMenuOpen = !layerMenuOpen">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                                    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/>
                                    <circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="7" cy="18" r="2"/>
                                </svg>
                                차트 설정
                            </button>
                            <ul v-if="layerMenuOpen" class="layer-list" role="menu">
                                <li v-for="l in availableLayers" :key="l.key" role="menuitemcheckbox"
                                    :aria-checked="isLayerOn(l.key)" :class="{ on: isLayerOn(l.key) }" @click="toggleLayer(l.key)">
                                    <span class="check">{{ isLayerOn(l.key) ? '✓' : '' }}</span>{{ l.label }}
                                </li>
                            </ul>
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
                    <!-- 휠/핀치로 확대, 드래그로 이동, 마우스를 올리면 위 범례가 그 봉 값으로 바뀐다 -->
                    <div class="chart-wrap">
                        <LwStockChart :data="chartData" :layers="layers" :layer-options="layerOptions" />
                    </div>
                    <ChartAnalysisSummary :analysis="chartData.analysis" :layers="layers"
                        :pick-index="elliottPick" @pick="k => elliottPick = k" />
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
import LwStockChart from '../common/comp/LwStockChart.vue';
import ChartAnalysisSummary from '../common/comp/chartAnalysis/ChartAnalysisSummary.vue';
import { LAYERS } from '../common/comp/chartAnalysis/layers.js';
import { useChartLayers } from '../common/comp/chartAnalysis/useChartLayers.js';
import aibeesApi from '@scripts/aibeesApi.js';
import { formatEok, formatNetAmt, signClass, shortYmd } from '@scripts/marketFormat.js';

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
const isLoading    = ref(false);

// ── 분석 레이어 ON/OFF ───────────────────────────────────────────────
// 서버가 계산해 준 모듈(analysis 의 key)만 메뉴에 나오고, 켜고 끈 상태는 이 브라우저에 기억한다
const { enabled: enabledLayers, isOn: isLayerOn, toggle: toggleLayer } = useChartLayers();
const availableLayers = computed(() => LAYERS.filter(l => chartData.value?.analysis?.[l.key] !== undefined));
const layers          = computed(() => availableLayers.value.map(l => l.key).filter(k => enabledLayers.value.includes(k)));
const layerMenuOpen   = ref(false);
const elliottPick     = ref(0);   // 차트에 그릴 엘리엇 해석(0 = 주요 해석). 종목을 다시 조회하면 주요 해석으로
const layerOptions    = computed(() => ({ elliott: elliottPick.value }));
watch(chartData, () => { elliottPick.value = 0; });
const layerMenuEl     = ref(null);
const closeLayerMenu  = (e) => { if (layerMenuEl.value && !layerMenuEl.value.contains(e.target)) layerMenuOpen.value = false; };
onMounted(() => document.addEventListener('click', closeLayerMenu));
onBeforeUnmount(() => document.removeEventListener('click', closeLayerMenu));

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
            dateLabel: shortYmd(inv.ymd),
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

        chartData.value = data.data;   // { ohcl, volume, rate, ma5..ma120, bb_* } 그대로 넘긴다
    } catch (e) {
        console.error(e);
    } finally {
        isLoading.value = false;
    }
};
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

    // 범례(OHLC·이평 값)가 차트 컴포넌트 안에 있어 높이에 그만큼 더한다
    .chart-wrap {
        height: 66vh;
    }

    // 차트 설정: 버튼은 글자+아이콘, 펼친 목록은 ✓ 표시 행
    .layer-menu { position: relative; }
    .layer-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        height: 32px;
        padding: 0 4px;
        background: none;
        border: 0;
        color: $ink;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
    }
    .layer-list {
        position: absolute;
        right: 0;
        top: 36px;
        z-index: 10;
        min-width: 168px;
        margin: 0;
        padding: 6px 0;
        list-style: none;
        background: $white;
        border: 1px solid $line-2;
        border-radius: 10px;
        box-shadow: 0 6px 20px rgba(43, 29, 20, .10);

        li {
            display: flex;
            align-items: center;
            padding: 8px 14px;
            font-size: 13px;
            color: $sub;
            cursor: pointer;
            &.on { color: $ink; font-weight: 600; }
            &:hover { background: $cream; }
        }
        .check { width: 18px; color: $brown; }
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
// PC: 차트를 넓게 보도록 화면 폭의 90%까지 쓴다(태블릿·모바일은 위 900px 기준 그대로)
@media (min-width: 769px) {
    .contents { max-width: 90%; }
}

@media (max-width: 768px) {
    .chart-wrap { height: 58vh; }
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
    .chart-card .chart-wrap { height: 56vh; }
    .chart-skeleton { height: 46vh; }
    // 헤더가 세로로 쌓이면 설정 버튼이 왼쪽에 붙는다 — 목록도 왼쪽 기준으로 펼쳐 화면 밖으로 나가지 않게
    .chart-card .layer-list { left: 0; right: auto; }
}

@media (max-width: 360px) {
    .period-btn { min-width: 30px; padding: 0 4px; font-size: 13px; }
}
</style>
