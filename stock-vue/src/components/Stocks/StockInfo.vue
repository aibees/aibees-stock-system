<template>
    <div id="stock-analysis">
        <Headers :prop_title="title" />

        <div class="contents">
            <!-- 검색 섹션 -->
            <section class="search-section">
                <SAutoInput
                id="search-input"
                v-model:name="inputName"
                v-model:code="inputCode"
                @search="stockSearchHandler"
                width="100%" />
                <button v-if="inputCode" class="chart-btn" @click="goToChart">차트보기</button>
            </section>

            <transition name="fade-slide">
                <div v-if="stockDetail" class="body-box">

                    <!-- ① AI 분석 결과 (화면 80% 공간) -->
                    <section class="ai-result-section">
                        <div class="section-header">
                            <span class="section-icon">✨</span>
                            <span class="section-title">AI 종목 분석</span>
                            <span v-if="aiModel" class="section-badge">{{ aiModel }}</span>
                            <!-- 토큰 사용량 -->
                            <span v-if="aiTokens" class="token-info">
                                in&nbsp;{{ aiTokens.input_tokens }}&nbsp;/&nbsp;out&nbsp;{{ aiTokens.output_tokens }}
                            </span>
                        </div>
                        <div class="ai-result-body">
                            <!-- marked로 변환된 HTML 렌더링 -->
                            <div v-if="aiHtml" class="markdown-body" v-html="aiHtml" />
                            <div v-else class="ai-loading">
                                <div class="loading-dots">
                                    <span></span><span></span><span></span>
                                </div>
                                <span class="loading-label">AI 종목분석 중입니다. <br/> Agent 질문처럼 오래 걸리니 기다려주세요.</span>
                            </div>
                        </div>
                    </section>

                    <!-- ② 최근 분기 실적 -->
                    <!-- <section class="quarterly-section">
                        <div class="section-header">
                            <span class="section-title">최근 분기 실적</span>
                            <span class="section-unit">단위: 억원</span>
                        </div>
                        <div class="quarterly-table">
                            <div class="qt-row qt-head">
                                <div class="qt-cell label-col"></div>
                                <div class="qt-cell" v-for="q in quarterlyResults" :key="q.quarter">{{ q.quarter }}</div>
                            </div>
                            <div class="qt-row">
                                <div class="qt-cell label-col">매출액</div>
                                <div class="qt-cell num" v-for="q in quarterlyResults" :key="'rev-' + q.quarter">
                                    {{ q.revenue }}
                                </div>
                            </div>
                            <div class="qt-row">
                                <div class="qt-cell label-col">영업이익</div>
                                <div class="qt-cell num" v-for="q in quarterlyResults" :key="'op-' + q.quarter">
                                    <span :class="profitClass(q.operatingProfit)">{{ q.operatingProfit }}</span>
                                </div>
                            </div>
                            <div class="qt-row last">
                                <div class="qt-cell label-col">당기순이익</div>
                                <div class="qt-cell num" v-for="q in quarterlyResults" :key="'np-' + q.quarter">
                                    <span :class="profitClass(q.netProfit)">{{ q.netProfit }}</span>
                                </div>
                            </div>
                        </div>
                    </section> -->

                    <!-- ③ 추천 성과 추적 (최근 1달 이내 추천된 경우) -->
                    <section class="rec-section" v-if="recommendationData">
                        <div class="section-header">
                            <span class="section-title">추천 성과 추적</span>
                            <span class="rec-date-badge">추천일 {{ recommendationData.rec_record.ymd }}</span>
                        </div>
                        <div class="rec-grid">
                            <div class="rec-card base-card">
                                <span class="rec-label">추천당시 종가 {{ recommendationData.rec_record.ymd }}</span>
                                <span class="rec-price">{{ formatNumber(recommendationData.rec_record.close) }}<em>원</em></span>
                                <span class="rec-rate-badge neutral">기준가</span>
                            </div>
                            <div class="rec-card">
                                <span class="rec-label">현재 종가 {{ recommendationData.now_record.ymd }}</span>
                                <span class="rec-price">{{ formatNumber(recommendationData.now_record.close) }}<em>원</em></span>
                                <span class="rec-rate-badge" :class="rateClass(recommendationData.now_record.rate)">
                                    {{ formatRate(recommendationData.now_record.rate) }}
                                </span>
                            </div>
                            <div class="rec-card high-card">
                                <span class="rec-label">추천 후 최고가 {{ recommendationData.max_record.ymd }}</span>
                                <span class="rec-price">{{ formatNumber(recommendationData.max_record.close) }}<em>원</em></span>
                                <span class="rec-rate-badge" :class="rateClass(recommendationData.max_record.rate)">
                                    {{ formatRate(recommendationData.max_record.rate) }}
                                </span>
                            </div>
                        </div>
                    </section>

                </div>
            </transition>
        </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { marked } from 'marked';
import aibeesApi from '@scripts/aibeesApi.js';

// marked 옵션
marked.setOptions({ breaks: true, gfm: true });

const route = useRoute();
const router = useRouter();
const title = ref('종목 심층 분석');
const stockDetail = ref(null);
const aiSummary = ref('');       // 원본 markdown 텍스트
const aiTokens = ref(null);      // { input, output } — API 응답에서 채워짐
const aiModel = ref('');
const inputName = ref('');
const inputCode = ref('');

// markdown → HTML 변환 (v-html에 바인딩)
const aiHtml = computed(() =>
    aiSummary.value ? marked.parse(aiSummary.value) : ''
);

// 최근 분기 실적 (mock)
const quarterlyResults = ref([
    { quarter: '24Q2', revenue: '2,841', operatingProfit: '312', netProfit: '228' },
    { quarter: '24Q3', revenue: '3,104', operatingProfit: '-45', netProfit: '-38' },
    { quarter: '24Q4', revenue: '3,520', operatingProfit: '487', netProfit: '361' },
    { quarter: '25Q1', revenue: '3,215', operatingProfit: '401', netProfit: '290' },
]);

// 최근 1달 이내 추천 데이터 (mock, null이면 섹션 미노출)
const recommendationData = ref({});

onMounted(() => {
    const code = route.query.stock_code;
    const name = route.query.stock_name;
    if (code) {
        inputCode.value = code;
        inputName.value = name || code;
        stockSearchHandler(code);
    }
});

const goToChart = () => {
    router.push({ path: '/charts/stock', query: { code: inputCode.value } });
};

const stockSearchHandler = (code) => {
    if (!code) return;
    stockDetail.value = { code };
    aiSummary.value = '';
    aiTokens.value = null;
    aiModel.value = '';

    getAiResult(code);
    getRecommandResult(code);
};

const getAiResult = async (code) => {
    try {
        const { data } = await aibeesApi.get(`/api/v1/anthropic/stock-analysis?stock_code=${code}`);
        // data.data 응답 구조:
        // {
        //   content : string,          // markdown 형식의 AI 분석 결과
        //   usage   : { input_tokens, output_tokens },
        //   model   : string           // 사용 모델명 (예: "gemini-2.0-flash")
        // }
        aiSummary.value = data.data.content ?? '';
        aiTokens.value  = data.data.usage   ?? null;
        aiModel.value   = data.data.model   ?? '';
    } catch (e) {
        console.error(e);
        aiSummary.value = '분석 결과를 불러오지 못했습니다.';
    }
}

const getRecommandResult = async (code) => {
    try {
        const { data } = await aibeesApi.get(`/api/v1/stocks/rec-record?stock_code=${code}`);
        recommendationData.value = data.data;
    } catch (e) {
        console.error(e);
    }
}

const profitClass = (val) => {
    const n = parseFloat(String(val).replace(/,/g, ''));
    if (n > 0) return 'val-up';
    if (n < 0) return 'val-down';
    return '';
};

const rateClass = (rate) => {
    if (rate > 0) return 'rate-up';
    if (rate < 0) return 'rate-down';
    return 'neutral';
};

const formatNumber = (v) => Number(v).toLocaleString();
const formatRate = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%';
</script>

<style scoped lang="scss">
/* ── 색상 변수 (Home.vue 동일) ── */
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
$red:      #c92a2a;
$amber:    #e67700;

/* ── 기본 레이아웃 ── */
#stock-analysis {
    min-height: 100vh;
    background: $white;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 600px;
    margin: 0 auto;
    padding: 20px 16px 100px;
}

/* ── 검색 영역 — SAutoInput 스타일 오버라이드 ── */
.search-section {
    margin-bottom: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;

    .chart-btn {
        align-self: flex-end;
        padding: 5px 12px;
        border: 1px solid $gray-200;
        border-radius: 0.3rem;
        background: $white;
        color: $gray-700;
        font-size: 0.72rem;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        transition: border-color .12s, color .12s, background .12s;

        &:hover { border-color: $blue; color: $blue; background: $gray-50; }
    }

    /* ① 컨테이너 자체 여백 제거 */
    :deep(.auto-complete-container) {
        margin: 0;
        width: 100%;
    }

    /* ② 각 요소별로 :deep() 평탄하게 선언 — 중첩 컴파일 문제 방지 */
    :deep(.search-bar) {
        width: 100% !important;   /* SAutoInput의 width:90% 덮어쓰기 */
        box-sizing: border-box;
        margin: 0 !important;
        background: $white;
        border: 1.5px solid $gray-200;
        border-radius: 0.75rem;
        padding: 6px 6px 6px 14px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        transition: border-color 0.15s;

        &:focus-within {
            border-color: $blue;
            box-shadow: 0 2px 12px rgba(25, 113, 194, 0.12);
        }
    }

    :deep(.search-bar .search-icon) {
        font-size: 1rem;
        margin-right: 10px;
    }

    :deep(.search-bar input) {
        color: $gray-900;
        font-size: 0.95rem;

        &::placeholder { color: $gray-400; }
    }

    :deep(.search-bar .search-btn) {
        background: $navy;
        color: $white;
        border-radius: 0.5rem;
        padding: 9px 18px;
        font-size: 0.88rem;
        font-weight: 700;
        font-family: inherit;
        white-space: nowrap;

        &:hover  { background: $blue; }
        &:active { transform: scale(0.97); }
    }

    /* 자동완성 드롭다운 */
    :deep(.suggestion-div) {
        background: $white;
        border: 1px solid $gray-200;
        border-radius: 0.6rem;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
    }

    :deep(.suggestion-header) {
        background: $gray-50;
        border-bottom: 1px solid $gray-100;

        .item {
            color: $gray-500;
            font-size: 0.75rem;
            font-weight: 700;
        }
    }

    :deep(.list-item) {
        .s_code { color: $gray-400; }
        .s_name { color: $gray-900; }
        .s_type { color: $gray-400; }

        &:hover { background: $gray-50; }
    }
}

/* ── body-box ── */
.body-box {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* ── 공통: 섹션 헤더 ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .section-icon {
        font-size: 0.95rem;
    }

    .section-title {
        text-align: start;
        font-size: 0.95rem;
        font-weight: 700;
        color: $gray-900;
        flex: 1;
    }

    .section-badge {
        font-size: 0.68rem;
        font-weight: 700;
        color: $navy;
        background: #dbe4ff;
        border: 1px solid #bac8ff;
        padding: 2px 8px;
        border-radius: 0.3rem;
    }

    .token-info {
        font-size: 0.65rem;
        font-weight: 500;
        color: $gray-400;
        background: $gray-50;
        border: 1px solid $gray-100;
        padding: 2px 7px;
        border-radius: 0.3rem;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }

    .section-unit {
        font-size: 0.72rem;
        color: $gray-400;
    }
}

/* ── ① AI 분석 결과 섹션 ── */
.ai-result-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.75rem;
    padding: 18px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);

    .ai-result-body {
        // min-height: 80vw; /* 모바일 기준 화면 폭의 80% → 세로 큰 공간 */
        max-height: 50vh;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;

        @media (min-width: 600px) {
            min-height: 400px;
        }
    }

    /* ── marked 렌더링 영역 ── */
    .markdown-body {
        overflow: scroll;
        text-align: start;
        font-size: 0.9rem;
        line-height: 1.8;
        color: $gray-700;
        word-break: keep-all;

        :deep(h1), :deep(h2) {
        font-size: 0.95rem;
            font-weight: 700;
            color: $navy;
            margin: 18px 0 6px;
            padding-bottom: 5px;
            border-bottom: 1px solid $gray-100;
        }

        :deep(h3) {
            font-size: 0.88rem;
            font-weight: 700;
            color: $gray-900;
            margin: 14px 0 4px;
        }

        :deep(p) {
            margin: 6px 0;
        color: $gray-700;
        }

        :deep(ul), :deep(ol) {
            padding-left: 18px;
            margin: 6px 0;

            li {
                font-size: 0.88rem;
                line-height: 1.7;
                color: $gray-700;
            }
        }

        :deep(strong) {
            font-weight: 700;
            color: $gray-900;
        }

        :deep(code) {
            background: $gray-50;
            border: 1px solid $gray-100;
            border-radius: 0.3rem;
            padding: 1px 5px;
            font-size: 0.82rem;
            color: $navy;
        }

        :deep(pre) {
            background: $gray-50;
            border: 1px solid $gray-100;
            border-radius: 0.5rem;
            padding: 12px 14px;
            overflow-x: auto;

            code {
                border: none;
                padding: 0;
                background: none;
            }
        }

        :deep(blockquote) {
            border-left: 3px solid $blue;
            margin: 8px 0;
            padding: 4px 12px;
            color: $gray-500;
            background: $gray-50;
            border-radius: 0 0.3rem 0.3rem 0;
        }

        :deep(table) {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            margin: 10px 0;

            th {
                background: $gray-50;
                color: $gray-500;
                font-weight: 700;
                padding: 7px 8px;
                border: 1px solid $gray-100;
                text-align: center;
            }

            td {
                padding: 7px 8px;
                border: 1px solid $gray-100;
                color: $gray-700;
                text-align: right;

                &:first-child { text-align: left; }
            }

            tr:nth-child(even) td { background: $gray-50; }
        }

        /* 첫 번째 h2 상단 여백 제거 */
        :deep(> h1:first-child),
        :deep(> h2:first-child) { margin-top: 0; }
    }

    .ai-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        flex: 1;
        gap: 14px;

        .loading-dots {
            display: flex;
            gap: 8px;

            span {
                width: 8px;
                height: 8px;
                background: $blue;
                border-radius: 50%;
                animation: bounce 1.2s infinite ease-in-out;

                &:nth-child(2) { animation-delay: 0.2s; }
                &:nth-child(3) { animation-delay: 0.4s; }
            }
        }

        .loading-label {
            font-size: 0.85rem;
            color: $gray-500;
        }
    }
}

/* ── ② 분기 실적 ── */
.quarterly-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.75rem;
    padding: 18px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.quarterly-table {
    border: 1px solid $gray-100;
    border-radius: 0.5rem;
    overflow: hidden;

    .qt-row {
        display: grid;
        grid-template-columns: 5.5rem repeat(4, 1fr);
        border-bottom: 1px solid $gray-100;

        &.qt-head {
            background: $gray-50;

            .qt-cell {
                font-size: 0.72rem;
                font-weight: 700;
                color: $gray-500;
            }
        }

        &.last {
            border-bottom: none;
        }
    }

    .qt-cell {
        padding: 9px 4px;
        text-align: center;
        font-size: 0.8rem;
        color: $gray-700;

        &.label-col {
            text-align: left;
            padding-left: 10px;
            font-size: 0.78rem;
            font-weight: 600;
            color: $gray-500;
            background: $gray-50;
            border-right: 1px solid $gray-100;
        }

        &.num {
            font-weight: 600;
            font-size: 0.82rem;
        }
    }

    .val-up   { color: $red; }
    .val-down { color: $navy; }
}

/* ── ③ 추천 성과 ── */
.rec-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.75rem;
    padding: 18px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.rec-date-badge {
    font-size: 0.72rem;
    color: $gray-500;
    background: $gray-100;
    border: 1px solid $gray-200;
    padding: 2px 8px;
    border-radius: 0.3rem;
}

.rec-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
}

.rec-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 8px;
    border-radius: 0.6rem;
    border: 1px solid $gray-100;
    background: $gray-50;
    text-align: center;

    &.base-card {
        border-color: $gray-200;
    }

    &.high-card {
        border-color: #ffd8a8;
        background: #fff9f0;
    }

    .rec-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: $gray-500;
        line-height: 1.3;
    }

    .rec-price {
        font-size: 1rem;
        font-weight: 800;
        color: $gray-900;
        line-height: 1.2;

        em {
            font-size: 0.7rem;
            font-weight: 500;
            color: $gray-500;
            font-style: normal;
            margin-left: 1px;
        }
    }
}

.rec-rate-badge {
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 0.3rem;

    &.neutral  { background: $gray-100; color: $gray-500; }
    &.rate-up  { background: #ffe3e3; color: $red; }
    &.rate-down{ background: #dbe4ff; color: $navy; }
}

/* ── 전환 애니메이션 ── */
.fade-slide-enter-active,
.fade-slide-leave-active {
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.fade-slide-enter-from {
    opacity: 0;
    transform: translateY(16px);
}
.fade-slide-leave-to {
    opacity: 0;
}

/* ── 로딩 바운스 ── */
@keyframes bounce {
    0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
    40%           { transform: scale(1);   opacity: 1; }
}
</style>
